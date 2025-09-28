"""
ContextBuilderService - Centralized context building service.

This service consolidates all context building logic,
making it easier to understand and modify how context is assembled.
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, ContextItem, ParentHierarchyContext, ParentContextNode
)
from .context_formatter import ContextFormatter, ContextFormat

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore


class ContextType(Enum):
    """Types of context to build."""
    DEFAULT = "default"
    PLANNING = "planning"
    EXECUTION = "execution"
    AGGREGATION = "aggregation"
    ATOMIZATION = "atomization"
    MODIFICATION = "modification"


@dataclass
class ContextConfig:
    """Configuration for context building."""
    max_context_length: int = 10000
    include_parent_hierarchy: bool = False  # Disabled by default as it's redundant
    include_horizontal_dependencies: bool = True
    include_similar_tasks: bool = False  # Disabled by default
    max_similar_tasks: int = 5
    summarize_long_content: bool = False  # Don't summarize - show full content
    target_summary_words: int = 150


class ContextBuilderService:
    """
    Service for building context for agent tasks.
    
    This service:
    - Centralizes context building logic
    - Provides different context types for different purposes
    - Manages context size and relevance
    - Supports custom context strategies
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        """
        Initialize the ContextBuilderService.
        
        Args:
            config: Context building configuration
        """
        self.config = config or ContextConfig()
        
        # Context building strategies
        self._strategies = {
            ContextType.DEFAULT: self._build_default_context,
            ContextType.PLANNING: self._build_planning_context,
            ContextType.EXECUTION: self._build_execution_context,
            ContextType.AGGREGATION: self._build_aggregation_context,
            ContextType.ATOMIZATION: self._build_atomization_context,
            ContextType.MODIFICATION: self._build_modification_context,
        }
        
        # Metrics
        self._metrics = {
            "contexts_built": 0,
            "average_context_size": 0,
            "contexts_by_type": {}
        }
        
        logger.info("ContextBuilderService initialized")
    
    async def build_context(
        self,
        node: TaskNode,
        context_type: str,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> AgentTaskInput:
        """
        Build context for a node.
        
        Args:
            node: Node needing context
            context_type: Type of context to build
            knowledge_store: Knowledge store for retrieving context
            task_graph: Task graph for hierarchy information
            additional_context: Additional context to include
            
        Returns:
            Built context
        """
        # Convert string to enum
        try:
            context_enum = ContextType(context_type)
        except ValueError:
            logger.warning(f"Unknown context type: {context_type}, using default")
            context_enum = ContextType.DEFAULT
        
        # Update metrics
        self._metrics["contexts_built"] += 1
        self._metrics["contexts_by_type"][context_enum.value] = \
            self._metrics["contexts_by_type"].get(context_enum.value, 0) + 1
        
        # Get strategy
        strategy = self._strategies.get(context_enum, self._build_default_context)
        
        # Build context
        try:
            context = await strategy(node, knowledge_store, task_graph, additional_context)
            
            # Update average size
            self._update_average_size(len(context.formatted_full_context or ""))
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to build {context_type} context for {node.task_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return minimal context on error
            return self._build_minimal_context(node)
    
    async def _build_default_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build default context with all relevant information."""
        context_items = []
        
        # 1. Parent hierarchy context
        parent_context = None
        if self.config.include_parent_hierarchy and task_graph:
            parent_context = await self._build_parent_hierarchy(node, task_graph, knowledge_store)
        
        # 2. Horizontal dependencies - pass task_graph for sibling access
        if self.config.include_horizontal_dependencies and knowledge_store:
            dep_items = await self._get_dependency_context(node, knowledge_store, task_graph)
            context_items.extend(dep_items)
        
        # 3. Similar completed tasks
        if self.config.include_similar_tasks and knowledge_store:
            similar_items = await self._get_similar_task_context(node, knowledge_store)
            context_items.extend(similar_items)
        
        # 4. Additional context
        if additional_context:
            for key, value in additional_context.items():
                context_items.append(ContextItem(
                    source_task_id=f"additional_{key}",
                    source_task_goal=f"Additional context: {key}",
                    content=str(value),
                    content_type_description="additional_context"
                ))
        
        # Format context
        formatted_context = self._format_context(parent_context, context_items)
        
        # Log what we're building
        if context_items:
            dep_count = sum(1 for item in context_items if item.content_type_description == "dependency_result")
            other_count = len(context_items) - dep_count
            logger.info(
                f"Building context for {node.task_id}: "
                f"{dep_count} dependency results, {other_count} other items"
            )
            # Log dependency details
            for item in context_items:
                if item.content_type_description == "dependency_result":
                    logger.debug(f"  - Dependency from {item.source_task_id}: {item.source_task_goal[:50]}...")
        else:
            logger.info(f"Building context for {node.task_id}: No context items")
        
        logger.debug(f"Formatted context length: {len(formatted_context)}")
        
        # Build final input
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=parent_context,
            relevant_context_items=context_items if context_items else [],
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_planning_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for planning."""
        # Start with default context
        context = await self._build_default_context(node, knowledge_store, task_graph, additional_context)
        
        # Add planning-specific elements
        if knowledge_store:
            # Get successful plans from similar tasks
            similar_plans = await self._get_similar_plans(node, knowledge_store)
            if similar_plans:
                plan_items = [
                    ContextItem(
                        source_task_id=plan["task_id"],
                        source_task_goal=plan["goal"],
                        content=f"Successful plan: {plan['summary']}",
                        content_type_description="similar_plan"
                    )
                    for plan in similar_plans[:3]
                ]
                if context.relevant_context_items:
                    context.relevant_context_items.extend(plan_items)
                else:
                    context.relevant_context_items = plan_items
        
        return context
    
    async def _build_execution_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for execution."""
        # Start with default context
        context = await self._build_default_context(node, knowledge_store, task_graph, additional_context)
        
        # Prioritize recent, relevant results
        if context.relevant_context_items:
            # Sort by relevance and recency
            context.relevant_context_items.sort(
                key=lambda x: (
                    x.content_type_description == "dependency_result",  # Prioritize dependency results
                    x.content_type_description == "prerequisite",
                    x.source_task_id.startswith("recent_")
                ),
                reverse=True
            )
            
            # Limit context size more aggressively for execution
            max_items = 10
            if len(context.relevant_context_items) > max_items:
                context.relevant_context_items = context.relevant_context_items[:max_items]
        
        return context
    
    async def _build_aggregation_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for aggregation."""
        # For aggregation, we primarily need parent context and horizontal dependencies
        # Child results are added separately by the aggregate handler
        context_items = []
        
        # Parent hierarchy is crucial for aggregation
        parent_context = None
        if task_graph:
            parent_context = await self._build_parent_hierarchy(node, task_graph, knowledge_store)
        
        # Horizontal dependencies - pass task_graph for sibling access
        if knowledge_store:
            dep_items = await self._get_dependency_context(node, knowledge_store, task_graph)
            context_items.extend(dep_items)
        
        # Format context
        formatted_context = self._format_context(parent_context, context_items)
        
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type="AGGREGATE",
            parent_hierarchy_context=parent_context,
            relevant_context_items=context_items if context_items else [],
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_atomization_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context optimized for atomization decisions."""
        # Minimal context for atomization
        parent_context = None
        if task_graph and node.parent_node_id:
            parent = task_graph.get_node(node.parent_node_id)
            if parent:
                # Build proper parent chain
                parent_chain = [ParentContextNode(
                    task_id=parent.task_id,
                    goal=parent.goal,
                    layer=parent.layer,
                    task_type=str(parent.task_type)
                )]
                
                # Properly format all required fields
                parent_context = ParentHierarchyContext(
                    current_position=f"Subtask of layer {parent.layer} task: {parent.goal}",
                    parent_chain=parent_chain,
                    formatted_context=f"Parent task: {parent.goal}",
                    priority_level="medium"
                )
        
        formatted_context = ""
        if parent_context:
            formatted_context = parent_context.formatted_context
        
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=parent_context,
            relevant_context_items=[],
            formatted_full_context=formatted_context,
            overall_project_goal=task_graph.overall_project_goal if task_graph else None
        )
    
    async def _build_modification_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"],
        additional_context: Optional[Dict[str, Any]]
    ) -> AgentTaskInput:
        """Build context for plan modification."""
        # Start with planning context
        context = await self._build_planning_context(node, knowledge_store, task_graph, additional_context)
        
        # Add modification-specific data from additional_context
        if additional_context:
            mod_items = []
            
            if "original_plan" in additional_context:
                mod_items.append(ContextItem(
                    source_task_id="original_plan",
                    source_task_goal="Original plan to modify",
                    content=str(additional_context["original_plan"]),
                    content_type_description="original_plan"
                ))
            
            if "modification_instructions" in additional_context:
                mod_items.append(ContextItem(
                    source_task_id="modification_request",
                    source_task_goal="Modification instructions",
                    content=additional_context["modification_instructions"],
                    content_type_description="user_instructions"
                ))
            
            if mod_items:
                if context.relevant_context_items:
                    context.relevant_context_items = mod_items + context.relevant_context_items
                else:
                    context.relevant_context_items = mod_items
        
        return context
    
    async def _build_parent_hierarchy(
        self,
        node: TaskNode,
        task_graph: "TaskGraph",
        knowledge_store: "KnowledgeStore"
    ) -> Optional[ParentHierarchyContext]:
        """Build parent hierarchy context."""
        if not node.parent_node_id:
            return None
        
        parent = task_graph.get_node(node.parent_node_id)
        if not parent:
            return None
        
        # Get parent's context recursively (limited depth)
        hierarchy_parts = []
        current = parent
        depth = 0
        max_depth = 3
        
        while current and depth < max_depth:
            summary = current.output_summary or current.goal
            hierarchy_parts.append(f"L{current.layer}: {summary}")
            
            if current.parent_node_id:
                current = task_graph.get_node(current.parent_node_id)
                depth += 1
            else:
                break
        
        # Format hierarchy
        hierarchy_parts.reverse()
        formatted = "\n".join(hierarchy_parts)
        
        # Build parent chain
        parent_chain = []
        for i, part in enumerate(hierarchy_parts):
            # Extract layer and goal from formatted string
            if part.startswith("L"):
                layer_str, goal = part.split(": ", 1)
                layer = int(layer_str[1:])
                parent_chain.append(ParentContextNode(
                    task_id=f"parent_{i}",  # We don't have the actual IDs here
                    goal=goal,
                    layer=layer,
                    task_type="UNKNOWN"  # We don't have this info here
                ))
        
        # Determine current position
        current_position = f"Layer {node.layer} task under: {parent.goal}"
        
        return ParentHierarchyContext(
            current_position=current_position,
            parent_chain=parent_chain,
            formatted_context=formatted,
            priority_level="medium"  # Could be determined by logic
        )
    
    async def _get_dependency_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore",
        task_graph: Optional["TaskGraph"] = None
    ) -> List[ContextItem]:
        """Get context from dependencies."""
        logger.info(f"Getting dependency context for node {node.task_id}")
        logger.info(f"Node aux_data: {node.aux_data}")
        logger.info(f"Task graph provided: {task_graph is not None}")
        
        context_items = []
        dependency_ids = set()
        
        # Method 1: Get dependencies from aux_data
        depends_on_indices = node.aux_data.get('depends_on_indices', []) if node.aux_data is not None else []
        logger.info(f"Node {node.task_id} has depends_on_indices: {depends_on_indices}")
        if depends_on_indices and node.parent_node_id:
            # First try to get from task_graph (more reliable for newly created nodes)
            if task_graph:
                parent_node = task_graph.get_node(node.parent_node_id)
                if parent_node and parent_node.planned_sub_task_ids:
                    logger.info(f"Parent node {parent_node.task_id} has planned_sub_task_ids: {parent_node.planned_sub_task_ids}")
                    for dep_idx in depends_on_indices:
                        if 0 <= dep_idx < len(parent_node.planned_sub_task_ids):
                            dep_task_id = parent_node.planned_sub_task_ids[dep_idx]
                            dependency_ids.add(dep_task_id)
                            logger.info(f"Resolved dependency index {dep_idx} to task_id {dep_task_id}")
            else:
                # Fallback to knowledge store
                parent_record = knowledge_store.get_record_by_task_id(node.parent_node_id)
                if parent_record and hasattr(parent_record, 'planned_sub_task_ids'):
                    for dep_idx in depends_on_indices:
                        if 0 <= dep_idx < len(parent_record.planned_sub_task_ids):
                            dep_task_id = parent_record.planned_sub_task_ids[dep_idx]
                            dependency_ids.add(dep_task_id)
        
        # Method 2: Check for explicit dependency IDs in aux_data
        if node.aux_data is not None and 'dependency_ids' in node.aux_data:
            dependency_ids.update(node.aux_data['dependency_ids'])
        
        # Method 3: Look for sibling nodes that this task might depend on
        # This is a heuristic - if the node goal mentions results from other tasks
        if node.parent_node_id:
            parent_record = knowledge_store.get_record_by_task_id(node.parent_node_id)
            if parent_record and hasattr(parent_record, 'planned_sub_task_ids'):
                # Check all sibling tasks that completed before this one
                for sibling_id in parent_record.planned_sub_task_ids:
                    if sibling_id != node.task_id:
                        sibling_record = knowledge_store.get_record_by_task_id(sibling_id)
                        if sibling_record and sibling_record.status == "DONE":
                            # Check if this node's goal references the sibling
                            if any(keyword in node.goal.lower() for keyword in ['based on', 'using', 'from', 'analyze the', 'synthesize']):
                                dependency_ids.add(sibling_id)
        
        # Now retrieve context for all identified dependencies
        logger.info(f"Node {node.task_id} has {len(dependency_ids)} dependencies: {dependency_ids}")
        
        for dep_task_id in dependency_ids:
            dep_record = knowledge_store.get_record_by_task_id(dep_task_id)
            logger.info(f"Checking dependency {dep_task_id}: found={dep_record is not None}, status={getattr(dep_record, 'status', 'NO_STATUS') if dep_record else None}, has output_content={hasattr(dep_record, 'output_content') if dep_record else False}")
            
            if dep_record and dep_record.status == "DONE":
                # Get the actual result - check different possible fields
                result_content = None
                if hasattr(dep_record, 'result') and dep_record.result:
                    result_content = dep_record.result
                elif hasattr(dep_record, 'output_content') and dep_record.output_content:
                    result_content = dep_record.output_content
                elif hasattr(dep_record, 'output_summary') and dep_record.output_summary:
                    result_content = dep_record.output_summary
                elif hasattr(dep_record, 'aux_data') and dep_record.aux_data is not None and dep_record.aux_data.get('full_result'):
                    result_content = dep_record.aux_data['full_result']
                
                if result_content:
                    # Create context item from dependency result
                    context_item = ContextItem(
                        content=result_content,
                        source_task_id=dep_task_id,
                        source_task_goal=dep_record.goal,
                        content_type_description="dependency_result",
                        relevance_score=1.0  # Dependencies are highly relevant
                    )
                    context_items.append(context_item)
                    logger.info(f"Added dependency context from {dep_task_id} for node {node.task_id}")
                else:
                    logger.warning(f"Dependency {dep_task_id} is DONE but has no result content")
        
        if not context_items and dependency_ids:
            logger.warning(f"Node {node.task_id} has dependencies {dependency_ids} but no context items were created")
        elif not context_items and depends_on_indices:
            logger.warning(f"Node {node.task_id} has depends_on_indices {depends_on_indices} but no dependencies were resolved")
        elif not context_items:
            logger.info(f"Node {node.task_id} has no dependencies to include in context")
        
        return context_items
    
    async def _get_similar_task_context(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore"
    ) -> List[ContextItem]:
        """Get context from similar completed tasks."""
        # In real implementation, would use semantic search
        # to find similar completed tasks
        return []
    
    async def _get_similar_plans(
        self,
        node: TaskNode,
        knowledge_store: "KnowledgeStore"
    ) -> List[Dict[str, Any]]:
        """Get successful plans from similar tasks."""
        # In real implementation, would search for similar
        # tasks that were successfully planned
        return []
    
    def _format_context(
        self,
        parent_context: Optional[ParentHierarchyContext],
        context_items: List[ContextItem]
    ) -> str:
        """Format context into a string using unified formatter."""
        # Use unified formatter for consistent presentation
        return ContextFormatter.format_context(
            context_items=context_items,
            format_type=ContextFormat.EXECUTION
        )
    
    
    def _build_minimal_context(self, node: TaskNode) -> AgentTaskInput:
        """Build minimal context as fallback."""
        logger.warning(f"Using minimal context fallback for node {node.task_id}")
        return AgentTaskInput(
            current_task_id=node.task_id,
            current_goal=node.goal,
            current_task_type=str(node.task_type),
            parent_hierarchy_context=None,
            relevant_context_items=[],
            formatted_full_context="",  # Empty to avoid duplication
            overall_project_goal=None
        )
    
    def _update_average_size(self, size: int):
        """Update average context size metric."""
        current_avg = self._metrics["average_context_size"]
        total_built = self._metrics["contexts_built"]
        
        self._metrics["average_context_size"] = (
            (current_avg * (total_built - 1) + size) / total_built
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get context building metrics."""
        return self._metrics.copy()
    
    def update_config(self, new_config: ContextConfig):
        """Update context building configuration."""
        self.config = new_config
        logger.info("ContextBuilderService config updated")