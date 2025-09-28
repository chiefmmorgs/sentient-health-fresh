from loguru import logger
from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskStatus, NodeType, TaskType
from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore

class ProjectInitializer:
    """
    Responsible for initializing a new project by creating the root task node and graph.
    """
    def initialize_project(self,
                           root_goal: str,
                           task_graph: TaskGraph,
                           knowledge_store: KnowledgeStore,
                           root_task_type: TaskType = TaskType.WRITE
                          ) -> TaskNode:
        """
        Sets up the initial root node for the project.
        Returns the created root_node.
        """
        if task_graph.root_graph_id is not None:
            logger.warning("ProjectInitializer: Project already initialized or root graph exists. Skipping re-initialization.")
            existing_root = task_graph.get_node("root")
            if existing_root:
                return existing_root
            else:
                # This case should ideally not happen if root_graph_id is set.
                raise RuntimeError("ProjectInitializer: Root graph ID exists but root node is missing.")

        task_graph.overall_project_goal = root_goal
        
        root_node_id = "root"  # Fixed ID for the ultimate root task
        root_graph_id = "root_graph"  # Graph containing the root task

        # The root task usually starts as a PLAN to decompose the overall goal
        root_node = TaskNode(
            goal=root_goal,
            task_type=root_task_type,
            node_type=NodeType.PLAN,  # Root usually starts by planning
            layer=0,
            task_id=root_node_id,
            overall_objective=root_goal, # For root, objective is its own goal initially
            status=TaskStatus.PENDING # Initial status
        )
        
        task_graph.add_graph(root_graph_id, is_root=True)
        task_graph.add_node_to_graph(root_graph_id, root_node)
        knowledge_store.add_or_update_record_from_node(root_node)

        logger.success(f"ProjectInitializer: Initialized with root node: {root_node.task_id} in graph {root_graph_id}.")
        return root_node 