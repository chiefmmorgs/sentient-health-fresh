"""
StateTransitionManager - Centralized state transition management.

Responsibilities:
- Define and enforce state transition rules
- Validate state transitions
- Handle state change notifications
- Maintain state consistency across the system
"""

from typing import Dict, List, Set, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
import asyncio
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus
from sentientresearchagent.exceptions import InvalidTaskStateError

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore


@dataclass
class StateTransition:
    """Represents a state transition."""
    from_state: TaskStatus
    to_state: TaskStatus
    condition: Optional[Callable[[TaskNode], bool]] = None
    side_effects: Optional[Callable[[TaskNode], None]] = None


class TransitionEvent(Enum):
    """Types of transition events."""
    DEPENDENCIES_MET = "dependencies_met"
    PLANNING_COMPLETE = "planning_complete"
    EXECUTION_COMPLETE = "execution_complete"
    AGGREGATION_READY = "aggregation_ready"
    ERROR_OCCURRED = "error_occurred"
    REPLAN_REQUESTED = "replan_requested"
    USER_CANCELLED = "user_cancelled"


class StateTransitionManager:
    """
    Manages all state transitions in the system.
    
    This class provides a centralized place for all state transition logic,
    ensuring consistency and making the state machine explicit.
    """
    
    def __init__(self, task_graph: "TaskGraph", knowledge_store: "KnowledgeStore"):
        """
        Initialize the StateTransitionManager.
        
        Args:
            task_graph: The task graph
            knowledge_store: Knowledge store for persistence
        """
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        
        # Define valid transitions
        self._valid_transitions = self._define_transitions()
        
        # Transition hooks
        self._pre_transition_hooks: List[Callable] = []
        self._post_transition_hooks: List[Callable] = []
        
        # Transition history for debugging
        self._transition_history: List[Dict] = []
        self._max_history = 1000
        
        logger.info("StateTransitionManager initialized")
    
    def _define_transitions(self) -> Dict[TaskStatus, Set[TaskStatus]]:
        """
        Define the valid state transitions.
        
        Returns:
            Mapping of current state to valid next states
        """
        return {
            TaskStatus.PENDING: {
                TaskStatus.READY,      # Dependencies satisfied
                TaskStatus.FAILED,     # Initialization failure
                TaskStatus.CANCELLED   # User cancellation
            },
            TaskStatus.READY: {
                TaskStatus.RUNNING,    # Execution started
                TaskStatus.FAILED,     # Pre-execution failure
                TaskStatus.CANCELLED   # User cancellation
            },
            TaskStatus.RUNNING: {
                TaskStatus.DONE,       # Execution complete
                TaskStatus.PLAN_DONE,  # Planning complete
                TaskStatus.FAILED,     # Execution failure
                TaskStatus.NEEDS_REPLAN,  # Replan needed
                TaskStatus.CANCELLED   # User cancellation
            },
            TaskStatus.PLAN_DONE: {
                TaskStatus.AGGREGATING,    # Ready to aggregate
                TaskStatus.FAILED,         # Post-planning failure
                TaskStatus.NEEDS_REPLAN    # Replan needed
            },
            TaskStatus.AGGREGATING: {
                TaskStatus.DONE,           # Aggregation complete
                TaskStatus.FAILED,         # Aggregation failure
                TaskStatus.NEEDS_REPLAN    # Need different approach
            },
            TaskStatus.NEEDS_REPLAN: {
                TaskStatus.READY,          # Ready to retry
                TaskStatus.RUNNING,        # Direct to execution
                TaskStatus.FAILED,         # Give up
                TaskStatus.CANCELLED       # User cancellation
            },
            TaskStatus.DONE: {
                TaskStatus.NEEDS_REPLAN    # Retry completed task
            },
            TaskStatus.FAILED: {
                TaskStatus.NEEDS_REPLAN,   # Retry failed task
                TaskStatus.READY           # Direct retry
            },
            TaskStatus.CANCELLED: set()    # Terminal state
        }
    
    async def transition_node(
        self,
        node: TaskNode,
        to_state: TaskStatus,
        reason: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Transition a node to a new state.
        
        Args:
            node: Node to transition
            to_state: Target state
            reason: Reason for transition
            **kwargs: Additional data (result, error, etc.)
            
        Returns:
            True if transition was successful
        """
        from_state = node.status
        
        # Validate transition
        if not self._is_valid_transition(from_state, to_state):
            logger.warning(
                f"Invalid transition attempted: {node.task_id} "
                f"{from_state} -> {to_state}"
            )
            return False
        
        # Check transition conditions
        if not await self._check_transition_conditions(node, from_state, to_state):
            logger.info(
                f"Transition conditions not met: {node.task_id} "
                f"{from_state} -> {to_state}"
            )
            return False
        
        # Execute pre-transition hooks
        for hook in self._pre_transition_hooks:
            await self._execute_hook(hook, node, from_state, to_state)
        
        # Perform the transition
        try:
            # Update node status
            node.update_status(
                to_state,
                result=kwargs.get("result"),
                error_msg=kwargs.get("error_msg"),
                result_summary=kwargs.get("result_summary"),
                validate_transition=False  # We already validated
            )
            
            # Apply state-specific side effects
            await self._apply_side_effects(node, from_state, to_state, **kwargs)
            
            # Update knowledge store
            self.knowledge_store.add_or_update_record_from_node(node)
            
            # Record transition
            self._record_transition(node, from_state, to_state, reason)
            
            # Execute post-transition hooks
            for hook in self._post_transition_hooks:
                await self._execute_hook(hook, node, from_state, to_state)
            
            logger.info(
                f"State transition successful: {node.task_id} "
                f"{from_state} -> {to_state}"
                f"{f' ({reason})' if reason else ''}"
            )
            
            return True
            
        except Exception as e:
            logger.error(
                f"State transition failed: {node.task_id} "
                f"{from_state} -> {to_state}: {e}"
            )
            return False
    
    async def handle_event(
        self,
        node: TaskNode,
        event: TransitionEvent,
        **event_data
    ) -> bool:
        """
        Handle a transition event.
        
        Args:
            node: Node experiencing the event
            event: Type of event
            **event_data: Event-specific data
            
        Returns:
            True if event was handled successfully
        """
        current_state = node.status
        
        # Map events to transitions
        transition_map = {
            (TaskStatus.PENDING, TransitionEvent.DEPENDENCIES_MET): TaskStatus.READY,
            (TaskStatus.READY, TransitionEvent.PLANNING_COMPLETE): TaskStatus.PLAN_DONE,
            (TaskStatus.READY, TransitionEvent.EXECUTION_COMPLETE): TaskStatus.DONE,
            (TaskStatus.RUNNING, TransitionEvent.PLANNING_COMPLETE): TaskStatus.PLAN_DONE,
            (TaskStatus.RUNNING, TransitionEvent.EXECUTION_COMPLETE): TaskStatus.DONE,
            (TaskStatus.PLAN_DONE, TransitionEvent.AGGREGATION_READY): TaskStatus.AGGREGATING,
            (TaskStatus.AGGREGATING, TransitionEvent.EXECUTION_COMPLETE): TaskStatus.DONE,
        }
        
        # Handle error events
        if event == TransitionEvent.ERROR_OCCURRED:
            return await self.transition_node(
                node,
                TaskStatus.FAILED,
                reason=f"Error: {event_data.get('error', 'Unknown')}",
                error_msg=event_data.get('error')
            )
        
        # Handle replan events
        if event == TransitionEvent.REPLAN_REQUESTED:
            return await self.transition_node(
                node,
                TaskStatus.NEEDS_REPLAN,
                reason=event_data.get('reason', 'Replan requested')
            )
        
        # Handle cancellation
        if event == TransitionEvent.USER_CANCELLED:
            return await self.transition_node(
                node,
                TaskStatus.CANCELLED,
                reason="User cancelled"
            )
        
        # Look up transition
        key = (current_state, event)
        if key in transition_map:
            target_state = transition_map[key]
            return await self.transition_node(
                node,
                target_state,
                reason=f"Event: {event.value}",
                **event_data
            )
        
        logger.warning(
            f"No transition defined for {node.task_id} "
            f"in state {current_state} with event {event}"
        )
        return False
    
    async def update_ready_nodes(self) -> int:
        """
        Update all nodes that should transition to READY.
        
        Returns:
            Number of nodes transitioned
        """
        transitioned = 0
        all_nodes = self.task_graph.get_all_nodes()
        
        for node in all_nodes:
            if node.status == TaskStatus.PENDING:
                if await self._can_transition_to_ready(node):
                    success = await self.transition_node(
                        node,
                        TaskStatus.READY,
                        reason="Dependencies satisfied"
                    )
                    if success:
                        transitioned += 1
        
        if transitioned > 0:
            logger.info(f"Transitioned {transitioned} nodes to READY")
        
        return transitioned
    
    async def check_aggregation_ready(self) -> int:
        """
        Check and transition nodes ready for aggregation.
        
        Returns:
            Number of nodes transitioned
        """
        transitioned = 0
        all_nodes = self.task_graph.get_all_nodes()
        
        for node in all_nodes:
            if node.status == TaskStatus.PLAN_DONE:
                if await self._can_aggregate(node):
                    success = await self.handle_event(
                        node,
                        TransitionEvent.AGGREGATION_READY
                    )
                    if success:
                        transitioned += 1
        
        return transitioned
    
    def _is_valid_transition(self, from_state: TaskStatus, to_state: TaskStatus) -> bool:
        """Check if a transition is valid."""
        valid_next_states = self._valid_transitions.get(from_state, set())
        return to_state in valid_next_states
    
    async def _check_transition_conditions(
        self,
        node: TaskNode,
        from_state: TaskStatus,
        to_state: TaskStatus
    ) -> bool:
        """
        Check if transition conditions are met.
        
        Args:
            node: Node to check
            from_state: Current state
            to_state: Target state
            
        Returns:
            True if conditions are met
        """
        # PENDING -> READY: Check dependencies
        if from_state == TaskStatus.PENDING and to_state == TaskStatus.READY:
            return await self._can_transition_to_ready(node)
        
        # PLAN_DONE -> AGGREGATING: Check children completion
        if from_state == TaskStatus.PLAN_DONE and to_state == TaskStatus.AGGREGATING:
            return await self._can_aggregate(node)
        
        # Default: Allow transition
        return True
    
    async def _can_transition_to_ready(self, node: TaskNode) -> bool:
        """Check if a PENDING node can become READY."""
        # Check parent state
        if node.parent_node_id:
            parent = self.task_graph.get_node(node.parent_node_id)
            if not parent:
                return False
            if parent.status not in [TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE]:
                return False
        
        # Check dependencies
        container_graph = self._find_container_graph(node)
        if container_graph:
            predecessors = self.task_graph.get_node_predecessors(
                container_graph,
                node.task_id
            )
            for pred in predecessors:
                if pred.status != TaskStatus.DONE:
                    return False
        
        return True
    
    async def _can_aggregate(self, node: TaskNode) -> bool:
        """Check if a PLAN_DONE node can aggregate."""
        if not node.sub_graph_id:
            return True  # No children to wait for
        
        sub_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
        if not sub_nodes:
            return True  # Empty sub-graph
        
        # Check if enough children are complete
        complete_count = sum(
            1 for n in sub_nodes
            if n.status in [TaskStatus.DONE, TaskStatus.FAILED]
        )
        
        # Require at least 80% completion or all but one
        threshold = max(0.8 * len(sub_nodes), len(sub_nodes) - 1)
        return complete_count >= threshold
    
    async def _apply_side_effects(
        self,
        node: TaskNode,
        from_state: TaskStatus,
        to_state: TaskStatus,
        **kwargs
    ):
        """Apply state-specific side effects."""
        # Clear retry count on successful completion
        if to_state == TaskStatus.DONE:
            node.aux_data.pop("retry_count", None)
            node.aux_data.pop("retry_history", None)
        
        # Set completion timestamp
        if to_state in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            node.timestamp_completed = node.timestamp_updated
        
        # Clear sub-graph on replan
        if to_state == TaskStatus.NEEDS_REPLAN and node.sub_graph_id:
            # In real implementation, would clean up sub-graph
            logger.info(f"Would clean up sub-graph {node.sub_graph_id} for replan")
    
    def _find_container_graph(self, node: TaskNode) -> Optional[str]:
        """Find the graph containing a node."""
        for graph_id, graph in self.task_graph.graphs.items():
            if node.task_id in graph.nodes:
                return graph_id
        return None
    
    def _record_transition(
        self,
        node: TaskNode,
        from_state: TaskStatus,
        to_state: TaskStatus,
        reason: Optional[str]
    ):
        """Record a transition in history."""
        transition_record = {
            "node_id": node.task_id,
            "from_state": from_state.name,
            "to_state": to_state.name,
            "reason": reason,
            "timestamp": node.timestamp_updated.isoformat()
        }
        
        self._transition_history.append(transition_record)
        
        # Trim history if needed
        if len(self._transition_history) > self._max_history:
            self._transition_history = self._transition_history[-self._max_history:]
    
    async def _execute_hook(
        self,
        hook: Callable,
        node: TaskNode,
        from_state: TaskStatus,
        to_state: TaskStatus
    ):
        """Execute a transition hook safely."""
        try:
            if asyncio.iscoroutinefunction(hook):
                await hook(node, from_state, to_state)
            else:
                hook(node, from_state, to_state)
        except Exception as e:
            logger.error(f"Transition hook failed: {e}")
    
    def add_pre_transition_hook(self, hook: Callable):
        """Add a pre-transition hook."""
        self._pre_transition_hooks.append(hook)
    
    def add_post_transition_hook(self, hook: Callable):
        """Add a post-transition hook."""
        self._post_transition_hooks.append(hook)
    
    def get_transition_history(
        self,
        node_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get transition history.
        
        Args:
            node_id: Filter by node ID
            limit: Maximum records to return
            
        Returns:
            List of transition records
        """
        history = self._transition_history
        
        if node_id:
            history = [h for h in history if h["node_id"] == node_id]
        
        return history[-limit:]
    
    def get_state_statistics(self) -> Dict[str, int]:
        """Get statistics about current node states."""
        all_nodes = self.task_graph.get_all_nodes()
        
        stats = {}
        for status in TaskStatus:
            count = sum(1 for n in all_nodes if n.status == status)
            stats[status.name] = count
        
        return stats