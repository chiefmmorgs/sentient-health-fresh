"""
Agent Configuration Loader

Loads agent configurations from YAML files with comprehensive Pydantic validation.
Leverages structured Pydantic models for type safety and validation.
"""

import os
import importlib
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
from .models import validate_agents_yaml, validate_agent_config, AgentConfig, AgentsYAMLConfig

try:
    from omegaconf import OmegaConf, DictConfig
except ImportError:
    logger.error("OmegaConf not installed. Please install with: pip install omegaconf>=2.3.0")
    raise


class AgentConfigLoader:
    """Loads and validates agent configurations from YAML files with comprehensive Pydantic validation."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader with validation.
        
        Args:
            config_dir: Directory containing agent configuration files.
                       If None, uses the directory containing this file.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent
        
        self.config_dir = Path(config_dir)
        self.agents_config_file = self.config_dir / "agents.yaml"
        
        # Validate config directory exists
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")
        
        if not self.agents_config_file.exists():
            raise FileNotFoundError(f"Agents config file not found: {self.agents_config_file}")
        
        # Cache for validated configurations
        self._config_cache: Optional[AgentsYAMLConfig] = None
    
    def load_config(self) -> DictConfig:
        """
        Load and validate agent configuration from YAML with caching.
        
        Returns:
            OmegaConf DictConfig containing the validated agent configuration
        """
        try:
            logger.info(f"Loading agent configuration from: {self.agents_config_file}")
            config = OmegaConf.load(self.agents_config_file)
            
            # Validate using Pydantic model
            config_dict = OmegaConf.to_container(config, resolve=True)
            validated_config = validate_agents_yaml(config_dict)
            
            # Cache the validated config
            self._config_cache = validated_config
            
            logger.info(f"✅ Loaded and validated configuration for {len(validated_config.agents)} agents")
            
            # Convert back to DictConfig for compatibility
            return OmegaConf.create(validated_config.model_dump())
            
        except Exception as e:
            logger.error(f"Failed to load agent configuration: {e}")
            raise
    
    def get_validated_config(self) -> AgentsYAMLConfig:
        """
        Get the validated Pydantic configuration object.
        
        Returns:
            AgentsYAMLConfig instance
        """
        if self._config_cache is None:
            self.load_config()  # This will populate the cache
        return self._config_cache
    
    def resolve_prompt(self, prompt_source: str) -> str:
        """
        Resolve a prompt reference to the actual prompt string.
        
        Args:
            prompt_source: Dot-notation path to the prompt (e.g., "prompts.planner_prompts.PLANNER_SYSTEM_MESSAGE")
        
        Returns:
            The resolved prompt string
        """
        try:
            # Split the prompt source into module and attribute
            parts = prompt_source.split('.')
            if len(parts) < 2:
                raise ValueError(f"Invalid prompt source format: {prompt_source}")
            
            # Import the module relative to the agent_configs package
            module_path = '.'.join(parts[:-1])
            attribute_name = parts[-1]
            
            # Import relative to this package
            full_module_path = f"sentientresearchagent.hierarchical_agent_framework.agent_configs.{module_path}"
            module = importlib.import_module(full_module_path)
            
            # Get the prompt attribute
            if not hasattr(module, attribute_name):
                raise AttributeError(f"Module {module_path} has no attribute {attribute_name}")
            
            prompt = getattr(module, attribute_name)
            
            if not isinstance(prompt, str):
                raise TypeError(f"Prompt {prompt_source} is not a string, got {type(prompt)}")
            
            # Note: Folder context injection is now handled dynamically during execution
            # in base_adapter.py to support multi-project scenarios properly.
            # The injection at this level was causing issues because agents are created
            # globally before any specific project is active.
            
            return prompt
            
        except Exception as e:
            logger.error(f"Failed to resolve prompt {prompt_source}: {e}")
            raise
    
    def validate_agent_config(self, agent_config: Dict[str, Any]) -> List[str]:
        """
        Validate a single agent configuration using Pydantic with prompt resolution check.
        
        Args:
            agent_config: Agent configuration dictionary to validate
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        try:
            # Convert to dict if DictConfig
            if isinstance(agent_config, DictConfig):
                agent_config = OmegaConf.to_container(agent_config, resolve=True)
            
            # Validate using Pydantic model - this handles most validation
            validated = validate_agent_config(agent_config)
            
            # Additional validation for prompt resolution
            if validated.prompt_source:
                try:
                    self.resolve_prompt(validated.prompt_source)
                    logger.debug(f"✅ Prompt source validated: {validated.prompt_source}")
                except Exception as e:
                    errors.append(f"Invalid prompt_source '{validated.prompt_source}': {e}")
                    
        except Exception as e:
            # Parse Pydantic validation errors
            if hasattr(e, 'errors'):
                for error in e.errors():
                    field_path = ' -> '.join(str(loc) for loc in error['loc'])
                    errors.append(f"{field_path}: {error['msg']}")
            else:
                errors.append(str(e))
        
        return errors
    
    def validate_config(self, config: DictConfig) -> Dict[str, Any]:
        """
        Validate the entire agent configuration using Pydantic models.
        
        Args:
            config: Configuration to validate
        
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "agent_count": 0,
            "enabled_count": 0,
            "disabled_count": 0
        }
        
        try:
            # Convert to dict for Pydantic validation
            config_dict = OmegaConf.to_container(config, resolve=True)
            
            # Use Pydantic validation - this handles duplicate names, type checking, etc.
            validated_config = validate_agents_yaml(config_dict)
            
            # Count agents and their status
            validation_result["agent_count"] = len(validated_config.agents)
            
            for agent in validated_config.agents:
                if agent.enabled:
                    validation_result["enabled_count"] += 1
                else:
                    validation_result["disabled_count"] += 1
                
                # Additional validation for prompt resolution
                if agent.prompt_source:
                    try:
                        self.resolve_prompt(agent.prompt_source)
                        logger.debug(f"✅ Prompt validated for {agent.name}: {agent.prompt_source}")
                    except Exception as e:
                        validation_result["errors"].append(
                            f"Agent {agent.name}: Invalid prompt_source '{agent.prompt_source}': {e}"
                        )
            
            logger.info(f"✅ Configuration validated: {validation_result['enabled_count']} enabled, {validation_result['disabled_count']} disabled agents")
            
        except Exception as e:
            # Parse Pydantic validation errors
            if hasattr(e, 'errors'):
                for error in e.errors():
                    field_path = ' -> '.join(str(loc) for loc in error['loc'])
                    validation_result["errors"].append(f"{field_path}: {error['msg']}")
            else:
                validation_result["errors"].append(str(e))
        
        validation_result["valid"] = len(validation_result["errors"]) == 0
        
        return validation_result


def load_agent_configs(config_dir: Optional[Path] = None) -> DictConfig:
    """
    Convenience function to load agent configurations.
    
    Args:
        config_dir: Directory containing configuration files
    
    Returns:
        Loaded and validated configuration
    """
    loader = AgentConfigLoader(config_dir)
    config = loader.load_config()
    
    # Validate configuration
    validation = loader.validate_config(config)
    
    if not validation["valid"]:
        logger.error("Agent configuration validation failed:")
        for error in validation["errors"]:
            logger.error(f"  - {error}")
        raise ValueError("Invalid agent configuration")
    
    if validation["warnings"]:
        logger.warning("Agent configuration warnings:")
        for warning in validation["warnings"]:
            logger.warning(f"  - {warning}")
    
    logger.info(f"✅ Agent configuration validated: {validation['enabled_count']} enabled, {validation['disabled_count']} disabled")
    
    return config 