from typing import Dict, Tuple, Optional, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType
    from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter

class AgentRegistry:
    """
    Manages the registration and retrieval of agent adapters for a specific agent instance.
    This class encapsulates the state that was previously global, making agent instances
    fully independent and safe for multiprocessing.
    """
    def __init__(self):
        # AGENT_REGISTRY: Maps (action_verb, TaskType enum) to an adapter instance
        self._agent_registry: Dict[Tuple[str, Optional["TaskType"]], "BaseAdapter"] = {}
        # NAMED_AGENTS: Maps a string name to an adapter instance
        self._named_agents: Dict[str, Any] = {}
        logger.trace("AgentRegistry instance created.")

    def register_agent_adapter(self, adapter: "BaseAdapter",
                               action_verb: Optional[str] = None,
                               task_type: Optional["TaskType"] = None,
                               name: Optional[str] = None):
        """Register an adapter instance in the agent registry."""
        from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
        if not isinstance(adapter, BaseAdapter):
            logger.error(f"Registration failed: Expected BaseAdapter, got {type(adapter)}. Adapter: {adapter}")
            return

        registered = False
        adapter_type_name = type(adapter).__name__
        adapter_name_attr = getattr(adapter, 'agent_name', adapter_type_name)

        if action_verb:
            key = (action_verb.lower(), task_type)
            if key in self._agent_registry and self._agent_registry[key] != adapter:
                logger.warning(
                    f"Overwriting agent '{type(self._agent_registry[key]).__name__}' with '{adapter_name_attr}' "
                    f"in agent_registry for key {key}"
                )
            self._agent_registry[key] = adapter
            logger.info(
                f"AgentRegistry: Registered adapter '{adapter_name_attr}' for action '{action_verb}', "
                f"task_type '{task_type.name if task_type else None}'"
            )
            registered = True

        if name:
            if name in self._named_agents and self._named_agents[name] != adapter:
                logger.warning(
                    f"Overwriting agent '{str(self._named_agents[name])}' with '{adapter_name_attr}' "
                    f"in named_agents for name '{name}'"
                )
            self._named_agents[name] = adapter
            logger.info(f"AgentRegistry: Registered adapter '{adapter_name_attr}' with name '{name}'")
            registered = True

        if not registered:
            logger.warning(f"Adapter '{adapter_name_attr}' was not registered. Provide action/task_type or a name.")

    def get_agent_adapter(self, node: "TaskNode", action_verb: str) -> Optional["BaseAdapter"]:
        """Retrieve an appropriate adapter for a given TaskNode and action verb."""
        from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
        logger.trace(f"🔍 AgentRegistry: Looking for adapter for node {node.task_id} with action '{action_verb}'")

        node_agent_name = getattr(node, 'agent_name', None)

        # 1. Try by specific agent_name assigned to the node
        if node_agent_name:
            adapter = self._named_agents.get(node_agent_name)
            if isinstance(adapter, BaseAdapter):
                logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' by name '{node_agent_name}' for node {node.task_id}.")
                return adapter
            if adapter is not None:
                logger.warning(f"AgentRegistry: Found item named '{node_agent_name}', but it's not a BaseAdapter (type: {type(adapter)}). Falling back.")
            else:
                logger.trace(f"AgentRegistry: Agent name '{node_agent_name}' not found. Falling back.")

        # 2. Fallback to (action_verb, task_type) lookup
        task_type_enum = self._resolve_task_type(node)

        # Special handling for verbs that don't use task_type
        if action_verb.lower() in ["atomize", "modify_plan"]:
            task_type_enum = None

        key = (action_verb.lower(), task_type_enum)
        
        adapter = self._agent_registry.get(key)
        if adapter:
            logger.info(f"AgentRegistry: Found adapter '{type(adapter).__name__}' for key {key} for node {node.task_id}.")
            return adapter
        else:
            logger.warning(f"AgentRegistry: No adapter found for key {key} for node {node.task_id}.")
            logger.trace(f"🔍 Available keys: {list(self._agent_registry.keys())}")
            return None

    def _resolve_task_type(self, node: "TaskNode") -> Optional["TaskType"]:
        """Safely resolves the task_type of a node to a TaskType enum."""
        from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskType
        task_type = getattr(node, 'task_type', None)
        if isinstance(task_type, TaskType):
            return task_type
        if isinstance(task_type, str):
            try:
                return TaskType[task_type.upper()]
            except KeyError:
                logger.warning(f"AgentRegistry: Invalid task_type string '{task_type}' for node {node.task_id}.")
                return None
        return None

    def get_named_agent(self, name: str) -> Optional["BaseAdapter"]:
        """Retrieves a registered agent by its specific name."""
        return self._named_agents.get(name)

    def get_all_named_agents(self) -> Dict[str, Any]:
        """Returns the dictionary of all named agents."""
        return self._named_agents.copy()

    def get_all_registered_agents(self) -> Dict[Tuple[str, Optional["TaskType"]], "BaseAdapter"]:
        """Returns the dictionary of all action-based registered agents."""
        return self._agent_registry.copy()

    def close_all(self):
        """
        Iterates through all registered adapters and calls their close() method
        to release underlying resources like network connections.
        """
        from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
        logger.info("AgentRegistry: Closing all registered agent adapters...")
        closed_adapters = set()
        
        all_adapters = list(self._agent_registry.values()) + list(self._named_agents.values())
        
        for adapter in all_adapters:
            if adapter in closed_adapters:
                continue
            
            if isinstance(adapter, BaseAdapter) and hasattr(adapter, 'close'):
                try:
                    # The adapter's close method should handle the actual cleanup
                    adapter.close()
                    closed_adapters.add(adapter)
                except Exception as e:
                    logger.error(f"Error closing adapter {type(adapter).__name__}: {e}")
        logger.info(f"AgentRegistry: Closed {len(closed_adapters)} unique adapters.")