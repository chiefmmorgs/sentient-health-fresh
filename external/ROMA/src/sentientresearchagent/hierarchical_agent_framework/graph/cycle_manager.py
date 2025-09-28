from loguru import logger
import asyncio
import time
from typing import Any as NodeProcessorType, Optional, Callable # For NodeProcessor type hint

from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType # NodeType, TaskType might not be directly used here
from sentientresearchagent.hierarchical_agent_framework.graph.state_manager import StateManager
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore


def _validate_status_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
    """
    Validate that a status transition is logically allowed.
    This prevents invalid state transitions that could cause deadlocks.
    """
    # Define valid transitions
    valid_transitions = {
        TaskStatus.PENDING: [TaskStatus.READY, TaskStatus.FAILED],
        TaskStatus.READY: [TaskStatus.RUNNING, TaskStatus.FAILED],
        TaskStatus.RUNNING: [TaskStatus.PLAN_DONE, TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
        TaskStatus.PLAN_DONE: [TaskStatus.AGGREGATING, TaskStatus.DONE, TaskStatus.READY, TaskStatus.NEEDS_REPLAN, TaskStatus.FAILED],
        TaskStatus.AGGREGATING: [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.NEEDS_REPLAN],
        TaskStatus.NEEDS_REPLAN: [TaskStatus.READY, TaskStatus.FAILED],
        TaskStatus.DONE: [],  # Terminal state
        TaskStatus.FAILED: []  # Terminal state
    }
    
    allowed = valid_transitions.get(from_status, [])
    return to_status in allowed
# NodeProcessor itself is passed, not its components separately to CycleManager.
# from sentientresearchagent.hierarchical_agent_framework.node.node_processor import NodeProcessor 


async def _atomic_transition_if_eligible(
    node: TaskNode,
    from_status: TaskStatus,
    to_status: TaskStatus,
    eligibility_check: Callable[[], bool],
    knowledge_store: KnowledgeStore,
    update_callback: Optional[Callable] = None
) -> bool:
    """
    Atomically transitions a node from one status to another if eligible.
    This prevents race conditions where the node status might change between
    the check and the update.
    
    Returns:
        bool: True if transition occurred, False otherwise
    """
    try:
        # Enhanced atomicity check with node lock
        if not hasattr(node, '_status_lock'):
            logger.warning(f"Node {node.task_id} missing status lock - potential race condition")
            return False
        
        # Double-check pattern with lock for extra safety
        with node._status_lock:
            # Verify status hasn't changed during async operations
            if node.status != from_status:
                logger.debug(f"Atomic transition skipped: {node.task_id} status changed ({node.status} != {from_status})")
                return False
            
            # Validate transition is allowed
            if not _validate_status_transition(node.status, to_status):
                logger.warning(f"Invalid transition attempted: {node.task_id} {from_status} -> {to_status}")
                return False
            
            # Check eligibility within the lock
            if not eligibility_check():
                logger.debug(f"Atomic transition skipped: {node.task_id} eligibility check failed")
                return False
            
            # Perform the transition
            old_status = node.status
            node.update_status(to_status)
            
            # Verify transition actually occurred
            if node.status != to_status:
                logger.error(f"Transition failed: {node.task_id} expected {to_status}, got {node.status}")
                return False
            
            # Update knowledge store with new state
            try:
                knowledge_store.add_or_update_record_from_node(node)
            except Exception as e:
                logger.error(f"Knowledge store update failed for {node.task_id}: {e}")
                # Don't fail the transition for KS errors
            
            # Trigger update callback for immediate broadcast
            if update_callback:
                try:
                    update_callback()
                    logger.debug(f"Atomic transition: Update callback triggered after {old_status} -> {to_status} for {node.task_id}")
                except Exception as e:
                    logger.warning(f"Atomic transition: Update callback failed: {e}")
            
            logger.debug(f"Atomic transition successful: {node.task_id} {old_status} -> {to_status}")
            return True
            
    except Exception as e:
        logger.error(f"Atomic transition error for {node.task_id}: {e}")
        return False 

class CycleManager:
    """
    Manages the core logic of a single step within the ExecutionEngine's run_cycle.
    It handles node status transitions and dispatches nodes to the NodeProcessor.
    """

    async def execute_step(
        self,
        task_graph: TaskGraph,
        state_manager: StateManager,
        node_processor: NodeProcessorType, # Actual NodeProcessor instance
        knowledge_store: KnowledgeStore,
        update_callback: Optional[Callable] = None  # Add update callback for broadcasts
    ) -> bool:
        """
        Executes one step of the processing cycle.

        Returns:
            bool: True if any processing or state transition occurred in the step, False otherwise.
        """
        processed_in_step = False
        
        all_nodes_current_step = task_graph.get_all_nodes()
        if not all_nodes_current_step:
            logger.debug("CycleManager: No nodes in the graph to process this step.")
            return False # No nodes, no processing

        # --- 1. Update PENDING -> READY transitions ---
        logger.debug("CycleManager: Checking for PENDING -> READY transitions.")
        for node in all_nodes_current_step:
            # Atomic check-and-update for PENDING -> READY transition
            if await _atomic_transition_if_eligible(node, TaskStatus.PENDING, TaskStatus.READY,
                                                   lambda: state_manager.can_become_ready(node),
                                                   knowledge_store, update_callback):
                processed_in_step = True
                logger.info(f"  CycleManager Transition: Node {node.task_id} PENDING -> READY (Goal: '{node.goal[:30]}...')")

        # --- 2. Process AGGREGATING nodes (serially, one at a time) ---
        # Re-fetch nodes as statuses might have changed
        nodes_after_pending_update = task_graph.get_all_nodes()
        aggregating_node_to_process = next((n for n in nodes_after_pending_update if n.status == TaskStatus.AGGREGATING), None)

        if aggregating_node_to_process:
            logger.info(f"  CycleManager: Processing AGGREGATING Node: {aggregating_node_to_process.task_id} (Layer: {aggregating_node_to_process.layer}, Goal: '{aggregating_node_to_process.goal[:30]}...')")
            await node_processor.process_node(aggregating_node_to_process, task_graph, knowledge_store)
            processed_in_step = True
            # If an AGGREGATING node was processed, it's a significant state change.
            # Return True and let ExecutionEngine loop again to re-evaluate the whole graph state.
            return True # Indicate processing occurred

        # --- 3. Process READY nodes (in parallel) ---
        nodes_for_ready_processing = task_graph.get_all_nodes() # Re-fetch
        ready_nodes = [n for n in nodes_for_ready_processing if n.status == TaskStatus.READY]
        if ready_nodes:
            logger.info(f"  CycleManager: Found {len(ready_nodes)} READY nodes. Queueing for parallel processing.")
            
            # Enhanced logging for parallel execution
            node_details = []
            for node in ready_nodes:
                parent_info = f"parent:{node.parent_node_id[:8] if node.parent_node_id else 'none'}"
                node_details.append(f"{node.task_id[:8]}({parent_info})")
            logger.info(f"  Parallel batch: [{', '.join(node_details)}]")
            
            tasks_to_run = [
                node_processor.process_node(ready_node, task_graph, knowledge_store)
                for ready_node in ready_nodes
            ]
            if tasks_to_run:
                try:
                    logger.debug(f"  Starting asyncio.gather for {len(tasks_to_run)} tasks...")
                    start_time = time.time()
                    await asyncio.gather(*tasks_to_run)
                    end_time = time.time()
                    logger.info(f"  Parallel processing completed in {end_time - start_time:.2f}s")
                    
                    # Log post-processing status
                    post_status = {}
                    for node in ready_nodes:
                        status = node.status.name
                        post_status[status] = post_status.get(status, 0) + 1
                    logger.info(f"  Post-processing status: {post_status}")
                    
                    processed_in_step = True
                    return True # Indicate processing occurred
                except Exception as e:
                    logger.error(f"  Parallel processing failed: {e}")
                    # Log which nodes might be stuck
                    for node in ready_nodes:
                        logger.error(f"    Node {node.task_id[:8]} status: {node.status.name}")
                    raise

        # --- 4. Update PLAN_DONE -> AGGREGATING / READY transitions ---
        nodes_for_plan_done_update = task_graph.get_all_nodes()
        made_plan_done_transition = False
        logger.debug("CycleManager: Checking for PLAN_DONE transitions.")
        
        # Keep checking PLAN_DONE nodes until no more transitions are possible
        # This handles race conditions where subtasks complete asynchronously
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            any_transition_this_iteration = False
            plan_done_nodes = [n for n in task_graph.get_all_nodes() if n.status == TaskStatus.PLAN_DONE]
            
            if not plan_done_nodes:
                logger.debug(f"CycleManager: No PLAN_DONE nodes remaining after {iteration-1} iterations")
                break
                
            logger.debug(f"CycleManager: PLAN_DONE iteration {iteration}: checking {len(plan_done_nodes)} nodes")
            
            for node in plan_done_nodes:
                if node.status != TaskStatus.PLAN_DONE:
                    # Node status changed during this iteration, skip
                    continue
                    
                # ENHANCED: Check if this node was converted to EXECUTE type during planning
                if node.node_type == NodeType.EXECUTE:
                    # A PLAN node that becomes EXECUTE is an atomic task
                    if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.DONE,
                                                           lambda: True,  # Always eligible if we got here
                                                           knowledge_store, update_callback):
                        logger.info(f"  CycleManager Transition: Node {node.task_id} was atomic. Transitioning PLAN_DONE -> DONE.")
                        processed_in_step = True
                        made_plan_done_transition = True
                        any_transition_this_iteration = True
                # Also check if this was originally an EXECUTE node that somehow got planned
                elif hasattr(node, 'aux_data') and node.aux_data.get('was_executed_as_atomic'):
                    if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.DONE,
                                                           lambda: True,  # Always eligible if we got here
                                                           knowledge_store, update_callback):
                        logger.warning(f"  CycleManager: Node {node.task_id} was already executed as atomic but reached PLAN_DONE. Transitioning directly to DONE.")
                        processed_in_step = True
                        made_plan_done_transition = True
                        any_transition_this_iteration = True
                elif state_manager.can_aggregate(node):
                    children_failed = False
                    if node.sub_graph_id:
                        sub_graph_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
                        if any(sn.status == TaskStatus.FAILED for sn in sub_graph_nodes):
                            children_failed = True
                    
                    if children_failed:
                        if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.NEEDS_REPLAN,
                                                               lambda: True,  # Already checked children_failed
                                                               knowledge_store, update_callback):
                            logger.info(f"  CycleManager Transition: Node {node.task_id} PLAN_DONE -> NEEDS_REPLAN (due to failed children, Goal: '{node.goal[:30]}...')")
                            any_transition_this_iteration = True
                    else:
                        if await _atomic_transition_if_eligible(node, TaskStatus.PLAN_DONE, TaskStatus.AGGREGATING,
                                                               lambda: True,  # Already checked can_aggregate
                                                               knowledge_store, update_callback):
                            logger.info(f"  CycleManager Transition: Node {node.task_id} PLAN_DONE -> AGGREGATING (Goal: '{node.goal[:30]}...')")
                            any_transition_this_iteration = True
                    processed_in_step = True
                    made_plan_done_transition = True
                else:
                    # Node cannot aggregate yet (dependencies not ready)
                    logger.debug(f"Node {node.task_id} cannot AGGREGATE: Not all sub-tasks in '{node.sub_graph_id}' are finished.")
                    # Log which sub-tasks are blocking
                    if node.sub_graph_id:
                        sub_nodes = task_graph.get_nodes_in_graph(node.sub_graph_id)
                        incomplete = [n for n in sub_nodes if n.status not in {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED}]
                        if incomplete:
                            logger.debug(f"  Blocking sub-tasks for {node.task_id}:")
                            for inc in incomplete[:5]:  # Show first 5
                                logger.debug(f"    - {inc.task_id}: {inc.status.name} (goal: '{inc.goal[:30]}...')")
            
            # If no transitions occurred this iteration, break (no point in re-checking)
            if not any_transition_this_iteration:
                logger.debug(f"CycleManager: No PLAN_DONE transitions in iteration {iteration}, stopping re-evaluation")
                break
        
        if iteration >= max_iterations:
            logger.warning(f"CycleManager: PLAN_DONE re-evaluation hit max iterations ({max_iterations})")
        
        if made_plan_done_transition:
            return True # Indicate processing occurred

        # --- 5. Process NEEDS_REPLAN nodes (serially, one at a time) ---
        # This runs if no other major processing happened above that caused an early return.
        nodes_for_replan_processing = task_graph.get_all_nodes()
        needs_replan_nodes = [n for n in nodes_for_replan_processing if n.status == TaskStatus.NEEDS_REPLAN]
        if needs_replan_nodes:
            node_to_replan = needs_replan_nodes[0]
            logger.info(f"  CycleManager: Processing NEEDS_REPLAN Node: {node_to_replan.task_id} (Goal: '{node_to_replan.goal[:30]}...')")
            await node_processor.process_node(node_to_replan, task_graph, knowledge_store)
            processed_in_step = True
            # After processing a NEEDS_REPLAN node, its status changes.
            return True # Indicate processing occurred

        return processed_in_step 