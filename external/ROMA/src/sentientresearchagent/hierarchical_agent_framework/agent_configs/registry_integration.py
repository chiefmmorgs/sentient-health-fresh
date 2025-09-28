"""
Registry Integration

Bridges the new YAML-based agent configuration system with the existing registry.
Allows gradual migration from definitions/ to agent_configs/.
"""

from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
from pathlib import Path

from .config_loader import AgentConfigLoader, load_agent_configs
from .agent_factory import AgentFactory, create_agents_from_config
from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry
from sentientresearchagent.hierarchical_agent_framework.agents.base_adapter import BaseAdapter
from sentientresearchagent.hierarchical_agent_framework.node.task_node import TaskNode
from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint


class RegistryIntegrator:
    """Integrates YAML-configured agents into a specific registry instance."""
    
    def __init__(self, agent_registry: AgentRegistry, config_loader: Optional['AgentConfigLoader'] = None):
        """
        Initialize the registry integrator.
        
        Args:
            agent_registry: The AgentRegistry instance to populate.
            config_loader: Optional config loader. If None, creates a default one.
        """
        self.agent_registry = agent_registry
        self.config_loader = config_loader or AgentConfigLoader()
        self.factory = AgentFactory(self.config_loader)
        self.created_agents: Dict[str, Dict[str, Any]] = {}
        
    def load_and_register_agents(self) -> Dict[str, Any]:
        """
        Load agents from YAML configuration and register them in the existing registry.
        
        Returns:
            Dictionary with registration results
        """
        try:
            logger.info("🔄 Starting YAML agent integration with instance registry...")
            
            # Load configuration
            config = self.config_loader.load_config()
            logger.info(f"📋 Loaded configuration for {len(config.agents)} agents")
            
            # Create agents
            self.created_agents = self.factory.create_all_agents(config)
            logger.info(f"🏭 Created {len(self.created_agents)} agents from configuration")
            
            # Register agents in the provided registry instance
            registration_results = self._register_agents_in_instance_registry()
            
            logger.info("✅ YAML agent integration completed successfully")
            return registration_results
            
        except Exception as e:
            logger.error(f"❌ Failed to integrate YAML agents: {e}")
            raise
    
    def _register_agents_in_instance_registry(self) -> Dict[str, Any]:
        """Registers the created agents into the instance-specific registry."""
        results: Dict[str, Any] = {
            "registered_action_keys": 0,
            "registered_named_keys": 0,
            "skipped_agents": 0,
            "failed_registrations": 0,
            "details": []
        }
        
        for agent_name, agent_info in self.created_agents.items():
            try:
                adapter = agent_info.get("adapter")
                registration = agent_info.get("registration", {})
                
                if not adapter:
                    logger.warning(f"⏭️  Skipping registration for {agent_name}: No adapter instance found.")
                    results["skipped_agents"] += 1
                    continue

                if not isinstance(adapter, BaseAdapter):
                    logger.warning(f"⏭️  Skipping registration for {agent_name}: Item is not a valid BaseAdapter (type: {type(adapter)}).")
                    results["skipped_agents"] += 1
                    continue

                action_keys_registered = []
                for action_verb, task_type in registration.get("action_keys", []):
                    # Use the instance method to register
                    self.agent_registry.register_agent_adapter(
                        adapter=adapter,
                        action_verb=action_verb,
                        task_type=task_type
                    )
                    results["registered_action_keys"] += 1
                    action_keys_registered.append((action_verb, task_type))
                
                named_keys_registered = []
                for name in registration.get("named_keys", []):
                    # Use the instance method to register
                    self.agent_registry.register_agent_adapter(adapter=adapter, name=name)
                    results["registered_named_keys"] += 1
                    named_keys_registered.append(name)
                
                results["details"].append({
                    "name": agent_name,
                    "type": agent_info.get("type"),
                    "action_keys_registered": action_keys_registered,
                    "named_keys_registered": named_keys_registered,
                    "errors": [] # Assuming success if no exception
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to register agent {agent_name}: {e}", exc_info=True)
                results["failed_registrations"] += 1
        
        return results
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get current status of the agent registry."""
        return {
            "total_agent_registry_entries": len(self.agent_registry.get_all_registered_agents()),
            "total_named_agents": len(self.agent_registry.get_all_named_agents()),
            "yaml_agents_created": len(self.created_agents),
            "yaml_agent_names": list(self.created_agents.keys()),
            "registry_keys": list(self.agent_registry.get_all_registered_agents().keys()),
            "named_agent_keys": list(self.agent_registry.get_all_named_agents().keys())
        }
    
    def validate_integration(self) -> Dict[str, Any]:
        """Validate that YAML agents are properly integrated."""
        validation_results = {
            "valid": True,
            "issues": [],
            "yaml_agents_in_registry": 0,
            "yaml_agents_in_named": 0
        }
        
        for agent_name, agent_info in self.created_agents.items():
            adapter = agent_info["adapter"]
            registration = agent_info["registration"]
            
            # Check action key registrations
            for action_verb, task_type in registration["action_keys"]:
                key = (action_verb.lower(), task_type)
                registered_adapter = self.agent_registry.get_agent_adapter(
                    TaskNode(task_id="validation", goal="validation", task_type=task_type),
                    action_verb
                )
                if registered_adapter == adapter:
                    validation_results["yaml_agents_in_registry"] += 1
                else:
                    validation_results["issues"].append(
                        f"Agent {agent_name} not found in registry for key {key}"
                    )
                    validation_results["valid"] = False
            
            # Check named registrations
            for named_key in registration["named_keys"]:
                if self.agent_registry.get_named_agent(named_key) == adapter:
                    validation_results["yaml_agents_in_named"] += 1
                else:
                    validation_results["issues"].append(
                        f"Agent {agent_name} not found in registry for name '{named_key}'"
                    )
                    validation_results["valid"] = False
        
        return validation_results

    def load_and_register_profile(self, profile_name: str) -> Dict[str, Any]:
        """
        Load a specific profile and register any profile-specific agents.
        
        Args:
            profile_name: Name of the profile to load
            
        Returns:
            Registration results
        """
        try:
            from .profile_loader import ProfileLoader
            
            logger.info(f"🔄 Loading profile: {profile_name}")
            
            # Load the profile
            profile_loader = ProfileLoader()
            profile_config_raw = profile_loader.profiles_dir / f"{profile_name}.yaml"
            
            if not profile_config_raw.exists():
                raise FileNotFoundError(f"Profile {profile_name} not found")
            
            # Load raw config to get agents section
            from omegaconf import OmegaConf
            profile_config = OmegaConf.load(profile_config_raw)
            
            # Create any profile-specific agents
            profile_agents = self.factory.create_agents_for_profile(profile_config)
            
            if profile_agents:
                logger.info(f"📋 Created {len(profile_agents)} profile-specific agents")
                
                # Register the profile-specific agents
                self.created_agents.update(profile_agents)
                registration_results = self._register_agents_in_instance_registry()
                
                logger.info(f"✅ Profile {profile_name} integration completed")
                return registration_results
            else:
                logger.info(f"📋 Profile {profile_name} has no specific agents to register")
                return {
                    "registered_action_keys": 0,
                    "registered_named_keys": 0,
                    "skipped_agents": 0,
                    "failed_registrations": 0,
                    "details": []
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to integrate profile {profile_name}: {e}")
            raise

    def validate_profile_integration(self, profile_name: str) -> Dict[str, Any]:
        """
        Validate that a profile's agents are properly integrated.
        
        Args:
            profile_name: Name of the profile to validate
            
        Returns:
            Validation results
        """
        try:
            from .profile_loader import ProfileLoader
            
            # Load the blueprint
            profile_loader = ProfileLoader()
            blueprint = profile_loader.load_profile(profile_name)
            
            # Validate using the factory
            validation = self.factory.validate_blueprint_agents(blueprint)
            
            return {
                "profile_name": profile_name,
                "blueprint_valid": validation["valid"],
                "missing_agents": validation["missing_agents"],
                "blueprint_agents": validation["blueprint_agents"],
                "available_agents": validation["available_agents"]
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to validate profile {profile_name}: {e}")
            return {
                "profile_name": profile_name,
                "blueprint_valid": False,
                "error": str(e)
            }


def integrate_yaml_agents(agent_registry: AgentRegistry) -> Dict[str, Any]:
    """
    Convenience function to integrate YAML agents into the provided registry instance.
    
    Args:
        agent_registry: The AgentRegistry instance to populate.
        
    Returns:
        Integration results.
    """
    integrator = RegistryIntegrator(agent_registry)
    return integrator.load_and_register_agents()


def get_integration_status() -> Dict[str, Any]:
    """
    Get the current integration status.
    
    Returns:
        Status information
    """
    integrator = RegistryIntegrator()
    return integrator.get_registry_status()


def integrate_profile(profile_name: str) -> Dict[str, Any]:
    """
    Convenience function to integrate a specific profile.
    
    Args:
        profile_name: Name of the profile to integrate
        
    Returns:
        Integration results
    """
    integrator = RegistryIntegrator()
    return integrator.load_and_register_profile(profile_name)


def validate_profile(profile_name: str, agent_registry: AgentRegistry) -> Dict[str, Any]:
    """
    Validates a profile against a given agent registry instance.
    
    Args:
        profile_name: The name of the profile to validate.
        agent_registry: The AgentRegistry instance to validate against.
        
    Returns:
        A dictionary with validation results.
    """
    try:
        from .profile_loader import ProfileLoader
        from .config_loader import AgentConfigLoader
        
        # Load the blueprint
        profile_loader = ProfileLoader()
        blueprint = profile_loader.load_profile(profile_name)
        
        # Validate using the factory against the provided registry
        factory = AgentFactory(AgentConfigLoader()) # Factory needs a loader
        validation = factory.validate_blueprint_agents(blueprint, agent_registry)
        
        return {
            "profile_name": profile_name,
            "blueprint_valid": validation["valid"],
            "missing_agents": validation["missing_agents"],
            "blueprint_agents": validation["blueprint_agents"],
            "available_agents": validation["available_agents"],
            "issues": validation["issues"]
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to validate profile {profile_name}: {e}", exc_info=True)
        return {
            "profile_name": profile_name,
            "blueprint_valid": False,
            "error": str(e),
            "issues": [str(e)]
        }


def apply_blueprint_to_node(node: TaskNode, blueprint: AgentBlueprint, action_verb: str) -> bool:
    """
    Apply blueprint configuration to a TaskNode based on action and node level.
    
    Args:
        node: TaskNode to configure
        blueprint: AgentBlueprint to apply
        action_verb: The action being performed
        
    Returns:
        bool: True if successfully applied, False otherwise
    """
    try:
        # Determine if this is the root node
        is_root_node = (node.task_id == "root" or 
                       getattr(node, 'level', 0) == 0 or
                       getattr(node, 'parent_id', None) is None)
        
        if action_verb.lower() == "plan":
            # For planning, check if we should use root-specific planner
            if is_root_node and blueprint.root_planner_adapter_name:
                agent_name = blueprint.root_planner_adapter_name
                logger.info(f"🎯 Using ROOT planner '{agent_name}' for root node {node.task_id}")
            elif node.task_type and node.task_type in blueprint.planner_adapter_names:
                agent_name = blueprint.planner_adapter_names[node.task_type]
                logger.info(f"📋 Using task-specific planner '{agent_name}' for {node.task_type} node {node.task_id}")
            else:
                agent_name = blueprint.default_planner_adapter_name
                logger.info(f"📋 Using default planner '{agent_name}' for node {node.task_id}")
                
        elif action_verb.lower() == "execute":
            # For execution, use task-specific executors
            if node.task_type and node.task_type in blueprint.executor_adapter_names:
                agent_name = blueprint.executor_adapter_names[node.task_type]
            else:
                agent_name = blueprint.default_executor_adapter_name
                
        elif action_verb.lower() == "atomize":
            agent_name = blueprint.atomizer_adapter_name
        elif action_verb.lower() == "aggregate":
            agent_name = blueprint.aggregator_adapter_name
        elif action_verb.lower() == "modify_plan":
            agent_name = blueprint.plan_modifier_adapter_name
        else:
            logger.warning(f"Unknown action_verb '{action_verb}' for blueprint application")
            return False
        
        if agent_name:
            node.agent_name = agent_name
            logger.info(f"✅ Applied blueprint: Node {node.task_id} -> Agent '{agent_name}' for action '{action_verb}'")
            return True
        else:
            logger.warning(f"No agent name found for action '{action_verb}' in blueprint '{blueprint.name}'")
            return False
            
    except Exception as e:
        logger.error(f"Error applying blueprint to node {node.task_id}: {e}")
        return False


def integrate_agents_with_global_registry(config_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Convenience function to integrate agents with the global registry instance.
    
    Args:
        config_dir: Directory containing agent configuration files
        
    Returns:
        Dictionary with integration results
    """
    from sentientresearchagent.hierarchical_agent_framework.agents.registry import AgentRegistry
    from .config_loader import AgentConfigLoader
    
    global_registry = AgentRegistry.get_instance()
    config_loader = AgentConfigLoader(config_dir) if config_dir else AgentConfigLoader()
    integrator = RegistryIntegrator(global_registry, config_loader)
    
    return integrator.load_and_register_agents()


def integrate_agents_with_instance_registry(
    agent_registry: AgentRegistry, 
    config_dir: Optional[Path] = None,
    config_loader: Optional['AgentConfigLoader'] = None
) -> Dict[str, Any]:
    """
    Convenience function to integrate agents with a specific registry instance.
    
    Args:
        agent_registry: The AgentRegistry instance to populate
        config_dir: Directory containing agent configuration files
        config_loader: Optional config loader instance
        
    Returns:
        Dictionary with integration results
    """
    if config_loader is None and config_dir is not None:
        from .config_loader import AgentConfigLoader
        config_loader = AgentConfigLoader(config_dir)
    
    integrator = RegistryIntegrator(agent_registry, config_loader)
    return integrator.load_and_register_agents() 