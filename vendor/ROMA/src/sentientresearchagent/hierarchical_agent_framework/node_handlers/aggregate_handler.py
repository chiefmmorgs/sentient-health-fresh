"""
AggregateHandler - Handles nodes that need aggregation.

This simplified handler focuses solely on aggregation logic,
delegating common functionality to BaseNodeHandler.
"""

from typing import Any, List
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import ContextItem
from .base_handler import BaseNodeHandler, HandlerContext
from sentientresearchagent.hierarchical_agent_framework.services.context_formatter import ContextFormatter, ContextFormat


class AggregateHandler(BaseNodeHandler):
    """
    Handles nodes that need to aggregate results from sub-tasks.
    
    This handler is responsible for:
    - Collecting results from child nodes
    - Filtering redundant information
    - Building aggregation context
    - Executing aggregator agent
    - Synthesizing final result
    """
    
    def __init__(self):
        super().__init__("AggregateHandler")
    
    def _validate_node_state(self, node: TaskNode) -> bool:
        """Validate node is ready for aggregation."""
        return node.status == TaskStatus.AGGREGATING
    
    def _get_stage_name(self) -> str:
        """Get tracing stage name."""
        return "aggregation"
    
    async def _process(self, node: TaskNode, context: HandlerContext) -> Any:
        """
        Main aggregation logic.
        
        Args:
            node: Node to aggregate
            context: Handler context
            
        Returns:
            Aggregated result
        """
        # Collect child results
        child_results = await self._collect_child_results(node, context)
        
        # Build aggregation context with both child results and horizontal dependencies
        aggregation_context = await self._build_aggregation_context(
            node, 
            child_results, 
            context
        )
        
        # Store input for tracing
        node.input_payload_dict = aggregation_context.model_dump()
        
        # Get aggregator agent
        aggregator = await self._get_agent_for_node(node, context, "aggregate")
        if not aggregator:
            raise ValueError(f"No aggregator available for node {node.task_id}")
        
        # Execute aggregation
        logger.info(f"Executing aggregation for node {node.task_id} with {len(child_results)} child results")
        result = await aggregator.process(node, aggregation_context, context.trace_manager)
        
        return result
    
    async def _collect_child_results(
        self, 
        node: TaskNode, 
        context: HandlerContext
    ) -> List[ContextItem]:
        """
        Collect results from child nodes.
        
        Args:
            node: Parent node
            context: Handler context
            
        Returns:
            List of child results as context items
        """
        child_results = []
        
        if not node.sub_graph_id:
            logger.warning(f"Node {node.task_id} has no sub-graph for aggregation")
            return child_results
        
        # Get child nodes from task graph
        child_nodes = []
        if context.task_graph:
            child_nodes = context.task_graph.get_nodes_in_graph(node.sub_graph_id)
        else:
            logger.error(f"No task graph available in context for aggregation of {node.task_id}")
            return child_results
        
        # Filter completed children
        completed_children = [
            child for child in child_nodes
            if child.status in [TaskStatus.DONE, TaskStatus.FAILED]
        ]
        
        # Filter redundant results using smart dependency analysis
        non_redundant_children = await self._filter_redundant_children(
            completed_children, 
            context
        )
        
        logger.info(f"Collecting results from {len(non_redundant_children)} children "
                   f"(filtered from {len(completed_children)} completed)")
        
        # Convert to context items
        for child in non_redundant_children:
            content = child.result if child.status == TaskStatus.DONE else child.error
            
            # Smart content processing based on child type
            processed_content = await self._process_child_content(
                content, 
                child.goal, 
                child.task_type
            )
            
            context_item = ContextItem(
                source_task_id=child.task_id,
                source_task_goal=child.goal,
                content=processed_content,
                content_type_description=f"child_{child.status.value.lower()}_output"
            )
            
            child_results.append(context_item)
        
        return child_results
    
    async def _filter_redundant_children(
        self,
        children: List[TaskNode],
        context: HandlerContext
    ) -> List[TaskNode]:
        """
        Filter out redundant children based on dependency analysis.
        
        If a child depends on all other children (directly or transitively),
        we only need to include that child since it has already processed
        all the information from its dependencies.
        
        Args:
            children: List of completed child nodes
            context: Handler context
            
        Returns:
            Filtered list of non-redundant children
        """
        if len(children) <= 1:
            return children
        
        # Build dependency map
        dependency_map = {}
        for child in children:
            deps = set()
            
            # Get direct dependencies from aux_data
            depends_on_indices = child.aux_data.get('depends_on_indices', [])
            if depends_on_indices and child.parent_node_id:
                # Map indices to actual task IDs
                parent_node = None
                if context.task_graph:
                    parent_node = context.task_graph.get_node(child.parent_node_id)
                
                if parent_node and parent_node.planned_sub_task_ids:
                    for dep_idx in depends_on_indices:
                        if 0 <= dep_idx < len(parent_node.planned_sub_task_ids):
                            dep_id = parent_node.planned_sub_task_ids[dep_idx]
                            deps.add(dep_id)
            
            dependency_map[child.task_id] = deps
        
        # Compute transitive dependencies
        def get_transitive_deps(task_id: str, visited: set = None) -> set:
            if visited is None:
                visited = set()
            if task_id in visited:
                return set()
            visited.add(task_id)
            
            direct_deps = dependency_map.get(task_id, set())
            all_deps = direct_deps.copy()
            
            for dep_id in direct_deps:
                all_deps.update(get_transitive_deps(dep_id, visited))
            
            return all_deps
        
        # Check if any child depends on all others
        result_children = []
        child_ids = {child.task_id for child in children}
        
        for child in children:
            transitive_deps = get_transitive_deps(child.task_id)
            other_children = child_ids - {child.task_id}
            
            # If this child depends on all other children, it's comprehensive
            if other_children.issubset(transitive_deps):
                logger.info(
                    f"Node {child.task_id} depends on all other siblings - "
                    f"using only this node for aggregation"
                )
                return [child]  # Only include this comprehensive child
        
        # No comprehensive child found - include all
        logger.info(f"No comprehensive child found - including all {len(children)} children")
        return children
    
    async def _process_child_content(
        self, 
        content: Any, 
        goal: str, 
        task_type: str
    ) -> str:
        """
        Process child content for aggregation.
        
        Args:
            content: Raw content from child
            goal: Child's goal
            task_type: Child's task type
            
        Returns:
            Processed content string - NO TRUNCATION
        """
        if content is None:
            return f"No output for: {goal}"
        
        # Use unified formatter to extract content - NO TRUNCATION
        return ContextFormatter._extract_output(content)
    
    async def _build_aggregation_context(
        self,
        node: TaskNode,
        child_results: List[ContextItem],
        context: HandlerContext
    ) -> Any:
        """
        Build context for aggregation including both child results
        and horizontal dependencies.
        
        Args:
            node: Node being aggregated
            child_results: Results from children
            context: Handler context
            
        Returns:
            Aggregation context
        """
        # Get base context with horizontal dependencies
        base_context = await self._build_context_for_node(
            node,
            context,
            context_type="aggregation"
        )
        
        # Combine with child results
        if child_results:
            if base_context.relevant_context_items:
                # Add child results to existing context
                base_context.relevant_context_items.extend(child_results)
            else:
                # Just child results
                base_context.relevant_context_items = child_results
            
            # Update formatted context using unified formatter
            all_items = base_context.relevant_context_items or []
            
            # Collect status information for child results
            statuses = {}
            if child_results:
                for child in child_results:
                    statuses[child.source_task_id] = 'DONE'  # We only include completed children
            
            # Use unified formatter
            base_context.formatted_full_context = ContextFormatter.format_context(
                context_items=all_items,
                format_type=ContextFormat.AGGREGATION,
                additional_info={'statuses': statuses}
            )
        
        return base_context
    
    async def _post_process(
        self, 
        node: TaskNode, 
        context: HandlerContext, 
        result: Any
    ):
        """Post-process aggregation result."""
        # Set output type
        node.output_type_description = "aggregated_result"
        
        # Handle the result
        await self._handle_agent_result(
            node,
            result,
            context,
            success_status=TaskStatus.DONE
        )
        
        # Call parent post-process
        await super()._post_process(node, context, result)