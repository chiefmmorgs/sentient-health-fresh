"""
Configuration module for the Sentient Research Agent.

This module centralizes the loading, validation, and access of configuration
settings for the entire application, leveraging Pydantic for robust data modeling.

Exports:
    - SentientConfig: The main Pydantic model for all configuration settings.
    - WebServerConfig, LLMConfig, CacheConfig, ExecutionConfig, LoggingConfig, AgentConfig:
      Sub-models for specific configuration sections.
    - load_config: Function to load configuration from files and environment variables.
    - find_config_file: Utility to automatically locate the configuration file.
    - auto_load_config: Utility to automatically load configuration.
    - validate_config: Utility for comprehensive configuration validation.
    - get_config_info: Utility to get information about current configuration.
"""
from .config import (
    SentientConfig,
    WebServerConfig,
    LLMConfig,
    CacheConfig,
    ExecutionConfig,
    LoggingConfig,
    AgentConfig,
    load_config
)

from .config_utils import (
    find_config_file,
    auto_load_config,
    validate_config,
    get_config_info
)

__all__ = [
    "SentientConfig",
    "WebServerConfig",
    "LLMConfig",
    "CacheConfig",
    "ExecutionConfig",
    "LoggingConfig",
    "AgentConfig",
    "load_config",
    "find_config_file",
    "auto_load_config",
    "validate_config",
    "get_config_info",
]
