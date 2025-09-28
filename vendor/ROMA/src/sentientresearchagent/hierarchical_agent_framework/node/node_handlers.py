from typing import Optional, Any, cast
from datetime import datetime
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.agent_io_models import (
    AgentTaskInput, PlanOutput, ReplanRequestDetails, CustomSearcherOutput, PlanModifierInput, ContextItem
)
from sentientresearchagent.hierarchical_agent_framework.context.context_builder import (
    resolve_context_for_agent,
)
from sentientresearchagent.hierarchical_agent_framework.context.planner_context_builder import resolve_input_for_planner_agent
from pydantic import BaseModel

from .inode_handler import INodeHandler, ProcessorContext
from ..context.enhanced_context_builder import resolve_context_for_agent_with_parents
from ..context.smart_context_utils import get_smart_child_context
from ..agents.utils import get_context_summary, TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
from .dependency_utils import DependencyChainTracker
# TraceManager is now accessed via ProcessorContext instead of global singleton


def get_planner_from_blueprint(blueprint: 'AgentBlueprint', task_type: TaskType, fallback_name: Optional[str] = None, node: Optional[TaskNode] = None) -> Optional[str]:
    """
    Get the appropriate planner name from blueprint based on task type and node level.
    
    Args:
        blueprint: The agent blueprint
        task_type: The task type needing planning
        fallback_name: Fallback agent name if blueprint doesn't specify
        node: The TaskNode (needed to determine if it's root)
        
    Returns:
        Agent name to use for planning, or None if no suitable planner found
    """
    if not blueprint:
        return fallback_name
    
    # NEW: Check if this is the root node and if blueprint has root planner
    if node:
        is_root_node = (
            node.task_id == "root" or 
            getattr(node, 'layer', 0) == 0 or
            getattr(node, 'parent_node_id', None) is None
        )
        
        if is_root_node and hasattr(blueprint, 'root_planner_adapter_name') and blueprint.root_planner_adapter_name:
            planner_name = blueprint.root_planner_adapter_name
            logger.info(f"🎯 Using ROOT planner for root node {node.task_id}: {planner_name}")
            return planner_name
        else:
            logger.info(f"📋 Using task-specific planner for non-root node {node.task_id} (layer: {getattr(node, 'layer', 'unknown')}, parent: {getattr(node, 'parent_node_id', 'unknown')})")
    
    # 1. Try task-specific planner
    if hasattr(blueprint, 'planner_adapter_names') and task_type in blueprint.planner_adapter_names:
        planner_name = blueprint.planner_adapter_names[task_type]
        logger.debug(f"Blueprint specifies planner for {task_type}: {planner_name}")
        return planner_name
    
    # 2. Try default planner
    if hasattr(blueprint, 'default_planner_adapter_name') and blueprint.default_planner_adapter_name:
        planner_name = blueprint.default_planner_adapter_name
        logger.debug(f"Blueprint specifies default planner: {planner_name}")
        return planner_name
    
    # 3. Try legacy single planner (backward compatibility)
    if hasattr(blueprint, 'planner_adapter_name') and blueprint.planner_adapter_name:
        planner_name = blueprint.planner_adapter_name
        logger.debug(f"Blueprint specifies legacy single planner: {planner_name}")
        return planner_name
    
    # 4. Try prefix-based naming
    if hasattr(blueprint, 'default_node_agent_name_prefix') and blueprint.default_node_agent_name_prefix:
        planner_name = f"{blueprint.default_node_agent_name_prefix}Planner"
        logger.debug(f"Blueprint suggests prefix-based planner: {planner_name}")
        return planner_name
    
    return fallback_name


def get_executor_from_blueprint(blueprint: 'AgentBlueprint', task_type: TaskType, fallback_name: Optional[str] = None) -> Optional[str]:
    """
    Get the appropriate executor name from blueprint based on task type.
    
    Args:
        blueprint: The agent blueprint
        task_type: The task type needing execution
        fallback_name: Fallback agent name if blueprint doesn't specify
        
    Returns:
        Agent name to use for execution, or None if no suitable executor found
    """
    if not blueprint:
        return fallback_name
    
    # 1. Try task-specific executor
    if hasattr(blueprint, 'executor_adapter_names') and task_type in blueprint.executor_adapter_names:
        executor_name = blueprint.executor_adapter_names[task_type]
        logger.debug(f"Blueprint specifies executor for {task_type}: {executor_name}")
        return executor_name
    
    # 2. Try default executor
    if hasattr(blueprint, 'default_executor_adapter_name') and blueprint.default_executor_adapter_name:
        executor_name = blueprint.default_executor_adapter_name
        logger.debug(f"Blueprint specifies default executor: {executor_name}")
        return executor_name
    
    # 3. Try prefix-based naming
    if hasattr(blueprint, 'default_node_agent_name_prefix') and blueprint.default_node_agent_name_prefix:
        executor_name = f"{blueprint.default_node_agent_name_prefix}Executor"
        logger.debug(f"Blueprint suggests prefix-based executor: {executor_name}")
        return executor_name
    
    return fallback_name


def get_aggregator_from_blueprint(blueprint: 'AgentBlueprint', task_type: TaskType, fallback_name: Optional[str] = None, node: Optional['TaskNode'] = None) -> Optional[str]:
    """
    Get the appropriate aggregator name from blueprint based on task type and node context.
    
    Args:
        blueprint: The agent blueprint
        task_type: The task type needing aggregation
        fallback_name: Fallback agent name if blueprint doesn't specify
        node: The task node being aggregated (used to detect root nodes)
        
    Returns:
        Agent name to use for aggregation, or None if no suitable aggregator found
    """
    if not blueprint:
        return fallback_name
    
    # 1. Check if this is a root node and blueprint has root-specific aggregator
    if node:
        is_root_node = (
            node.task_id == "root" or 
            getattr(node, 'layer', 0) == 0 or
            getattr(node, 'parent_node_id', None) is None
        )
        
        logger.debug(f"🔍 AGGREGATOR SELECTION DEBUG for node {node.task_id}:")
        logger.debug(f"  - task_id: {node.task_id}")
        logger.debug(f"  - layer: {getattr(node, 'layer', 'N/A')}")
        logger.debug(f"  - parent_node_id: {getattr(node, 'parent_node_id', 'N/A')}")
        logger.debug(f"  - is_root_node: {is_root_node}")
        logger.debug(f"  - task_type: {task_type}")
        logger.debug(f"  - blueprint has root_aggregator_adapter_name: {hasattr(blueprint, 'root_aggregator_adapter_name')}")
        if hasattr(blueprint, 'root_aggregator_adapter_name'):
            logger.debug(f"  - root_aggregator_adapter_name value: {blueprint.root_aggregator_adapter_name}")
        
        if is_root_node and hasattr(blueprint, 'root_aggregator_adapter_name') and blueprint.root_aggregator_adapter_name:
            aggregator_name = blueprint.root_aggregator_adapter_name
            logger.info(f"🎯 Blueprint specifies ROOT aggregator for root node {node.task_id}: {aggregator_name}")
            return aggregator_name
    
    # 2. Try task-specific aggregator
    if hasattr(blueprint, 'aggregator_adapter_names') and task_type in blueprint.aggregator_adapter_names:
        aggregator_name = blueprint.aggregator_adapter_names[task_type]
        logger.debug(f"Blueprint specifies aggregator for {task_type}: {aggregator_name}")
        return aggregator_name
    
    # 3. Try default single aggregator
    if hasattr(blueprint, 'aggregator_adapter_name') and blueprint.aggregator_adapter_name:
        aggregator_name = blueprint.aggregator_adapter_name
        logger.debug(f"Blueprint specifies default aggregator: {aggregator_name}")
        return aggregator_name
    
    # 4. Try prefix-based naming
    if hasattr(blueprint, 'default_node_agent_name_prefix') and blueprint.default_node_agent_name_prefix:
        aggregator_name = f"{blueprint.default_node_agent_name_prefix}Aggregator"
        logger.debug(f"Blueprint suggests prefix-based aggregator: {aggregator_name}")
        return aggregator_name
    
    return fallback_name


class ReadyPlanHandler(INodeHandler):
    """Handles a READY node that needs to be PLANNED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"    ReadyPlanHandler: Planning for node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:50]}...', Original Agent Name at Entry: {agent_name_at_entry})")
        
        # Start tracing for planning stage
        stage = context.trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="planning",
            agent_name=agent_name_at_entry,
            adapter_name="ReadyPlanHandler"
        )
        
        try:
            current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            # ENHANCED: Use new blueprint system for planner selection with node parameter
            lookup_name_for_planner = get_planner_from_blueprint(
                context.current_agent_blueprint, 
                node.task_type, 
                agent_name_at_entry,
                node  # NEW: Pass the node so we can check if it's root
            )

            # Validate that we're not using an aggregator for planning
            if lookup_name_for_planner and 'aggregator' in lookup_name_for_planner.lower():
                logger.error(
                    f"🚨 CRITICAL: Attempted to use aggregator '{lookup_name_for_planner}' "
                    f"for planning node {node.task_id}. This is incorrect!"
                )
                # Clear the bad agent name and try to find a proper planner
                lookup_name_for_planner = None
                if context.current_agent_blueprint:
                    # Try to get the correct planner from blueprint
                    lookup_name_for_planner = get_planner_from_blueprint(
                        context.current_agent_blueprint,
                        node.task_type,
                        None,  # Don't use the aggregator as fallback
                        node
                    )

            node.agent_name = lookup_name_for_planner 
            planner_adapter = context.agent_registry.get_agent_adapter(node, action_verb="plan")

            if not planner_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyPlanHandler: Blueprint planner lookup failed. Trying original entry agent_name for plan: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                planner_adapter = context.agent_registry.get_agent_adapter(node, action_verb="plan")
            
            if not planner_adapter:
                final_tried_name = node.agent_name or lookup_name_for_planner or agent_name_at_entry
                error_msg = f"No PLAN adapter found for node {node.task_id} (TaskType: {node.task_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                
                # Complete tracing stage with error
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="planning",
                    error=error_msg
                )
                
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(planner_adapter, 'agent_name', type(planner_adapter).__name__)
            logger.info(f"    ReadyPlanHandler: Using PLAN adapter '{adapter_used_name}' for node {node.task_id}")

            # ENHANCED: Use blueprint for context builder agent selection too
            context_builder_agent_name = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry
            )
            
            agent_task_input_model = resolve_context_for_agent_with_parents(
                current_task_id=node.task_id,
                current_goal=node.goal,
                current_task_type=node.task_type.value,
                knowledge_store=context.knowledge_store,
                agent_name=context_builder_agent_name,
                overall_project_goal=context.task_graph.overall_project_goal
            )
            formatted_context = agent_task_input_model.formatted_full_context
            node.input_payload_dict = agent_task_input_model.model_dump()
            
            # Update tracing stage with input context (MOVED HERE - after formatted_context is defined)
            if stage:
                stage.input_context = {
                    "formatted_context_length": len(formatted_context) if formatted_context else 0,
                    "context_items_count": len(agent_task_input_model.context_items) if hasattr(agent_task_input_model, 'context_items') else 0,
                    "overall_project_goal": context.task_graph.overall_project_goal[:200] if context.task_graph.overall_project_goal else None
                }
            
            plan_output: Optional[PlanOutput] = await planner_adapter.process(node, agent_task_input_model, context.trace_manager)

            if plan_output is None or not plan_output.sub_tasks:
                if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                    logger.warning(f"    Node {node.task_id} (PLAN): Planner returned no sub-tasks or None.")
                    if plan_output is None:
                        error_msg = "Planner failed to produce an output."
                        context.trace_manager.complete_stage(
                            node_id=node.task_id,
                            stage_name="planning",
                            error=error_msg
                        )
                        node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                    else: 
                        logger.info(f"    Node {node.task_id} (PLAN): Planner returned an empty list. Interpreting as atomic.")
                        node.node_type = NodeType.EXECUTE
                        node.output_summary = "Planner determined no further sub-tasks are needed; task is atomic."
                        node.update_status(TaskStatus.PLAN_DONE)
                        
                        # Complete tracing stage successfully
                        context.trace_manager.complete_stage(
                            node_id=node.task_id,
                            stage_name="planning",
                            output_data="Task determined to be atomic"
                        )
                return

            hitl_outcome_plan = await context.hitl_coordinator.review_plan_generation(
                node=node, plan_output=plan_output, planner_input=agent_task_input_model
            )
            if hitl_outcome_plan["status"] == "request_modification":
                # User requested modification - set up node for replan
                modification_instructions = hitl_outcome_plan.get('modification_instructions', 'User requested modification.')
                
                # Set up auxiliary data for the modification
                node.aux_data['original_plan_for_modification'] = plan_output
                node.aux_data['user_modification_instructions'] = modification_instructions
                node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
                
                # Transition to NEEDS_REPLAN status
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.output_summary = "Plan requires user modification."
                
                # Update knowledge store to persist the status change
                context.knowledge_store.add_or_update_record_from_node(node)
                
                # Complete tracing stage with modification request
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="planning",
                    output_data=f"User requested modification: {modification_instructions[:200]}"
                )
                
                logger.info(f"✅ Node {node.task_id} set up for modification and transitioned to NEEDS_REPLAN")
                return
            
            elif hitl_outcome_plan["status"] != "approved":
                # Handle non-approved HITL outcomes (aborted, error, etc.)
                status = hitl_outcome_plan["status"]
                if status == "aborted":
                    logger.info(f"ReadyPlanHandler: Node {node.task_id} planning aborted by user")
                elif status == "error":
                    logger.info(f"ReadyPlanHandler: Node {node.task_id} planning failed due to HITL error")
                else:
                    logger.warning(f"ReadyPlanHandler: Node {node.task_id} planning not approved: {status}")
                # HITLCoordinator already set appropriate status, just return
                return
            
            # HITL approved - continue with plan implementation
            logger.info(f"✅ ReadyPlanHandler: Plan approved for node {node.task_id}, creating {len(plan_output.sub_tasks)} sub-tasks")
            
            # Create sub-nodes from the approved plan
            context.sub_node_creator.create_sub_nodes(node, plan_output)
            
            # Store the plan result and update status
            node.result = plan_output
            
            # CRITICAL FIX: Store full result in aux_data for consistency
            node.aux_data['full_result'] = plan_output
            
            # Generate meaningful summary instead of generic one
            try:
                if plan_output and hasattr(plan_output, 'sub_tasks') and plan_output.sub_tasks:
                    # Create a summary that includes the actual sub-task goals
                    subtask_goals = [subtask.goal for subtask in plan_output.sub_tasks[:3]]  # Take first 3 goals
                    goals_preview = '; '.join(subtask_goals)
                    if len(plan_output.sub_tasks) > 3:
                        goals_preview += f" (and {len(plan_output.sub_tasks) - 3} more tasks)"
                    node.output_summary = f"Planned {len(plan_output.sub_tasks)} sub-tasks: {goals_preview}"
                else:
                    node.output_summary = f"Generated plan with {len(plan_output.sub_tasks)} sub-tasks for goal: {node.goal[:100]}..."
            except Exception as e:
                logger.warning(f"Error generating meaningful plan summary for {node.task_id}: {e}")
                node.output_summary = f"Generated plan with {len(plan_output.sub_tasks)} sub-tasks for goal: {node.goal[:100]}..."
            
            # Only update status if not already PLAN_DONE (prevents double transitions)
            if node.status != TaskStatus.PLAN_DONE:
                node.update_status(TaskStatus.PLAN_DONE)
            
            # Trigger update callback after planning completes
            if context.update_callback:
                try:
                    context.update_callback()
                    logger.debug(f"ReadyPlanHandler: Update callback triggered after planning for {node.task_id}")
                except Exception as e:
                    logger.warning(f"ReadyPlanHandler: Update callback failed: {e}")
            
            logger.success(f"✅ ReadyPlanHandler: Node {node.task_id} planning complete. Status: {node.status.name}")
            
            # Complete tracing stage successfully
            sub_task_count = len(plan_output.sub_tasks) if plan_output.sub_tasks else 0
            context.trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="planning",
                output_data=f"Successfully created {sub_task_count} sub-tasks"
            )
            
        except Exception as e:
            # Complete tracing stage with error
            context.trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="planning",
                error=str(e)
            )
            raise

class ReadyExecuteHandler(INodeHandler):
    """Handles a READY node that needs to be EXECUTED."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"    ReadyExecuteHandler: Executing node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:50]}...', Original Agent Name at Entry: {agent_name_at_entry})")

        # CRITICAL FIX: Start execution stage here (base adapter will update it)
        execution_stage = context.trace_manager.start_stage(
            node_id=node.task_id,
            stage_name="execution",
            agent_name=agent_name_at_entry,
            adapter_name="ReadyExecuteHandler"
        )

        try:
            # ENHANCED: Use blueprint for context builder agent selection
            context_builder_agent_name = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry or "default_executor"
            )
            
            agent_task_input_model = resolve_context_for_agent_with_parents(
                current_task_id=node.task_id, 
                current_goal=node.goal,
                current_task_type=node.task_type.value if isinstance(node.task_type, TaskType) else str(node.task_type),
                knowledge_store=context.knowledge_store, 
                agent_name=context_builder_agent_name,
                overall_project_goal=context.task_graph.overall_project_goal
            )
            node.input_payload_dict = agent_task_input_model.model_dump()

            # Update trace with input context
            if execution_stage:
                context.trace_manager.update_stage(
                    node_id=node.task_id,
                    stage_name="execution",
                    input_context=agent_task_input_model.model_dump(),
                    user_input=agent_task_input_model.current_goal
                )

            hitl_outcome_exec = await context.hitl_coordinator.review_before_execution(
                node=node, agent_task_input=agent_task_input_model
            )
            if hitl_outcome_exec["status"] != "approved":
                # Handle non-approved HITL outcomes properly
                status = hitl_outcome_exec["status"]
                error_msg = f"HITL execution not approved: {status}"
                
                # Complete tracing stage with error
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="execution",
                    error=error_msg
                )
                
                if status == "aborted":
                    # Node status already set to CANCELLED by HITLCoordinator
                    logger.info(f"ReadyExecuteHandler: Node {node.task_id} execution aborted by user")
                elif status == "error":
                    # Node status already set to FAILED by HITLCoordinator  
                    logger.info(f"ReadyExecuteHandler: Node {node.task_id} execution failed due to HITL error")
                elif status == "request_modification":
                    # For execution stage, modification requests should be treated as failed
                    # since we can't modify execution like we can modify plans
                    if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        node.update_status(TaskStatus.FAILED, error_msg="User requested modification for execution, but execution cannot be modified")
                else:
                    # Unknown status - fail safe
                    if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        node.update_status(TaskStatus.FAILED, error_msg=f"Unknown HITL outcome status: {status}")
                return

            # ENHANCED: Use new blueprint system for executor selection
            lookup_name_for_executor = get_executor_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry
            )

            node.agent_name = lookup_name_for_executor 
            executor_adapter = context.agent_registry.get_agent_adapter(node, action_verb="execute")

            if not executor_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyExecuteHandler: Blueprint executor lookup failed for {node.task_type}. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                executor_adapter = context.agent_registry.get_agent_adapter(node, action_verb="execute")

            if not executor_adapter:
                final_tried_name = node.agent_name or lookup_name_for_executor or agent_name_at_entry
                error_msg = f"No EXECUTE adapter found for node {node.task_id} (TaskType: {node.task_type}, NodeType: {node.node_type}, Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                
                # Complete tracing stage with error
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="execution",
                    error=error_msg
                )
                
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return
            
            adapter_used_name = getattr(executor_adapter, 'agent_name', type(executor_adapter).__name__)
            logger.info(f"    ReadyExecuteHandler: Using EXECUTE adapter '{adapter_used_name}' for node {node.task_id}")

            # Update trace with adapter info
            context.trace_manager.update_stage(
                node_id=node.task_id,
                stage_name="execution",
                agent_name=adapter_used_name,
                adapter_name=type(executor_adapter).__name__
            )

            node.update_status(TaskStatus.RUNNING)
            
            # IMPORTANT: Base adapter will update the trace stage during execution
            execution_result = await executor_adapter.process(node, agent_task_input_model, context.trace_manager)

            if execution_result is not None:
                node.result = execution_result
                
                # CRITICAL FIX: Store full result in aux_data for persistence
                node.aux_data['full_result'] = execution_result
                
                # ENHANCED: Extract meaningful output based on result type
                if hasattr(execution_result, 'output_text_with_citations'):
                    # CustomSearcherOutput - extract the actual search results
                    try:
                        output_summary = get_context_summary(
                            execution_result.output_text_with_citations, 
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                        )
                    except Exception as e:
                        logger.warning(f"Error generating summary for search results in {node.task_id}: {e}")
                        output_summary = execution_result.output_text_with_citations
                    node.output_summary = f"Search Results: {output_summary}"
                    
                    # Update trace with meaningful output
                    context.trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name="execution",
                        output_data=execution_result.output_text_with_citations,
                        llm_response=execution_result.output_text_with_citations  # Show search results as "LLM response"
                    )
                    
                elif hasattr(execution_result, 'model_dump'):
                    # Structured output - extract key information
                    dumped = execution_result.model_dump()
                    try:
                        output_summary = get_context_summary(
                            dumped, 
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                        )
                    except Exception as e:
                        logger.warning(f"Error generating summary for structured output in {node.task_id}: {e}")
                        output_summary = f"Structured output: {str(dumped)[:200]}..."
                    node.output_summary = output_summary
                    
                    # Update trace with structured output
                    context.trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name="execution",
                        output_data=dumped
                    )
                    
                elif isinstance(execution_result, str):
                    try:
                        output_summary = get_context_summary(
                            execution_result, 
                            target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                        )
                    except Exception as e:
                        logger.warning(f"Error generating summary for string output in {node.task_id}: {e}")
                        output_summary = execution_result[:250] + "..." if len(execution_result) > 250 else execution_result
                    node.output_summary = output_summary
                    
                    # Update trace with string output
                    context.trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name="execution",
                        output_data=execution_result,
                        llm_response=execution_result
                    )
                    
                else:
                    output_summary = f"Execution completed. Data type: {type(execution_result).__name__}"
                    node.output_summary = output_summary
                    
                    # Update trace with generic output
                    context.trace_manager.update_stage(
                        node_id=node.task_id,
                        stage_name="execution",
                        output_data=str(execution_result)[:1000]
                    )
                
                # CRITICAL FIX: Store execution details in aux_data
                if hasattr(context, 'execution_details'):
                    node.aux_data['execution_details'] = context.execution_details
                
                node.update_status(TaskStatus.DONE)
                logger.success(f"ReadyExecuteHandler: Node {node.task_id} execution complete. Status: {node.status.name}.")
                
                # Update the execution stage to mark it as completed without overwriting data
                # First, let's check what data exists in the stage before updating
                trace = context.trace_manager.get_trace_for_node(node.task_id)
                if trace:
                    stage = trace.get_stage("execution")
                    if stage and hasattr(stage, 'additional_data') and stage.additional_data:
                        logger.info(f"🔍 BEFORE COMPLETION - Stage has additional_data with keys: {list(stage.additional_data.keys())}")
                
                context.trace_manager.update_stage(
                    node_id=node.task_id,
                    stage_name="execution",
                    status="completed",
                    completed_at=datetime.now()
                )
                
                # Check again after update
                if trace:
                    stage = trace.get_stage("execution")
                    if stage and hasattr(stage, 'additional_data') and stage.additional_data:
                        logger.info(f"🔍 AFTER COMPLETION - Stage has additional_data with keys: {list(stage.additional_data.keys())}")
                
                # Force save the trace to disk to ensure it's persisted properly
                context.trace_manager._save_trace_to_disk(trace)
                
                # Trigger update callback after status change
                if context.update_callback:
                    try:
                        context.update_callback()
                        logger.debug(f"ReadyExecuteHandler: Update callback triggered for {node.task_id}")
                    except Exception as e:
                        logger.warning(f"ReadyExecuteHandler: Update callback failed: {e}")
                
                # Stage completion is now handled here since we removed it from adapters
            else:
                error_msg = "Executor returned no result."
                if node.status not in [TaskStatus.CANCELLED, TaskStatus.FAILED]:
                    node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                
                # Complete stage with error if adapter didn't do it
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="execution",
                    error=error_msg
                )
                
        except Exception as e:
            # Complete tracing stage with error
            context.trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="execution",
                error=str(e)
            )
            raise
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        ReadyExecuteHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry


class ReadyNodeHandler(INodeHandler):
    """Handles a node in READY status, determining if it needs atomization, planning, or execution."""
    def __init__(self, ready_plan_handler: ReadyPlanHandler, ready_execute_handler: ReadyExecuteHandler):
        self.ready_plan_handler = ready_plan_handler
        self.ready_execute_handler = ready_execute_handler

    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        logger.info(f"  ReadyNodeHandler: Handling READY node {node.task_id} (Initial NodeType: {node.node_type}, Layer: {node.layer}, Goal: '{node.goal[:30]}...')")
        node.update_status(TaskStatus.RUNNING) # Set status to RUNNING early

        # Use the max_planning_layer from the NodeProcessorConfig
        max_planning_layer = context.config.max_planning_layer
        
        # CRITICAL FIX: When forcing a PLAN node to EXECUTE, ensure it has the right adapter
        if node.layer >= max_planning_layer:
            logger.info(
                f"    ReadyNodeHandler: Node {node.task_id} (Layer {node.layer}) is at or exceeds max_planning_layer "
                f"({max_planning_layer}). Forcing to EXECUTE and skipping atomization."
            )
            
            # CRITICAL FIX: When forcing a PLAN node to EXECUTE, ensure it has the right adapter
            if node.node_type == NodeType.PLAN:
                # This was intended to be a PLAN node but we're forcing it to execute
                # Clear any aggregator configuration and let the execute handler pick the right executor
                logger.info(
                    f"    ReadyNodeHandler: Clearing aggregator configuration for forced-execute node {node.task_id}"
                )
                
                # Clear the agent_name if it's an aggregator
                if node.agent_name and 'aggregator' in node.agent_name.lower():
                    original_agent = node.agent_name
                    node.agent_name = None  # Let execute handler determine the right executor
                    logger.info(
                        f"    ReadyNodeHandler: Cleared aggregator '{original_agent}' from node {node.task_id}"
                    )
            
            node.node_type = NodeType.EXECUTE
            await self.ready_execute_handler.handle(node, context)
            return

        # Check if this is a root node and force_root_node_planning is enabled
        is_root_node = (
            node.task_id == "root" or 
            getattr(node, 'layer', 0) == 0 or
            getattr(node, 'parent_node_id', None) is None
        )
        
        atomizer_decision_type: Optional[NodeType] = None
        try:
            if is_root_node and getattr(context.config, 'force_root_node_planning', True):
                logger.info(
                    f"    ReadyNodeHandler: Node {node.task_id} is a root node with force_root_node_planning=True. "
                    f"Skipping atomization and forcing PLAN type to ensure proper decomposition."
                )
                atomizer_decision_type = NodeType.PLAN
            else:
                # At this point: node.layer < max_planning_layer
                # Run atomizer to determine if the node should be PLAN or EXECUTE
                logger.info(f"    ReadyNodeHandler: Node {node.task_id} (Layer {node.layer}) proceeding to atomization (layer < {max_planning_layer}).")
                
                atomizer_decision_type = await context.node_atomizer.atomize_node(node, context)
                
                if atomizer_decision_type is None:
                    raise ValueError("Atomizer returned None NodeType, which is unexpected.")
                
                logger.info(f"    ReadyNodeHandler: Atomizer for node {node.task_id} determined NodeType: {atomizer_decision_type}")

        except Exception as e:
            logger.exception(f"    ReadyNodeHandler: Error during atomization for node {node.task_id}. Marking FAILED.")
            node.update_status(TaskStatus.FAILED, error_msg=f"Error during node atomization: {str(e)}")
            return

        # Set the final node type based on atomizer decision
        node.node_type = atomizer_decision_type

        if node.node_type == NodeType.PLAN:
            logger.info(f"    ReadyNodeHandler: Node {node.task_id} is NodeType.PLAN. Calling ready_plan_handler.")
            await self.ready_plan_handler.handle(node, context)
        elif node.node_type == NodeType.EXECUTE:
            logger.info(f"    ReadyNodeHandler: Node {node.task_id} is NodeType.EXECUTE. Calling ready_execute_handler.")
            await self.ready_execute_handler.handle(node, context)
        else:
            logger.error(
                f"    ReadyNodeHandler: Node {node.task_id} has an unexpected final NodeType '{node.node_type}' "
                f"after atomization. Expected NodeType.PLAN or NodeType.EXECUTE."
            )
            node.update_status(TaskStatus.FAILED, error_msg=f"Node has unhandled final NodeType: {node.node_type}")


class AggregatingNodeHandler(INodeHandler):
    """Handles a node in AGGREGATING status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"  AggregatingNodeHandler: Handling AGGREGATING node {node.task_id} (Blueprint: {blueprint_name_log}, Goal: '{node.goal[:30]}...', Original Agent Name at Entry: {agent_name_at_entry})")
        
        # DEBUG: Log blueprint details
        if context.current_agent_blueprint:
            logger.debug(f"🔍 BLUEPRINT DEBUG for aggregation:")
            logger.debug(f"  - Blueprint name: {context.current_agent_blueprint.name}")
            logger.debug(f"  - Has root_aggregator_adapter_name: {hasattr(context.current_agent_blueprint, 'root_aggregator_adapter_name')}")
            if hasattr(context.current_agent_blueprint, 'root_aggregator_adapter_name'):
                logger.debug(f"  - root_aggregator_adapter_name: {context.current_agent_blueprint.root_aggregator_adapter_name}")
            logger.debug(f"  - Has aggregator_adapter_names: {hasattr(context.current_agent_blueprint, 'aggregator_adapter_names')}")
            if hasattr(context.current_agent_blueprint, 'aggregator_adapter_names'):
                logger.debug(f"  - aggregator_adapter_names: {context.current_agent_blueprint.aggregator_adapter_names}")
        
        try:
            # CRITICAL FIX: Start tracing for aggregation stage
            stage = context.trace_manager.start_stage(
                node_id=node.task_id,
                stage_name="aggregation",
                agent_name=agent_name_at_entry,
                adapter_name="AggregatingNodeHandler"
            )
            
            node.update_status(TaskStatus.RUNNING)
            child_results_for_aggregator: list = [] 
            
            if node.sub_graph_id:
                child_nodes = context.task_graph.get_nodes_in_graph(node.sub_graph_id)
                
                # Filter out children with DONE or FAILED status
                completed_children = []
                for child_node in child_nodes:
                    child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(str(child_node.status))
                    if child_status in [TaskStatus.DONE, TaskStatus.FAILED]:
                        completed_children.append(child_node)
                
                # 🔥 NEW: Filter out redundant child results based on dependency chains
                dependency_tracker = DependencyChainTracker(context.task_graph)
                non_redundant_children = dependency_tracker.filter_redundant_child_results(node, completed_children)
                
                logger.info(f"  Dependency filtering: {len(completed_children)} completed children -> {len(non_redundant_children)} non-redundant")
                
                total_child_content_size = 0
                
                for child_node in non_redundant_children:
                    child_status = child_node.status if isinstance(child_node.status, TaskStatus) else TaskStatus(str(child_node.status))
                    child_content = child_node.result if child_status == TaskStatus.DONE else child_node.error
                    
                    # 🔥 Use smart context sizing
                    processed_content, processing_method = get_smart_child_context(
                        content=child_content,
                        child_task_goal=child_node.goal,
                        child_task_type=child_node.task_type or "UNKNOWN"
                    )
                    
                    total_child_content_size += len(processed_content)
                    
                    # Enhanced ContextItem with processing metadata
                    context_item = ContextItem(
                        source_task_id=child_node.task_id, 
                        source_task_goal=child_node.goal,
                        content=processed_content,
                        content_type_description=f"child_{child_status.value.lower()}_output_{processing_method}"
                    )
                    child_results_for_aggregator.append(context_item)
                    
                    logger.info(f"    Child {child_node.task_id}: {processing_method} ({len(processed_content)} chars)")
                
                logger.info(f"  Total child content for aggregation: {total_child_content_size} chars from {len(child_results_for_aggregator)} children")

            # ENHANCED: Use blueprint for context builder agent selection too
            context_builder_agent_name = get_aggregator_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry,
                node
            )

            # ENHANCED: Use the enhanced context builder to get horizontal dependency context
            agent_task_input = resolve_context_for_agent_with_parents(
                current_task_id=node.task_id,
                current_goal=node.goal,
                current_task_type=TaskType.AGGREGATE.value,
                agent_name=context_builder_agent_name,
                knowledge_store=context.knowledge_store,
                overall_project_goal=context.task_graph.overall_project_goal
            )
            
            # CRITICAL: Combine child results with horizontal context
            # The enhanced context builder gives us horizontal context (from prerequisite siblings)
            # We need to add the child results to the existing context items
            if child_results_for_aggregator:
                if agent_task_input.relevant_context_items:
                    # Add child results to existing context items
                    agent_task_input.relevant_context_items.extend(child_results_for_aggregator)
                else:
                    # No existing context, just use child results
                    agent_task_input.relevant_context_items = child_results_for_aggregator
                
                # Update the formatted context to include both types
                formatted_context_parts = []
                
                # Add parent hierarchy context first (highest priority)
                if agent_task_input.parent_hierarchy_context:
                    formatted_context_parts.append(agent_task_input.parent_hierarchy_context.formatted_context)
                
                # Add horizontal context from prerequisites
                horizontal_context_items = [item for item in agent_task_input.relevant_context_items if item not in child_results_for_aggregator]
                if horizontal_context_items:
                    formatted_context_parts.append("\n=== PREREQUISITE CONTEXT ===")
                    for item in horizontal_context_items:
                        formatted_context_parts.extend([
                            f"\nSource: {item.source_task_goal}",
                            f"Type: {item.content_type_description}",
                            f"Content: {str(item.content)}",
                            "---"
                        ])
                
                # Add child results context
                if child_results_for_aggregator:
                    formatted_context_parts.append("\n=== CHILD RESULTS ===")
                    for item in child_results_for_aggregator:
                        formatted_context_parts.extend([
                            f"\nSource: {item.source_task_goal}",
                            f"Type: {item.content_type_description}",
                            f"Content: {str(item.content)}",
                            "---"
                        ])
                
                # Update the formatted context
                agent_task_input.formatted_full_context = "\n".join(formatted_context_parts) if formatted_context_parts else None
                
                logger.info(f"  AggregatingNodeHandler: Combined context - {len(horizontal_context_items)} horizontal + {len(child_results_for_aggregator)} child results")
            
            node.input_payload_dict = agent_task_input.model_dump()

            if not isinstance(node.node_type, NodeType): 
                node.node_type = NodeType(str(node.node_type)) 

            # ENHANCED: Use new blueprint system for aggregator selection based on task type
            lookup_name_for_aggregator = get_aggregator_from_blueprint(
                context.current_agent_blueprint,
                node.task_type,
                agent_name_at_entry,
                node
            )

            node.agent_name = lookup_name_for_aggregator
            aggregator_adapter = context.agent_registry.get_agent_adapter(node, action_verb="aggregate")

            if not aggregator_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry:
                logger.debug(f"        AggregatingNodeHandler: Blueprint aggregator lookup failed. Trying original entry agent_name: {agent_name_at_entry}")
                node.agent_name = agent_name_at_entry
                aggregator_adapter = context.agent_registry.get_agent_adapter(node, action_verb="aggregate")

            if not aggregator_adapter:
                final_tried_name = node.agent_name or lookup_name_for_aggregator or agent_name_at_entry
                error_msg = f"No AGGREGATE adapter found for node {node.task_id} (Effective Agent Name tried: {final_tried_name or 'None'})"
                logger.error(error_msg)
                
                # Complete tracing stage with error
                context.trace_manager.complete_stage(
                    node_id=node.task_id,
                    stage_name="aggregation",
                    error=error_msg
                )
                
                node.update_status(TaskStatus.FAILED, error_msg=error_msg)
                return

            adapter_used_name = getattr(aggregator_adapter, 'agent_name', type(aggregator_adapter).__name__)
            logger.info(f"    AggregatingNodeHandler: Invoking AGGREGATE adapter '{adapter_used_name}' for {node.task_id}")

            aggregated_result = await aggregator_adapter.process(node, agent_task_input, context.trace_manager)
            
            # CRITICAL FIX: Store full result in both locations for consistency
            node.result = aggregated_result
            node.aux_data['full_result'] = aggregated_result
            
            # Generate meaningful summary for aggregated results
            try:
                if aggregated_result:
                    meaningful_summary = get_context_summary(
                        aggregated_result, 
                        target_word_count=TARGET_WORD_COUNT_FOR_CTX_SUMMARIES
                    )
                    logger.info(f"    AggregatingNodeHandler: Generated meaningful summary for {node.task_id} (len: {len(meaningful_summary)})")
                else:
                    meaningful_summary = "Aggregation completed with no output"
            except Exception as e:
                logger.warning(f"    AggregatingNodeHandler: Error generating summary for {node.task_id}: {e}")
                meaningful_summary = f"Aggregation completed. Output type: {type(aggregated_result).__name__}"
            
            node.output_type_description = "aggregated_text_result"
            node.update_status(TaskStatus.DONE, result=aggregated_result, result_summary=meaningful_summary)
            logger.success(f"    AggregatingNodeHandler: Node {node.task_id} aggregation complete. Status: {node.status.name}.")
            
            # Trigger update callback after status change
            if context.update_callback:
                try:
                    context.update_callback()
                    logger.debug(f"AggregatingNodeHandler: Update callback triggered for {node.task_id}")
                except Exception as e:
                    logger.warning(f"AggregatingNodeHandler: Update callback failed: {e}")
            
            # Stage completion is handled by BaseAdapter's process method
            
        except Exception as e:
            # Complete tracing stage with error
            context.trace_manager.complete_stage(
                node_id=node.task_id,
                stage_name="aggregation",
                error=str(e)
            )
            raise
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        AggregatingNodeHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry


class NeedsReplanNodeHandler(INodeHandler):
    """Handles a node in NEEDS_REPLAN status."""
    async def handle(self, node: TaskNode, context: ProcessorContext) -> None:
        agent_name_at_entry = node.agent_name
        blueprint_name_log = context.current_agent_blueprint.name if context.current_agent_blueprint else "N/A"
        logger.info(f"  NeedsReplanNodeHandler: Handling NEEDS_REPLAN node {node.task_id} (Blueprint: {blueprint_name_log}, Replan Attempts: {node.replan_attempts}, Goal: '{node.goal[:30]}...', Original Agent Name at Entry: {agent_name_at_entry})")

        try:
            # Check if this is a user-requested modification
            is_user_modification = node.aux_data.get('user_modification_instructions') is not None
            
            # Only check max attempts for system-triggered replans, not user modifications
            if not is_user_modification and node.replan_attempts >= context.config.max_replan_attempts:
                logger.warning(f"    Node {node.task_id}: Max replan attempts ({context.config.max_replan_attempts}) reached. Marking as FAILED.")
                node.update_status(TaskStatus.FAILED, error_msg="Max replan attempts reached.")
                return

            # Only increment replan_attempts for system-triggered replans
            if not is_user_modification:
                node.replan_attempts += 1 
            
            node.update_status(TaskStatus.RUNNING)
            node.node_type = NodeType.PLAN 

            current_overall_objective = node.overall_objective or getattr(context.task_graph, 'overall_project_goal', "Undefined overall project goal")
            
            active_adapter = None
            is_modifier_agent = False 
            action_verb_to_use = "modify_plan"
            lookup_name_for_replan_op = agent_name_at_entry 

            if context.current_agent_blueprint:
                if context.current_agent_blueprint.plan_modifier_adapter_name:
                    lookup_name_for_replan_op = context.current_agent_blueprint.plan_modifier_adapter_name
                    logger.debug(f"        NeedsReplan: Blueprint specifies plan_modifier: {lookup_name_for_replan_op}")
                elif not lookup_name_for_replan_op and context.current_agent_blueprint.default_node_agent_name_prefix:
                    lookup_name_for_replan_op = f"{context.current_agent_blueprint.default_node_agent_name_prefix}PlanModifier"
                    logger.debug(f"        NeedsReplan: Blueprint suggests prefix for plan_modifier: {lookup_name_for_replan_op}")
            
            node.agent_name = lookup_name_for_replan_op
            active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use)
            if active_adapter: is_modifier_agent = True

            if not active_adapter: 
                logger.warning(f"    NeedsReplan: No 'modify_plan' adapter resolved (tried: {node.agent_name}). Falling back to 'plan' adapter.")
                action_verb_to_use = "plan"
                is_modifier_agent = False
                # MODIFIED: Use get_planner_from_blueprint for consistent planner lookup
                lookup_name_for_replan_op = get_planner_from_blueprint(
                    context.current_agent_blueprint,
                    node.task_type,
                    agent_name_at_entry, # Fallback if blueprint provides nothing
                    node # Pass the node for root planner consideration
                )
                logger.debug(f"        NeedsReplan: Fallback to 'plan' adapter. Blueprint lookup via get_planner_from_blueprint returned: {lookup_name_for_replan_op}")
                
                node.agent_name = lookup_name_for_replan_op # Set for planner lookup
                active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use) # Re-fetch adapter
                
                if not active_adapter and agent_name_at_entry and node.agent_name != agent_name_at_entry : 
                    node.agent_name = agent_name_at_entry
                    active_adapter = context.agent_registry.get_agent_adapter(node, action_verb=action_verb_to_use)

                if not active_adapter: # Still no planner? Fail.
                    node.update_status(TaskStatus.FAILED, error_msg="Fallback to Plan adapter failed during replan due to missing PlanModifier inputs & subsequent planner lookup failure.")
                    return
                logger.info(f"    NeedsReplanNodeHandler: Switched to Plan adapter '{getattr(active_adapter, 'agent_name', type(active_adapter).__name__)}' for replan.")
                # Input for the standard planner
                input_for_replan = resolve_input_for_planner_agent(
                    current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                    overall_objective=current_overall_objective, planning_depth=node.layer,
                    replan_details=node.replan_details, global_constraints=getattr(context.task_graph, 'global_constraints', [])
                )
            else: 
                # Input for the standard planner (initial case or after 'modify_plan' adapter wasn't found first)
                input_for_replan = resolve_input_for_planner_agent(
                    current_task_id=node.task_id, knowledge_store=context.knowledge_store,
                    overall_objective=current_overall_objective, planning_depth=node.layer,
                    replan_details=node.replan_details, global_constraints=getattr(context.task_graph, 'global_constraints', [])
                )
            node.input_payload_dict = input_for_replan.model_dump()
            new_plan_output: Optional[PlanOutput] = await active_adapter.process(node, input_for_replan, context.trace_manager)

            if new_plan_output is None or not new_plan_output.sub_tasks:
                logger.warning(f"    Node {node.task_id} (NEEDS_REPLAN): {'PlanModifier' if is_modifier_agent else 'Planner'} returned no sub-tasks.")
                node.update_status(TaskStatus.FAILED, error_msg=f"{'PlanModifier' if is_modifier_agent else 'Planner'} failed to produce new plan.")
                return

            # Check if this replan was triggered by user modification
            is_user_modification = node.aux_data.get('user_modification_instructions') is not None

            if is_user_modification:
                # Use review_modified_plan for user-requested modifications
                hitl_outcome_replan = await context.hitl_coordinator.review_modified_plan(
                    node=node, modified_plan=new_plan_output, replan_attempt_count=node.replan_attempts
                )
            else:
                # Use review_plan_generation for system-triggered replans
                hitl_outcome_replan = await context.hitl_coordinator.review_plan_generation(
                    node=node, plan_output=new_plan_output,
                    planner_input=input_for_replan, is_replan=True 
                )

            if hitl_outcome_replan["status"] == "approved":
                # Plan approved, proceed with applying the plan
                pass
            elif hitl_outcome_replan["status"] == "request_modification":
                # User requested another modification - update the node for another replan cycle
                logger.info(f"Node {node.task_id}: User requested another modification.")
                modification_instructions = hitl_outcome_replan.get('modification_instructions', 'User requested modification.')
                
                # Update the node for another modification cycle
                node.aux_data['original_plan_for_modification'] = new_plan_output
                node.aux_data['user_modification_instructions'] = modification_instructions
                node.replan_reason = f"User requested modification: {modification_instructions[:100]}..."
                node.update_status(TaskStatus.NEEDS_REPLAN)
                node.output_summary = "Plan requires user modification."
                
                # CRITICAL: Update the knowledge store immediately to ensure the status change is persisted
                context.knowledge_store.add_or_update_record_from_node(node)
                logger.info(f"✅ Node {node.task_id} status updated to NEEDS_REPLAN and persisted to knowledge store")
                return
            else:
                # Handle other statuses (aborted, error, etc.)
                logger.info(f"Node {node.task_id}: Replan not approved by user. Status: {hitl_outcome_replan['status']}")
                if node.status not in [TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.NEEDS_REPLAN]:
                     node.update_status(TaskStatus.FAILED, error_msg="Replanning not approved by user.")
                return

            if node.sub_graph_id: 
                logger.info(f"    Node {node.task_id}: Clearing existing sub-graph {node.sub_graph_id} before applying new plan.")
                context.task_graph.remove_graph_and_nodes(node.sub_graph_id) 
                node.sub_graph_id = None
                node.planned_sub_task_ids = [] 
            
            context.sub_node_creator.create_sub_nodes(node, new_plan_output)
            node.result = new_plan_output
            
            # CRITICAL FIX: Store full result in aux_data for consistency
            node.aux_data['full_result'] = new_plan_output
            
            node.output_summary = f"Replanned with {len(new_plan_output.sub_tasks)} sub-tasks after {node.replan_attempts} attempt(s)."
            node.replan_details = None 
            node.aux_data.pop('original_plan_for_modification', None) 
            node.aux_data.pop('user_modification_instructions', None)
            node.replan_reason = None 
            
            # Only update status if not already PLAN_DONE (prevents double transitions)
            if node.status != TaskStatus.PLAN_DONE:
                node.update_status(TaskStatus.PLAN_DONE)
            logger.success(f"    NeedsReplanNodeHandler: Node {node.task_id} replanning complete. Status: {node.status.name}")
        finally:
            if node.agent_name != agent_name_at_entry:
                logger.debug(f"        NeedsReplanNodeHandler: Restoring node.agent_name from '{node.agent_name}' to entry value '{agent_name_at_entry}' for node {node.task_id}")
                node.agent_name = agent_name_at_entry