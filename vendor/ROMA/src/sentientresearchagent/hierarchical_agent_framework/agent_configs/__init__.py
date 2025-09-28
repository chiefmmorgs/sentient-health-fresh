"""
Agent Configuration System

This module provides a centralized, YAML-based configuration system for agents.
Prompts are defined in Python files for better IDE support and maintainability.
"""

from .config_loader import load_agent_configs, AgentConfigLoader

# Note: AgentFactory is imported separately to avoid circular imports
# Use: from .agent_factory import AgentFactory

__all__ = [
    'load_agent_configs',
    'AgentConfigLoader'
] 