from typing import Optional, Callable, Any, Dict, TYPE_CHECKING
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType, NodeType, TaskStatus
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import AtomizerOutput, AgentTaskInput
# No longer importing get_agent_adapter from registry
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import resolve_context_for_agent
from sentientresearchagent.hierarchical_agent_framework.agents.utils import get_context_summary
from .hitl_coordinator import HITLCoordinator
# Corrected import: 'apply_blueprint_to_node' is in 'registry_integration', not 'inode_handler'
from .inode_handler import ProcessorContext
from ..agent_configs.registry_integration import apply_blueprint_to_node
# TraceManager is now accessed via ProcessorContext instead of global singleton

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph

class NodeAtomizer:
    """
    Responsible for determining if a node's goal is atomic using an Atomizer agent
    and handling associated HITL interactions.
    """
    def __init__(self, 
                 hitl_coordinator: HITLCoordinator): 
        self.hitl_coordinator = hitl_coordinator 

    async def atomize_node(
        self, node: TaskNode, context: ProcessorContext 
    ) -> Optional[NodeType]:
        """
        Calls the Atomizer agent to determine if the node's goal is atomic.
        Returns the NodeType to proceed with (PLAN or EXECUTE), or None if HITL caused an abort/error.
        
        NOTE: The atomizer may suggest a refined goal, but we do NOT modify the original
        node's goal to preserve the planner's intent and avoid convergence of similar goals.
        """
        logger.info(f"    🐛 DEBUG: atomize_node called for {node.task_id}")
        
        # NEW: Check if atomization should be skipped entirely
        skip_atomization = getattr(context.config, 'skip_atomization', False)
        logger.info(f"    🐛 DEBUG: skip_atomization = {skip_atomization}, context.config type = {type(context.config)}")
        if skip_atomization:
            logger.info(f"🚫 ATOMIZATION SKIPPED: Node {node.task_id} - skip_atomization is enabled")
            
            # Use hierarchy/depth-based rules instead
            max_recursion_depth = getattr(context.config, 'max_planning_layer', 5)
            if node.layer >= max_recursion_depth:
                logger.info(f"🎯 DEPTH RULE APPLIED: Node {node.task_id} at layer {node.layer} >= max_depth {max_recursion_depth} - forcing EXECUTE")
                return NodeType.EXECUTE
            else:
                logger.info(f"🎯 DEPTH RULE APPLIED: Node {node.task_id} at layer {node.layer} < max_depth {max_recursion_depth} - defaulting to PLAN")
                return NodeType.PLAN
        
        # Start tracing for atomization stage
        stage = context.trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="atomization",
            agent_name=node.agent_name,
            adapter_name="NodeAtomizer"
        )
        
        knowledge_store: KnowledgeStore = context.knowledge_store
        task_graph: 'TaskGraph' = context.task_graph
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        
        # Preserve the node's agent_name as it was upon entering this atomizer step
        agent_name_at_atomizer_entry = node.agent_name
        logger.info(f"    NodeAtomizer: Atomizing for node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:30]}...', Original Agent Name at Entry: {agent_name_at_atomizer_entry})")

        try:
            logger.info(f"    🐛 DEBUG: Starting atomization process for {node.task_id}")
            
            current_task_type_value = node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type)
            logger.info(f"    🐛 DEBUG: current_task_type_value = {current_task_type_value}")
            
            # Update tracing stage with initial context
            if stage:
                stage.processing_parameters = {
                    "task_type": current_task_type_value,
                    "blueprint": blueprint_name_log,
                    "original_goal": node.goal[:200]
                }
            
            # Determine agent_name for context resolution (less critical, uses a default)
            context_builder_agent_name = agent_name_at_atomizer_entry or "default_atomizer"
            if context.current_agent_blueprint:
                if context.current_agent_blueprint.atomizer_adapter_name:
                    context_builder_agent_name = context.current_agent_blueprint.atomizer_adapter_name
                elif not agent_name_at_atomizer_entry and context.current_agent_blueprint.default_node_agent_name_prefix:
                    context_builder_agent_name = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Atomizer"
            context_builder_agent_name = context_builder_agent_name or "default_atomizer"
            logger.info(f"    🐛 DEBUG: context_builder_agent_name = {context_builder_agent_name}")

            logger.info(f"    🐛 DEBUG: About to resolve context for agent")
            atomizer_input_model = resolve_context_for_agent(
                current_task_id=node.task_id, current_goal=node.goal,
                current_task_type=current_task_type_value, agent_name=context_builder_agent_name, 
                knowledge_store=knowledge_store, overall_project_goal=task_graph.overall_project_goal
            )
            logger.info(f"    🐛 DEBUG: Context resolved successfully")
            
            # Update tracing stage with context info
            if stage:
                stage.input_context = {
                    "context_builder_agent": context_builder_agent_name,
                    "context_items_count": len(atomizer_input_model.relevant_context_items) if hasattr(atomizer_input_model, 'relevant_context_items') else 0,
                    "overall_project_goal": task_graph.overall_project_goal[:200] if task_graph.overall_project_goal else None
                }
            
            # Determine the name to use for looking up the atomizer adapter
            lookup_name_for_atomizer = agent_name_at_atomizer_entry # Start with pre-existing name
            if context.current_agent_blueprint:
                if context.current_agent_blueprint.atomizer_adapter_name:
                    lookup_name_for_atomizer = context.current_agent_blueprint.atomizer_adapter_name
                    logger.debug(f"        NodeAtomizer: Blueprint specifies atomizer: {lookup_name_for_atomizer}")
                elif not lookup_name_for_atomizer and context.current_agent_blueprint.default_node_agent_name_prefix:
                    lookup_name_for_atomizer = f"{context.current_agent_blueprint.default_node_agent_name_prefix}Atomizer"
                    logger.debug(f"        NodeAtomizer: Blueprint suggests prefix for atomizer: {lookup_name_for_atomizer}")
            
            logger.info(f"    🐛 DEBUG: lookup_name_for_atomizer = {lookup_name_for_atomizer}")
            
            node.agent_name = lookup_name_for_atomizer # Temporarily set for get_agent_adapter
            logger.info(f"    🐛 DEBUG: About to call get_agent_adapter with action_verb='atomize'")
            atomizer_adapter = context.agent_registry.get_agent_adapter(node, action_verb="atomize") 
            logger.info(f"    🐛 DEBUG: get_agent_adapter returned: {atomizer_adapter}")

            if not atomizer_adapter and agent_name_at_atomizer_entry and node.agent_name != agent_name_at_atomizer_entry:
                logger.debug(f"        NodeAtomizer: Blueprint atomizer lookup failed. Trying original entry agent_name for atomize: {agent_name_at_atomizer_entry}")
                node.agent_name = agent_name_at_atomizer_entry # Restore and try original
                atomizer_adapter = context.agent_registry.get_agent_adapter(node, action_verb="atomize")
                logger.info(f"    🐛 DEBUG: Retry get_agent_adapter returned: {atomizer_adapter}")

            action_to_take: NodeType
            if atomizer_adapter:
                logger.info(f"    🐛 DEBUG: Found atomizer adapter, proceeding with atomization")
                adapter_used_name = getattr(atomizer_adapter, 'agent_name', type(atomizer_adapter).__name__)
                logger.info(f"    NodeAtomizer: Calling Atomizer adapter '{adapter_used_name}' for node {node.task_id} ('{node.goal[:30]}...')")
                
                # Update tracing stage with atomizer adapter info
                if stage:
                    stage.agent_name = adapter_used_name
                
                logger.info(f"    🐛 DEBUG: About to call atomizer_adapter.process")
                atomizer_output: Optional[AtomizerOutput] = await atomizer_adapter.process(node, atomizer_input_model, context.trace_manager)
                logger.info(f"    🐛 DEBUG: atomizer_adapter.process returned: {atomizer_output}")
                
                if atomizer_output is None:
                    error_msg = "Atomizer returned None, cannot determine next step."
                    logger.warning(f"    NodeAtomizer: Atomizer for {node.task_id} returned None.")
                    
                    # Complete tracing stage with error
                    context.trace_manager.complete_stage(
                        node_id=node.task_id,
                        stage_name="atomization",
                        error=error_msg
                    )
                    
                    if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]: 
                         node.update_status(TaskStatus.FAILED, error_msg=error_msg) 
                    return None

                original_goal_for_hitl = atomizer_input_model.current_goal 
                
                # Log the atomizer's suggestion but DON'T modify the node's goal
                if atomizer_output.updated_goal != node.goal:
                    logger.info(f"    Atomizer suggested goal refinement for {node.task_id}: '{node.goal[:50]}...' -> '{atomizer_output.updated_goal[:50]}...'")
                    logger.debug(f"    NOTE: Preserving original goal to maintain planner's intent")
                
                # Use the atomizer's suggested goal for HITL review, but don't apply it to the node
                suggested_goal_for_hitl = atomizer_output.updated_goal
                
                action_to_take = NodeType.EXECUTE if atomizer_output.is_atomic else NodeType.PLAN
                logger.info(f"    Atomizer determined {node.task_id} as {action_to_take.name}.")
                
                # Update tracing stage with atomizer output
                if stage:
                    stage.output_data = {
                        "is_atomic": atomizer_output.is_atomic,
                        "suggested_goal": suggested_goal_for_hitl[:200],
                        "action_to_take": action_to_take.name,
                        "goal_changed": atomizer_output.updated_goal != node.goal
                    }
                
                # COMPREHENSIVE DEBUG: Log HITL decision factors before calling
                logger.debug(f"🐛 ATOMIZER DEBUG: About to call HITL review for {node.task_id}")
                logger.debug(f"🐛 ATOMIZER DEBUG: Node layer = {node.layer}")
                logger.debug(f"🐛 ATOMIZER DEBUG: HITL coordinator config = {self.hitl_coordinator.config}")
                logger.debug(f"🐛 ATOMIZER DEBUG: hitl_root_plan_only = {getattr(self.hitl_coordinator.config, 'hitl_root_plan_only', 'NOT_SET')}")
                logger.debug(f"🐛 ATOMIZER DEBUG: enable_hitl_after_atomizer = {self.hitl_coordinator.config.enable_hitl_after_atomizer}")
                
                logger.info(f"    🐛 DEBUG: About to call HITL review")

                hitl_outcome_atomizer = await self.hitl_coordinator.review_atomizer_output(
                    node=node, original_goal=original_goal_for_hitl,
                    updated_goal=suggested_goal_for_hitl,
                    is_atomic=atomizer_output.is_atomic, 
                    proposed_next_action=action_to_take.value, 
                    context_items=atomizer_input_model.relevant_context_items  # Pass items, not summary
                )
                logger.info(f"    🐛 DEBUG: HITL review returned: {hitl_outcome_atomizer}")
                
                if hitl_outcome_atomizer.get("status") != "approved": 
                    logger.info(f"NodeAtomizer: HITL review for atomizer output of {node.task_id} was not 'approved'. Status is {node.status}. HITL outcome: {hitl_outcome_atomizer}")
                    
                    # Complete tracing stage with HITL rejection
                    context.trace_manager.complete_stage(
                        node_id=node.task_id,
                        stage_name="atomization",
                        error=f"HITL rejected atomizer output: {hitl_outcome_atomizer.get('status', 'unknown')}"
                    )
                    return None 
                
                # Complete tracing stage successfully
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="atomization",
                    output_data=f"Determined as {action_to_take.name}, is_atomic: {atomizer_output.is_atomic}"
                )
                
                logger.info(f"    🐛 DEBUG: Returning action_to_take: {action_to_take}")
                return action_to_take 
            
            else: # No atomizer_adapter found
                final_tried_name = node.agent_name or lookup_name_for_atomizer or agent_name_at_atomizer_entry
                logger.warning(f"    NodeAtomizer: No AtomizerAdapter found for node {node.task_id} (tried: {final_tried_name or 'None'}). Defaulting its NodeType based on current value or to EXECUTE.")
                logger.info(f"    🐛 DEBUG: No atomizer adapter found, using fallback logic")
                
                result = None
                if isinstance(node.node_type, str):
                    try: 
                        result = NodeType(node.node_type)
                        logger.info(f"    🐛 DEBUG: Fallback returning NodeType from string: {result}")
                    except ValueError: 
                        result = NodeType.EXECUTE
                        logger.info(f"    🐛 DEBUG: Fallback returning NodeType.EXECUTE for invalid string format")
                elif isinstance(node.node_type, NodeType): 
                    result = node.node_type 
                else: 
                    result = NodeType.EXECUTE
                
                # Complete tracing stage with fallback result
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="atomization",
                    output_data=f"No atomizer found, fallback to {result.name}"
                )
                
                return result
                
            # 🚨 CRITICAL FIX: SEARCH nodes should NEVER be atomized as PLAN nodes
            if hasattr(node, 'task_type') and node.task_type and str(node.task_type).upper() == 'SEARCH':
                logger.info(f"🚨 SEARCH NODE OVERRIDE: Node {node.task_id} is SEARCH type - forcing EXECUTE to prevent incorrect planning/aggregation")
                
                # Complete tracing stage  
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="atomization",
                    output_data="SEARCH node forced to EXECUTE (skipped atomizer)"
                )
                
                return NodeType.EXECUTE
                
        except Exception as e:
            # Complete tracing stage with error
            context.trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="atomization",
                error=str(e)
            )
            raise
            
        finally:
            # Restore node.agent_name to what it was when this function was entered.
            # The atomizer's specific name should not persist on the node object for subsequent unrelated steps.
            if node.agent_name != agent_name_at_atomizer_entry:
                logger.debug(f"        NodeAtomizer: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_atomizer_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_atomizer_entry