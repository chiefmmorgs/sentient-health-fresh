"""
Utility functions for managing task dependencies and preventing redundant context propagation.
"""
from typing import Set, List, Dict, Optional
from loguru import logger
from ..graph.task_graph import TaskGraph
from .task_node import TaskNode, TaskStatus


class DependencyChainTracker:
    """Tracks transitive dependency chains to prevent redundant context propagation."""
    
    def __init__(self, task_graph: TaskGraph):
        self.task_graph = task_graph
        self._dependency_cache: Dict[str, Set[str]] = {}
    
    def get_all_transitive_dependencies(self, node: TaskNode) -> Set[str]:
        """
        Get all transitive dependencies for a node.
        If node 3 depends on node 2, and node 2 depends on nodes 0,1,
        then node 3's transitive dependencies are {0, 1, 2}.
        
        Args:
            node: The node to get dependencies for
            
        Returns:
            Set of task IDs that this node transitively depends on
        """
        if node.task_id in self._dependency_cache:
            return self._dependency_cache[node.task_id]
        
        transitive_deps = set()
        
        # Get direct dependencies from aux_data
        direct_dep_indices = node.aux_data.get('depends_on_indices', []) if node.aux_data is not None else []
        
        if direct_dep_indices and node.parent_node_id:
            # Get parent node to resolve indices to actual task IDs
            parent_node = self.task_graph.get_node(node.parent_node_id)
            if parent_node and parent_node.planned_sub_task_ids:
                # Convert indices to task IDs
                for idx in direct_dep_indices:
                    if 0 <= idx < len(parent_node.planned_sub_task_ids):
                        dep_task_id = parent_node.planned_sub_task_ids[idx]
                        transitive_deps.add(dep_task_id)
                        
                        # Recursively get dependencies of dependencies
                        dep_node = self.task_graph.get_node(dep_task_id)
                        if dep_node:
                            sub_deps = self.get_all_transitive_dependencies(dep_node)
                            transitive_deps.update(sub_deps)
        
        # Cache the result
        self._dependency_cache[node.task_id] = transitive_deps
        return transitive_deps
    
    def filter_redundant_child_results(self, parent_node: TaskNode, child_nodes: List[TaskNode]) -> List[TaskNode]:
        """
        Filter out child nodes whose results are already processed by other children.
        
        For example, if node 3 depends on node 2, and node 2 depends on nodes 0,1,
        then only node 3's result should be passed to the parent aggregator.
        
        Args:
            parent_node: The parent node doing aggregation
            child_nodes: List of child nodes with results
            
        Returns:
            Filtered list of child nodes whose results should be aggregated
        """
        # Build a map of which nodes are consumed by others
        consumed_by: Dict[str, Set[str]] = {}
        node_map = {node.task_id: node for node in child_nodes}
        
        # For each child, track what it consumes
        for child in child_nodes:
            deps = self.get_all_transitive_dependencies(child)
            for dep_id in deps:
                if dep_id in node_map:  # Only track dependencies within this sibling group
                    if dep_id not in consumed_by:
                        consumed_by[dep_id] = set()
                    consumed_by[dep_id].add(child.task_id)
        
        # Find nodes that are not consumed by any other node
        non_redundant_nodes = []
        for child in child_nodes:
            if child.task_id not in consumed_by:
                # This node's output is not consumed by any sibling
                non_redundant_nodes.append(child)
                logger.info(f"  DependencyChainTracker: Including {child.task_id} - not consumed by siblings")
            else:
                consumers = consumed_by[child.task_id]
                # Check if all consumers are failed/cancelled
                all_consumers_failed = True
                for consumer_id in consumers:
                    consumer = node_map.get(consumer_id)
                    if consumer and consumer.status == TaskStatus.DONE:
                        all_consumers_failed = False
                        break
                
                if all_consumers_failed:
                    # Include this node since its consumers failed
                    non_redundant_nodes.append(child)
                    logger.info(f"  DependencyChainTracker: Including {child.task_id} - consumers failed")
                else:
                    logger.info(f"  DependencyChainTracker: Excluding {child.task_id} - consumed by {consumers}")
        
        return non_redundant_nodes
    
    def clear_cache(self):
        """Clear the dependency cache."""
        self._dependency_cache.clear()