"""
Agent Profile Loader

Loads agent profiles from YAML files with comprehensive Pydantic validation.
Creates AgentBlueprint instances with enhanced validation and error handling.
"""

import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger

try:
    from omegaconf import OmegaConf, DictConfig
except ImportError:
    logger.error("OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
    raise

from sentientresearchagent.hierarchical_agent_framework.agent_blueprints import AgentBlueprint
from sentientresearchagent.hierarchical_agent_framework.types import TaskType
from sentientresearchagent.hierarchical_agent_framework.agent_configs.models import (
    validate_profile_yaml, ProfileYAMLConfig, ProfileConfig
)


class ProfileLoader:
    """Loads agent profiles from YAML configuration files with comprehensive Pydantic validation."""
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        """
        Initialize the profile loader with validation.
        
        Args:
            profiles_dir: Directory containing profile YAML files.
                         If None, uses the profiles/ subdirectory of this module.
        """
        if profiles_dir is None:
            profiles_dir = Path(__file__).parent / "profiles"
        
        self.profiles_dir = Path(profiles_dir)
        
        # Validate profiles directory exists
        if not self.profiles_dir.exists():
            raise FileNotFoundError(f"Profiles directory not found: {self.profiles_dir}")
        
        # Cache for validated profiles
        self._profile_cache: Dict[str, ProfileYAMLConfig] = {}
    
    def list_available_profiles(self) -> List[str]:
        """
        List all available profile names.
        
        Returns:
            List of profile names (without .yaml extension)
        """
        profile_files = list(self.profiles_dir.glob("*.yaml"))
        return [f.stem for f in profile_files]
    
    def load_profile(self, profile_name: str) -> AgentBlueprint:
        """
        Load a specific agent profile with comprehensive validation and caching.
        
        Args:
            profile_name: Name of the profile to load (without .yaml extension)
            
        Returns:
            AgentBlueprint instance
            
        Raises:
            FileNotFoundError: If profile file doesn't exist
            ValueError: If profile configuration is invalid
        """
        # Check cache first
        if profile_name in self._profile_cache:
            logger.debug(f"Using cached profile: {profile_name}")
            validated_config = self._profile_cache[profile_name]
            profile_config = validated_config.profile
        else:
            profile_file = self.profiles_dir / f"{profile_name}.yaml"
            
            if not profile_file.exists():
                available = self.list_available_profiles()
                raise FileNotFoundError(
                    f"Profile '{profile_name}' not found. Available profiles: {available}"
                )
            
            try:
                logger.info(f"Loading agent profile from: {profile_file}")
                config = OmegaConf.load(profile_file)
                
                # Validate using Pydantic model
                try:
                    config_dict = OmegaConf.to_container(config, resolve=True)
                    validated_config = validate_profile_yaml(config_dict)
                    profile_config = validated_config.profile
                    
                    # Cache the validated config
                    self._profile_cache[profile_name] = validated_config
                    
                    logger.info(f"✅ Profile validated and cached: {profile_name}")
                    
                except Exception as e:
                    logger.error(f"Profile validation failed for {profile_name}: {e}")
                    raise ValueError(f"Invalid profile configuration: {e}") from e
                    
            except Exception as e:
                if isinstance(e, ValueError):
                    raise
                logger.error(f"Failed to load profile '{profile_name}': {e}")
                raise
        
        # Convert TaskType strings to enums (validated by Pydantic)
        planner_adapter_names = {}
        if profile_config.planner_adapter_names:
            for task_type_str, agent_name in profile_config.planner_adapter_names.items():
                task_type = TaskType[task_type_str.upper()]
                planner_adapter_names[task_type] = agent_name
        
        # Convert TaskType strings to enums for executor_adapter_names
        executor_adapter_names = {}
        if profile_config.executor_adapter_names:
            for task_type_str, agent_name in profile_config.executor_adapter_names.items():
                task_type = TaskType[task_type_str.upper()]
                executor_adapter_names[task_type] = agent_name
        
        # Convert TaskType strings to enums for aggregator_adapter_names
        aggregator_adapter_names = {}
        if profile_config.aggregator_adapter_names:
            for task_type_str, agent_name in profile_config.aggregator_adapter_names.items():
                task_type = TaskType[task_type_str.upper()]
                aggregator_adapter_names[task_type] = agent_name
        
        # Create AgentBlueprint instance with validated data
        blueprint = AgentBlueprint(
            name=profile_config.name,
            description=profile_config.description or f"Agent profile: {profile_name}",
            root_planner_adapter_name=profile_config.root_planner_adapter_name,
            root_aggregator_adapter_name=profile_config.root_aggregator_adapter_name,
            planner_adapter_names=planner_adapter_names,
            executor_adapter_names=executor_adapter_names,
            aggregator_adapter_names=aggregator_adapter_names,
            atomizer_adapter_name=profile_config.atomizer_adapter_name or "DefaultAtomizer",
            aggregator_adapter_name=profile_config.aggregator_adapter_name or "DefaultAggregator",
            plan_modifier_adapter_name=profile_config.plan_modifier_adapter_name or "PlanModifier",
            default_planner_adapter_name=profile_config.default_planner_adapter_name,
            default_executor_adapter_name=profile_config.default_executor_adapter_name,
            default_node_agent_name_prefix=profile_config.default_node_agent_name_prefix
        )
        
        # Log root-specific configurations if present
        if blueprint.root_planner_adapter_name:
            logger.info(f"  - Root planner: {blueprint.root_planner_adapter_name}")
        if blueprint.root_aggregator_adapter_name:
            logger.info(f"  - Root aggregator: {blueprint.root_aggregator_adapter_name}")
                
        logger.info(f"✅ Successfully loaded profile '{profile_name}' with {len(planner_adapter_names)} planner mappings, {len(executor_adapter_names)} executor mappings, and {len(aggregator_adapter_names)} aggregator mappings")
        return blueprint
    
    def get_validated_profile_config(self, profile_name: str) -> ProfileYAMLConfig:
        """
        Get the validated Pydantic profile configuration.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            ProfileYAMLConfig instance
        """
        if profile_name not in self._profile_cache:
            # This will load and cache the profile
            self.load_profile(profile_name)
        return self._profile_cache[profile_name]
    
    def load_all_profiles(self) -> Dict[str, AgentBlueprint]:
        """
        Load all available profiles.
        
        Returns:
            Dictionary mapping profile names to AgentBlueprint instances
        """
        profiles = {}
        available_profiles = self.list_available_profiles()
        
        for profile_name in available_profiles:
            try:
                profiles[profile_name] = self.load_profile(profile_name)
            except Exception as e:
                logger.error(f"Failed to load profile '{profile_name}': {e}")
                # Continue loading other profiles
        
        logger.info(f"Loaded {len(profiles)} agent profiles: {list(profiles.keys())}")
        return profiles


def load_profile(profile_name: str, profiles_dir: Optional[Path] = None) -> AgentBlueprint:
    """
    Convenience function to load a single profile.
    
    Args:
        profile_name: Name of the profile to load
        profiles_dir: Optional custom profiles directory
        
    Returns:
        AgentBlueprint instance
    """
    loader = ProfileLoader(profiles_dir)
    return loader.load_profile(profile_name)


def list_profiles(profiles_dir: Optional[Path] = None) -> List[str]:
    """
    Convenience function to list available profiles.
    
    Args:
        profiles_dir: Optional custom profiles directory
        
    Returns:
        List of available profile names
    """
    loader = ProfileLoader(profiles_dir)
    return loader.list_available_profiles() 