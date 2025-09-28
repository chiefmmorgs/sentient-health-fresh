"""
Unified Configuration Manager for SentientResearchAgent.

This module provides a single source of truth for all configuration,
eliminating redundancies and ensuring consistency across the system.
"""

from typing import Optional, Dict, Any, Union
from pathlib import Path
from loguru import logger
import threading
from contextlib import contextmanager

from .config import SentientConfig, load_config, ExecutionConfig


class ConfigurationManager:
    """
    Singleton configuration manager that ensures a single source of truth.
    
    This manager:
    1. Loads configuration once from file/env
    2. Provides a consistent interface for all components
    3. Handles overrides in a predictable manner
    4. Ensures all components see the same configuration
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._config: Optional[SentientConfig] = None
        self._config_path: Optional[Path] = None
        self._overrides: Dict[str, Any] = {}
        self._frozen = False
        self._initialized = True
        
    def load(self, config_path: Optional[Union[str, Path]] = None, use_env: bool = True) -> SentientConfig:
        """
        Load configuration from file and environment.
        
        Args:
            config_path: Optional path to config file
            use_env: Whether to load from environment variables
            
        Returns:
            Loaded configuration
        """
        if self._frozen:
            raise RuntimeError("Configuration is frozen and cannot be reloaded")
            
        logger.info("Loading configuration...")
        
        # Load base configuration
        self._config = load_config(config_file=config_path, use_env=use_env)
        self._config_path = Path(config_path) if config_path else None
        
        # Apply any stored overrides
        self._apply_overrides()
        
        logger.info(f"Configuration loaded successfully from {self._config_path or 'defaults'}")
        return self._config
    
    def get_config(self) -> SentientConfig:
        """
        Get the current configuration.
        
        Returns:
            Current configuration instance
            
        Raises:
            RuntimeError: If configuration not loaded
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load() first.")
        return self._config
    
    def override(self, **kwargs) -> None:
        """
        Apply configuration overrides.
        
        These overrides take precedence over file/env configuration
        but are applied consistently to all components.
        
        Args:
            **kwargs: Configuration overrides as key=value pairs
        """
        if self._frozen:
            raise RuntimeError("Configuration is frozen and cannot be modified")
            
        # Store overrides
        for key, value in kwargs.items():
            self._overrides[key] = value
            
        # Apply to current config if loaded
        if self._config:
            self._apply_overrides()
    
    @contextmanager
    def temporary_override(self, **kwargs):
        """
        Context manager for temporary configuration overrides.
        
        Args:
            **kwargs: Temporary overrides
            
        Example:
            with config_manager.temporary_override(skip_atomization=True):
                # Execute with temporary config
                pass
        """
        if self._frozen:
            raise RuntimeError("Configuration is frozen and cannot be modified")
            
        # Save current state
        original_overrides = self._overrides.copy()
        original_config = self._config.dict() if self._config else None
        
        try:
            # Apply temporary overrides
            self.override(**kwargs)
            yield self._config
        finally:
            # Restore original state
            self._overrides = original_overrides
            if original_config and self._config:
                # Restore config from saved state
                self._config = SentientConfig(**original_config)
                self._apply_overrides()
    
    def freeze(self) -> None:
        """
        Freeze configuration to prevent further modifications.
        
        This ensures configuration remains consistent during execution.
        """
        self._frozen = True
        logger.info("Configuration frozen - no further modifications allowed")
    
    def unfreeze(self) -> None:
        """Allow configuration modifications again."""
        self._frozen = False
        logger.info("Configuration unfrozen - modifications allowed")
    
    def _apply_overrides(self) -> None:
        """Apply stored overrides to configuration."""
        if not self._config:
            return
            
        for key, value in self._overrides.items():
            # Handle nested paths like "execution.skip_atomization"
            if '.' in key:
                section, attr = key.split('.', 1)
                if hasattr(self._config, section):
                    section_obj = getattr(self._config, section)
                    if hasattr(section_obj, attr):
                        setattr(section_obj, attr, value)
                        logger.debug(f"Applied override: {key} = {value}")
            else:
                # Top-level attribute
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                    logger.debug(f"Applied override: {key} = {value}")
    
    def get_execution_config(self) -> ExecutionConfig:
        """Get execution-specific configuration."""
        if not self._config:
            raise RuntimeError("Configuration not loaded")
        return self._config.execution
    
    def get_node_processor_config(self) -> Dict[str, Any]:
        """
        Get configuration for NodeProcessor.
        
        This centralizes the logic for creating NodeProcessor config
        from the main configuration.
        """
        if not self._config:
            raise RuntimeError("Configuration not loaded")
            
        exec_config = self._config.execution
        
        return {
            "enable_hitl": exec_config.enable_hitl,
            "max_planning_layer": exec_config.max_recursion_depth,
            "skip_atomization": exec_config.skip_atomization,
            "hitl_root_plan_only": exec_config.hitl_root_plan_only,
            "force_root_node_planning": exec_config.force_root_node_planning,
            "enable_hitl_after_plan_generation": exec_config.hitl_after_plan_generation if not exec_config.hitl_root_plan_only else True,
            "enable_hitl_after_modified_plan": exec_config.hitl_after_modified_plan if not exec_config.hitl_root_plan_only else True,
            "enable_hitl_after_atomizer": exec_config.hitl_after_atomizer if not exec_config.hitl_root_plan_only else False,
            "enable_hitl_before_execute": exec_config.hitl_before_execute if not exec_config.hitl_root_plan_only else False,
            "optimization_level": exec_config.optimization_level,
            "execution_strategy": exec_config.execution_strategy,
            "knowledge_store_batch_size": exec_config.knowledge_store_batch_size,
            "broadcast_mode": exec_config.broadcast_mode,
            "enable_update_coalescing": exec_config.enable_update_coalescing,
            "update_coalescing_window_ms": exec_config.update_coalescing_window_ms,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if not self._config:
            raise RuntimeError("Configuration not loaded")
        return self._config.dict()


# Global instance
_config_manager = ConfigurationManager()


# Convenience functions for backward compatibility
def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance."""
    return _config_manager


def load_unified_config(config_path: Optional[Union[str, Path]] = None) -> SentientConfig:
    """
    Load configuration using the unified manager.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Loaded configuration
    """
    return _config_manager.load(config_path)


def get_config() -> SentientConfig:
    """Get current configuration."""
    return _config_manager.get_config()


def override_config(**kwargs) -> None:
    """Apply configuration overrides."""
    _config_manager.override(**kwargs)