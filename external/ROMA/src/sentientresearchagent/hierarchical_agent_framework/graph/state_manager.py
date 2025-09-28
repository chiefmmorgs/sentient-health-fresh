from typing import Optional, TYPE_CHECKING
from collections import deque
from loguru import logger

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
# Import from our consolidated types module
from sentientresearchagent.hierarchical_agent_framework.types import (
    TaskStatus, NodeType, safe_task_status, safe_node_type, 
    TERMINAL_STATUSES, is_terminal_status
)

class StateManager:
    """Handles logic for checking if nodes can transition state."""

    def __init__(self, task_graph: "TaskGraph"):
        self.task_graph = task_graph

    def _find_container_graph_id_for_node(self, node: "TaskNode") -> Optional[str]:
        """
        Helper to find which graph contains a node.
        A node lives in the sub_graph of its parent.
        If no parent, it's in the root graph.
        """
        if node.parent_node_id:
            parent_node = self.task_graph.get_node(node.parent_node_id)
            if parent_node:
                # The node is in the sub-graph created and managed by its parent
                if parent_node.sub_graph_id:
                    return parent_node.sub_graph_id
                else:
                    # CRITICAL FIX: If parent doesn't have sub_graph_id yet, search all graphs
                    # This happens when parent is RUNNING but children are already created
                    logger.debug(f"Parent {parent_node.task_id} has no sub_graph_id yet, searching for child {node.task_id}")
                    for graph_id, graph_obj in self.task_graph.graphs.items():
                        if node.task_id in graph_obj.nodes:
                            logger.debug(f"Found child {node.task_id} in graph {graph_id}")
                            return graph_id
                    logger.warning(f"Child {node.task_id} not found in any graph despite having parent {parent_node.task_id}")
                    return None
            else:
                # This case (parent_node_id exists but parent_node not found) is an inconsistency.
                logger.warning(f"StateManager: Node {node.task_id} has parent_id {node.parent_node_id} but parent not found.")
                return None 
        elif self.task_graph.root_graph_id and self.task_graph.get_graph(self.task_graph.root_graph_id) and node.task_id in self.task_graph.get_graph(self.task_graph.root_graph_id).nodes:
            # If it has no parent, it should be in the root graph.
            return self.task_graph.root_graph_id
        else:
            # Fallback: search all graphs
            logger.warning(f"StateManager: Node {node.task_id} container graph not found by parent/root heuristic. Searching all graphs.")
            for graph_id, graph_obj in self.task_graph.graphs.items():
                if node.task_id in graph_obj.nodes:
                    return graph_id
            logger.error(f"StateManager: Node {node.task_id} could not be located in any graph.")
            return None

    def _check_parent_conditions_for_ready(self, node: "TaskNode") -> bool:
        """Checks if the parent node's status allows the current node to become READY."""
        if node.parent_node_id:
            parent_node = self.task_graph.get_node(node.parent_node_id)
            if not parent_node or parent_node.status not in (TaskStatus.RUNNING, TaskStatus.PLAN_DONE, TaskStatus.DONE, TaskStatus.AGGREGATING):
                return False
        # If no parent_node_id, it's a root node, so parent conditions are implicitly met.
        return True

    def _check_predecessor_conditions_for_ready(self, node: "TaskNode", container_graph_id: str) -> bool:
        """Checks if all predecessors of the node in its container graph are DONE."""
        predecessors = self.task_graph.get_node_predecessors(container_graph_id, node.task_id)
        if not predecessors:  # No predecessors, so dependency condition is met
            return True
        
        all_preds_done = all(pred.status == TaskStatus.DONE for pred in predecessors)
        return all_preds_done

    def can_become_ready(self, node: "TaskNode") -> bool:
        """Checks if a PENDING node can transition to READY."""
        if node.status != TaskStatus.PENDING:
            return False

        if not self._check_parent_conditions_for_ready(node):
            logger.debug(f"Node {node.task_id} cannot become READY: Parent conditions not met")
            if node.parent_node_id:
                parent = self.task_graph.get_node(node.parent_node_id)
                if parent:
                    logger.debug(f"  Parent {parent.task_id} status: {parent.status}")
            return False

        container_graph_id = self._find_container_graph_id_for_node(node)
        if not container_graph_id:
            logger.warning(f"Node {node.task_id} cannot become READY: Cannot determine its container graph.")
            if node.parent_node_id:
                parent = self.task_graph.get_node(node.parent_node_id)
                if parent:
                    logger.debug(f"  Parent {parent.task_id} sub_graph_id: {parent.sub_graph_id}")
            return False

        return self._check_predecessor_conditions_for_ready(node, container_graph_id)

    def can_aggregate(self, node: "TaskNode") -> bool:
        """Checks if a PLAN_DONE node (which is a PLAN type node) can transition to AGGREGATING."""
        
        # Use safe conversion for better type handling
        try:
            current_node_type = safe_node_type(node.node_type)
        except ValueError:
            logger.debug(f"StateManager.can_aggregate: Node {node.task_id} has invalid node_type '{node.node_type}'. Cannot convert to NodeType enum.")
            return False

        logger.debug(f"StateManager.can_aggregate CALLED for node {node.task_id}, status: {node.status}, node_type: {current_node_type}")

        if node.status != TaskStatus.PLAN_DONE or current_node_type != NodeType.PLAN:
            logger.debug(f"StateManager.can_aggregate: Node {node.task_id} failed initial status/type check.")
            return False
        
        logger.debug(f"StateManager.can_aggregate: Node {node.task_id} passed initial status/type check.")

        if not node.sub_graph_id:
            logger.warning(f"StateManager: Node {node.task_id} is PLAN_DONE but has no sub_graph_id.")
            return False
        
        logger.debug(f"StateManager.can_aggregate: Node {node.task_id} has sub_graph_id: {node.sub_graph_id}. Fetching sub-graph nodes.")
        sub_graph_nodes = self.task_graph.get_nodes_in_graph(node.sub_graph_id)
        logger.info(f"🔍 AGGREGATION DEBUG - Node {node.task_id} sub_graph_id: {node.sub_graph_id}, found {len(sub_graph_nodes)} children")

        if not sub_graph_nodes:
            # If a plan resulted in no sub-tasks, it could be considered ready to "aggregate" nothing.
            logger.info(f"Node {node.task_id} can AGGREGATE: PLAN_DONE and its sub-graph '{node.sub_graph_id}' is empty.")
            return True

        # All tasks within its sub_graph_id must be in a terminal state
        all_sub_finished = all(is_terminal_status(sn.status) for sn in sub_graph_nodes)
        
        if all_sub_finished:
            logger.info(f"Node {node.task_id} can AGGREGATE: All {len(sub_graph_nodes)} sub-tasks in '{node.sub_graph_id}' are finished.")
        else:
            # Enhanced debugging: show which specific nodes are blocking aggregation
            incomplete_nodes = []
            for sn in sub_graph_nodes:
                if not is_terminal_status(sn.status):
                    incomplete_nodes.append(f"{sn.task_id}:{sn.status.name}")
            
            logger.warning(f"⏳ AGGREGATION BLOCKED - Node {node.task_id} cannot AGGREGATE: {len(incomplete_nodes)}/{len(sub_graph_nodes)} children incomplete: {', '.join(incomplete_nodes)}")
            
            # Log each sub-task status for debugging
            for sn in sub_graph_nodes:
                terminal_status = is_terminal_status(sn.status)
                logger.debug(f"  ⏳ Sub-task {sn.task_id}: status={sn.status.name}, is_terminal={terminal_status}")
            
        return all_sub_finished

    def can_transition_to_done(self, node: "TaskNode") -> bool:
        """Check if a node can transition to DONE status."""
        # Only certain statuses can transition to DONE
        valid_statuses = {TaskStatus.RUNNING, TaskStatus.AGGREGATING}
        return node.status in valid_statuses

    def can_transition_to_failed(self, node: "TaskNode") -> bool:
        """Check if a node can transition to FAILED status."""
        # Any non-terminal status can transition to FAILED
        return not is_terminal_status(node.status)