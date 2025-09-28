"""
PlanHandler - Handles nodes that need planning.

This simplified handler focuses solely on planning logic,
delegating common functionality to BaseNodeHandler.
"""

from typing import Any, Optional
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import PlanOutput
from .base_handler import BaseNodeHandler, HandlerContext


class PlanHandler(BaseNodeHandler):
    """
    Handles nodes that need to be planned.
    
    This handler is responsible for:
    - Getting a planner agent
    - Building planning context
    - Executing the planner
    - Creating sub-nodes from the plan
    - Handling HITL review
    """
    
    def __init__(self):
        super().__init__("PlanHandler")
    
    def _validate_node_state(self, node: TaskNode) -> bool:
        """Validate node is ready for planning."""
        # Node should be READY and of PLAN type
        return (
            node.status == TaskStatus.READY and
            node.node_type == NodeType.PLAN
        )
    
    def _get_stage_name(self) -> str:
        """Get tracing stage name."""
        return "planning"
    
    async def _process(self, node: TaskNode, context: HandlerContext) -> PlanOutput:
        """
        Main planning logic.
        
        Args:
            node: Node to plan
            context: Handler context
            
        Returns:
            Plan output
        """
        # Check if we're at max recursion depth
        max_recursion_depth = context.config.get("execution", {}).get("max_recursion_depth", 5)
        if node.layer >= max_recursion_depth:
            logger.warning(
                f"Node {node.task_id} at layer {node.layer} is at or exceeds "
                f"max recursion depth {max_recursion_depth} - should not be planning!"
            )
            # Force to execute instead
            node.node_type = NodeType.EXECUTE
            node.update_status(TaskStatus.READY, validate_transition=True)
            return None
        
        # Get planner agent
        planner = await self._get_agent_for_node(node, context, "plan")
        if not planner:
            raise ValueError(f"No planner available for node {node.task_id}")
        
        # Build planning context
        planning_context = await self._build_context_for_node(
            node, 
            context, 
            context_type="planning"
        )
        
        # Store input for tracing
        node.input_payload_dict = planning_context.model_dump()
        
        # Execute planner
        logger.info(f"Executing planner for node {node.task_id}")
        plan_output = await planner.process(node, planning_context, context.trace_manager)
        
        # Validate plan output
        if not plan_output or not hasattr(plan_output, 'sub_tasks'):
            raise ValueError("Planner returned invalid output")
        
        # Handle empty plan
        if not plan_output.sub_tasks:
            logger.info(f"Planner returned empty plan for {node.task_id} - will create empty sub-graph")
            return plan_output
        
        # HITL review if available
        if context.hitl_service:
            review_result = await self._review_plan(node, plan_output, context)
            
            if review_result["status"] == "approved":
                # Create sub-nodes
                await self._create_sub_nodes(node, plan_output, context)
                return plan_output
            
            elif review_result["status"] == "request_modification":
                # Set up for modification
                await self._setup_modification(node, plan_output, review_result, context)
                return None  # Will be handled by replan
            
            else:
                # Rejected or cancelled
                raise ValueError(f"Plan not approved: {review_result['status']}")
        else:
            # No HITL - directly create sub-nodes
            await self._create_sub_nodes(node, plan_output, context)
            return plan_output
    
    async def _review_plan(
        self, 
        node: TaskNode, 
        plan_output: PlanOutput, 
        context: HandlerContext
    ) -> dict:
        """Review plan with HITL if enabled."""
        return await context.hitl_service.review_plan(
            node=node,
            plan_output=plan_output,
            planning_context=node.input_payload_dict
        )
    
    async def _create_sub_nodes(
        self, 
        node: TaskNode, 
        plan_output: PlanOutput, 
        context: HandlerContext
    ):
        """Create sub-nodes from the plan."""
        # Import SubNodeCreator locally to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.node.node_creation_utils import SubNodeCreator
        
        # Get task_graph from somewhere - need to add it to context or find another way
        # For now, we'll create sub-nodes manually since we don't have direct access to task_graph
        
        logger.info(f"Creating {len(plan_output.sub_tasks)} sub-nodes for {node.task_id}")
        
        # Store plan output in node
        node.result = plan_output
        node.aux_data['full_result'] = plan_output
        
        # Generate summary
        if plan_output and hasattr(plan_output, 'sub_tasks') and plan_output.sub_tasks:
            task_summaries = []
            for i, sub_task in enumerate(plan_output.sub_tasks[:3]):  # First 3 tasks
                task_summaries.append(f"{i+1}. {sub_task.goal[:50]}...")
            if len(plan_output.sub_tasks) > 3:
                task_summaries.append(f"... and {len(plan_output.sub_tasks) - 3} more tasks")
            node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks: " + "; ".join(task_summaries)
        else:
            node.output_summary = "Planning completed successfully"
        
        # Update node status to PLAN_DONE
        node.update_status(TaskStatus.PLAN_DONE, validate_transition=True)
        
        # Note: Actual sub-node creation needs to be handled by the system that has access to task_graph
        # This is a limitation of the v2 architecture where handlers don't have direct access to task_graph
    
    async def _setup_modification(
        self, 
        node: TaskNode, 
        plan_output: PlanOutput, 
        review_result: dict,
        context: HandlerContext
    ):
        """Set up node for plan modification."""
        modification_instructions = review_result.get('modification_instructions', '')
        
        # Store data for replan
        node.aux_data['original_plan_for_modification'] = plan_output
        node.aux_data['user_modification_instructions'] = modification_instructions
        node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
        
        # Transition to NEEDS_REPLAN
        await context.state_manager.transition_node(
            node,
            TaskStatus.NEEDS_REPLAN,
            reason="User requested plan modification"
        )
    
    async def _post_process(
        self, 
        node: TaskNode, 
        context: HandlerContext, 
        result: PlanOutput
    ):
        """Post-process planning result."""
        if result and result.sub_tasks:
            # Successful planning
            await self._handle_agent_result(
                node,
                result,
                context,
                success_status=TaskStatus.PLAN_DONE
            )
        else:
            # Empty plan or modification requested
            if node.status != TaskStatus.NEEDS_REPLAN:
                # Create empty sub-graph for aggregation to work
                empty_graph_id = f"{node.task_id}_empty_graph"
                context.task_graph.add_graph(empty_graph_id)
                node.sub_graph_id = empty_graph_id
                
                # Keep as PLAN node so it can aggregate
                await context.state_manager.transition_node(
                    node,
                    TaskStatus.PLAN_DONE,
                    reason="Empty plan - no subtasks to execute"
                )
        
        # Call parent post-process
        await super()._post_process(node, context, result)