from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional # Add Optional

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode

# Forward references for types used in ProcessorContext to avoid new circular imports
if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.graph.task_graph import TaskGraph
    from sentientresearchagent.hierarchical_agent_framework.context.knowledge_store import KnowledgeStore
    from .node_configs import NodeProcessorConfig
    from .hitl_coordinator import HITLCoordinator
    from .node_creation_utils import SubNodeCreator
    from .node_atomizer_utils import NodeAtomizer
    # Import AgentBlueprint for type hinting
    from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint


class ProcessorContext:
    """Holds shared resources and configurations for node handlers."""
    def __init__(self,
                 task_graph: 'TaskGraph',
                 knowledge_store: 'KnowledgeStore',
                 config: 'NodeProcessorConfig',
                 hitl_coordinator: 'HITLCoordinator',
                 sub_node_creator: 'SubNodeCreator',
                 node_atomizer: 'NodeAtomizer',
                 current_agent_blueprint: Optional['AgentBlueprint'] = None): # MODIFIED LINE
        self.task_graph = task_graph
        self.knowledge_store = knowledge_store
        self.config = config
        self.hitl_coordinator = hitl_coordinator
        self.sub_node_creator = sub_node_creator
        self.node_atomizer = node_atomizer
        self.current_agent_blueprint = current_agent_blueprint # MODIFIED LINE


class INodeHandler(ABC):
    """
    Abstract base class for node processing handlers (Strategy Pattern).
    """
    @abstractmethod
    async def handle(self, node: TaskNode, processor_context: 'ProcessorContext') -> None:
        """
        Handles the processing of a node based on its current state.

        Args:
            node: The TaskNode to process.
            processor_context: An object containing shared resources and components
                               from the NodeProcessor (e.g., task_graph, knowledge_store,
                               config, sub-components like hitl_coordinator).
        """
        pass
