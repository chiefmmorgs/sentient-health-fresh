"""
Sentient Research Agent - Hierarchical Agent Framework (HAF) - Node Package

This package contains all components related to individual task nodes within the HAF,
including their definition, processing, configuration, and human-in-the-loop coordination.
"""

# Directly defined in this package
from .task_node import TaskNode
from .node_processor import NodeProcessor
from .node_configs import NodeProcessorConfig
from .hitl_coordinator import HITLCoordinator
from .inode_handler import INodeHandler # Interface for node handlers

# Imported from other HAF packages to be part of this package's convenient API
from sentientresearchagent.hierarchical_agent_framework.types import TaskStatus, TaskType, NodeType
from ..context.agent_io_models import ReplanRequestDetails # Used by TaskNode

# Node handlers themselves (from node_handlers.py) are often not directly exported
# from the package __init__, but rather used by the NodeProcessor.
# Similarly for node_atomizer_utils.py and node_creation_utils.py unless
# specific utilities are meant for broader public use.

__all__ = [
    # From .task_node.py
    "TaskNode",

    # From .node_processor.py
    "NodeProcessor",

    # From .node_configs.py
    "NodeProcessorConfig",

    # From .hitl_coordinator.py
    "HITLCoordinator",

    # From .inode_handler.py
    "INodeHandler",

    # Re-exported from ..types
    "TaskStatus",
    "TaskType",
    "NodeType",

    # Re-exported from ..context.agent_io_models
    "ReplanRequestDetails", # This is the actual class name TaskNode uses
]
