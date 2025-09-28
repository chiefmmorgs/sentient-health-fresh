"""
AgentSelector - Service for selecting appropriate agents for tasks.

This service centralizes the logic for choosing which agent should
handle a particular task, making agent selection consistent and easy to modify.
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode, TaskType

if TYPE_CHECKING:
    from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint


class AgentRole(Enum):
    """Types of agent roles."""
    PLANNER = "planner"
    EXECUTOR = "executor"
    AGGREGATOR = "aggregator"
    ATOMIZER = "atomizer"
    MODIFIER = "modifier"


@dataclass
class AgentSelectionCriteria:
    """Criteria for selecting an agent."""
    node: TaskNode
    action_verb: str
    task_type: TaskType
    is_root: bool
    layer: int
    has_error: bool = False
    is_replan: bool = False
    
    @classmethod
    def from_node(cls, node: TaskNode, action_verb: str) -> "AgentSelectionCriteria":
        """Create criteria from a node."""
        return cls(
            node=node,
            action_verb=action_verb,
            task_type=node.task_type,
            is_root=(
                node.task_id == "root" or
                node.layer == 0 or
                node.parent_node_id is None
            ),
            layer=node.layer,
            has_error=node.error is not None,
            is_replan=node.replan_attempts > 0
        )


class AgentSelector:
    """
    Service for selecting appropriate agents based on task requirements.
    
    This service:
    - Encapsulates agent selection logic
    - Supports blueprint-based selection
    - Provides fallback mechanisms
    - Tracks selection metrics
    """
    
    def __init__(self, blueprint: Optional["AgentBlueprint"] = None):
        """
        Initialize the AgentSelector.
        
        Args:
            blueprint: Optional agent blueprint for guided selection
        """
        self.blueprint = blueprint
        
        # Default agent mappings
        self._default_agents = {
            # Planners
            (AgentRole.PLANNER, TaskType.SEARCH): "EnhancedSearchPlanner",
            (AgentRole.PLANNER, TaskType.THINK): "EnhancedThinkPlanner",
            (AgentRole.PLANNER, TaskType.WRITE): "EnhancedWritePlanner",
            (AgentRole.PLANNER, None): "CoreResearchPlanner",  # Default planner
            
            # Executors
            (AgentRole.EXECUTOR, TaskType.SEARCH): "OpenAICustomSearcher",
            (AgentRole.EXECUTOR, TaskType.THINK): "BasicReasoningExecutor",
            (AgentRole.EXECUTOR, TaskType.WRITE): "BasicReportWriter",
            (AgentRole.EXECUTOR, None): "BasicReasoningExecutor",  # Default executor
            
            # Aggregators
            (AgentRole.AGGREGATOR, TaskType.SEARCH): "SearchAggregator",
            (AgentRole.AGGREGATOR, TaskType.THINK): "ThinkAggregator",
            (AgentRole.AGGREGATOR, TaskType.WRITE): "WriteAggregator",
            (AgentRole.AGGREGATOR, None): "DefaultAggregator",  # Default aggregator
            
            # Others
            (AgentRole.ATOMIZER, None): "DefaultAtomizer",
            (AgentRole.MODIFIER, None): "PlanModifier",
        }
        
        # Root-specific agents
        self._root_agents = {
            AgentRole.PLANNER: "DeepResearchPlanner",
            AgentRole.AGGREGATOR: "RootResearchAggregator",
        }
        
        # Selection metrics
        self._metrics = {
            "total_selections": 0,
            "blueprint_selections": 0,
            "default_selections": 0,
            "fallback_selections": 0,
            "selection_by_role": {}
        }
        
        logger.info(f"AgentSelector initialized with blueprint: "
                   f"{blueprint.name if blueprint else 'None'}")
    
    async def select_agent(
        self,
        node: TaskNode,
        action_verb: str,
        task_type: Optional[TaskType] = None
    ) -> Optional[str]:
        """
        Select an appropriate agent for a task.
        
        Args:
            node: The task node
            action_verb: Action to perform (plan, execute, aggregate, etc.)
            task_type: Override task type (uses node.task_type if not provided)
            
        Returns:
            Agent name or None if no suitable agent found
        """
        # Create selection criteria
        criteria = AgentSelectionCriteria.from_node(node, action_verb)
        if task_type:
            criteria.task_type = task_type
        
        # Map action verb to role
        role = self._map_action_to_role(action_verb)
        if not role:
            logger.error(f"Unknown action verb: {action_verb}")
            return None
        
        # Update metrics
        self._metrics["total_selections"] += 1
        self._metrics["selection_by_role"][role.value] = \
            self._metrics["selection_by_role"].get(role.value, 0) + 1
        
        # Try selection strategies in order
        agent_name = None
        
        # 1. Try blueprint selection
        if self.blueprint:
            agent_name = self._select_from_blueprint(criteria, role)
            if agent_name:
                self._metrics["blueprint_selections"] += 1
                logger.info(f"Selected {agent_name} from blueprint for {role.value}")
                return agent_name
        
        # 2. Try default selection
        agent_name = self._select_default(criteria, role)
        if agent_name:
            self._metrics["default_selections"] += 1
            logger.info(f"Selected default {agent_name} for {role.value}")
            return agent_name
        
        # 3. Try fallback
        agent_name = self._select_fallback(criteria, role)
        if agent_name:
            self._metrics["fallback_selections"] += 1
            logger.warning(f"Using fallback {agent_name} for {role.value}")
            return agent_name
        
        logger.error(f"No agent found for {action_verb} on {node.task_id}")
        return None
    
    def _map_action_to_role(self, action_verb: str) -> Optional[AgentRole]:
        """Map action verb to agent role."""
        action_map = {
            "plan": AgentRole.PLANNER,
            "execute": AgentRole.EXECUTOR,
            "aggregate": AgentRole.AGGREGATOR,
            "atomize": AgentRole.ATOMIZER,
            "modify_plan": AgentRole.MODIFIER,
        }
        return action_map.get(action_verb)
    
    def _select_from_blueprint(
        self,
        criteria: AgentSelectionCriteria,
        role: AgentRole
    ) -> Optional[str]:
        """Select agent from blueprint."""
        if not self.blueprint:
            return None
        
        # Handle root node special cases
        if criteria.is_root:
            if role == AgentRole.PLANNER and hasattr(self.blueprint, 'root_planner_adapter_name'):
                return self.blueprint.root_planner_adapter_name
            elif role == AgentRole.AGGREGATOR and hasattr(self.blueprint, 'root_aggregator_adapter_name'):
                return self.blueprint.root_aggregator_adapter_name
        
        # Task-specific selection
        if role == AgentRole.PLANNER:
            if hasattr(self.blueprint, 'planner_adapter_names'):
                return self.blueprint.planner_adapter_names.get(criteria.task_type)
            elif hasattr(self.blueprint, 'default_planner_adapter_name'):
                return self.blueprint.default_planner_adapter_name
            elif hasattr(self.blueprint, 'planner_adapter_name'):
                return self.blueprint.planner_adapter_name
                
        elif role == AgentRole.EXECUTOR:
            if hasattr(self.blueprint, 'executor_adapter_names'):
                return self.blueprint.executor_adapter_names.get(criteria.task_type)
            elif hasattr(self.blueprint, 'default_executor_adapter_name'):
                return self.blueprint.default_executor_adapter_name
                
        elif role == AgentRole.AGGREGATOR:
            if hasattr(self.blueprint, 'aggregator_adapter_names'):
                return self.blueprint.aggregator_adapter_names.get(criteria.task_type)
            elif hasattr(self.blueprint, 'aggregator_adapter_name'):
                return self.blueprint.aggregator_adapter_name
        
        # Try prefix-based naming
        if hasattr(self.blueprint, 'default_node_agent_name_prefix'):
            prefix = self.blueprint.default_node_agent_name_prefix
            suffix_map = {
                AgentRole.PLANNER: "Planner",
                AgentRole.EXECUTOR: "Executor",
                AgentRole.AGGREGATOR: "Aggregator",
                AgentRole.ATOMIZER: "Atomizer",
                AgentRole.MODIFIER: "Modifier",
            }
            suffix = suffix_map.get(role)
            if suffix:
                return f"{prefix}{suffix}"
        
        return None
    
    def _select_default(
        self,
        criteria: AgentSelectionCriteria,
        role: AgentRole
    ) -> Optional[str]:
        """Select from default agent mappings."""
        # Check root-specific agents
        if criteria.is_root and role in self._root_agents:
            return self._root_agents[role]
        
        # Try task-specific default
        agent_name = self._default_agents.get((role, criteria.task_type))
        if agent_name:
            return agent_name
        
        # Try role default
        return self._default_agents.get((role, None))
    
    def _select_fallback(
        self,
        criteria: AgentSelectionCriteria,
        role: AgentRole
    ) -> Optional[str]:
        """Select fallback agent."""
        # Use the node's existing agent name if available
        if criteria.node.agent_name:
            return criteria.node.agent_name
        
        # Last resort defaults
        fallback_map = {
            AgentRole.PLANNER: "CoreResearchPlanner",
            AgentRole.EXECUTOR: "BasicReasoningExecutor",
            AgentRole.AGGREGATOR: "DefaultAggregator",
            AgentRole.ATOMIZER: "DefaultAtomizer",
            AgentRole.MODIFIER: "CoreResearchPlanner",  # Use planner as modifier
        }
        
        return fallback_map.get(role)
    
    def register_custom_agent(
        self,
        role: AgentRole,
        task_type: Optional[TaskType],
        agent_name: str
    ):
        """
        Register a custom agent mapping.
        
        Args:
            role: Agent role
            task_type: Task type (None for default)
            agent_name: Name of the agent
        """
        self._default_agents[(role, task_type)] = agent_name
        logger.info(f"Registered custom agent: {agent_name} for {role.value}/{task_type}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get selection metrics."""
        return self._metrics.copy()
    
    def reset_metrics(self):
        """Reset selection metrics."""
        self._metrics = {
            "total_selections": 0,
            "blueprint_selections": 0,
            "default_selections": 0,
            "fallback_selections": 0,
            "selection_by_role": {}
        }
    
    def get_agent_recommendations(
        self,
        task_type: TaskType,
        include_alternates: bool = True
    ) -> Dict[str, List[str]]:
        """
        Get agent recommendations for a task type.
        
        Args:
            task_type: Type of task
            include_alternates: Whether to include alternate agents
            
        Returns:
            Dictionary of role -> agent names
        """
        recommendations = {}
        
        for role in AgentRole:
            primary = self._default_agents.get((role, task_type))
            if not primary:
                primary = self._default_agents.get((role, None))
            
            if primary:
                agents = [primary]
                
                if include_alternates:
                    # Add alternates based on task type
                    if task_type == TaskType.SEARCH and role == AgentRole.EXECUTOR:
                        agents.extend(["GeminiCustomSearcher", "ExaComprehensiveSearcher"])
                    elif task_type == TaskType.THINK and role == AgentRole.PLANNER:
                        agents.append("CoreResearchPlanner")
                
                recommendations[role.value] = agents
        
        return recommendations