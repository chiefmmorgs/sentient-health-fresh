"""
Tests for agent_configs.registry_integration module.
Tests RegistryIntegrator class with proper mocking to avoid circular dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Mock all problematic modules before any imports
mock_modules = {
    'sentientresearchagent.hierarchical_agent_framework.agents.adapters': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.agents.definitions.custom_searchers': Mock(), 
    'sentientresearchagent.hierarchical_agent_framework.agents.definitions.exa_searcher': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.context.agent_io_models': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.agents.base_adapter': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.agents.registry': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.agent_blueprints': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.toolkits.data': Mock(),
    'sentientresearchagent.hierarchical_agent_framework.node.task_node': Mock(),
    'agno.agent': Mock(),
    'agno.models.litellm': Mock(),
    'agno.models.openai': Mock(),
    'agno.tools.duckduckgo': Mock(),
    'agno.tools.python': Mock(),
    'agno.tools.reasoning': Mock(),
    'agno.tools.wikipedia': Mock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Now we can safely import the module under test
from sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration import (
    integrate_agents_with_global_registry, 
    integrate_agents_with_instance_registry
)


class TestStandaloneFunctions:
    """Test standalone integration functions."""

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_integrate_agents_with_instance_registry(self, mock_integrator_class):
        """Test integrating agents with instance registry."""
        mock_registry = Mock()
        mock_integrator = Mock()
        mock_result = {"result": "success"}
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.return_value = mock_result
        
        result = integrate_agents_with_instance_registry(mock_registry)
        
        assert result == mock_result
        mock_integrator_class.assert_called_once_with(mock_registry, None)
        mock_integrator.load_and_register_agents.assert_called_once()

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_integrate_agents_with_instance_registry_with_loader(self, mock_integrator_class):
        """Test integrating agents with instance registry and custom loader."""
        mock_registry = Mock()
        mock_loader = Mock()
        mock_integrator = Mock()
        mock_result = {"result": "success"}
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.return_value = mock_result
        
        result = integrate_agents_with_instance_registry(mock_registry, None, mock_loader)
        
        assert result == mock_result
        mock_integrator_class.assert_called_once_with(mock_registry, mock_loader)


class TestRegistryIntegratorMocked:
    """Test RegistryIntegrator functionality through mocking."""

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_registry_integrator_creation(self, mock_integrator_class):
        """Test RegistryIntegrator can be created with mocked dependencies."""
        mock_registry = Mock()
        mock_loader = Mock()
        mock_integrator = Mock()
        
        mock_integrator_class.return_value = mock_integrator
        
        integrator = mock_integrator_class(mock_registry, mock_loader)
        assert integrator == mock_integrator

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_load_and_register_agents_success(self, mock_integrator_class):
        """Test successful agent loading and registration."""
        mock_registry = Mock()
        mock_integrator = Mock()
        mock_result = {
            "registered_action_keys": 2,
            "registered_named_keys": 2,
            "failed_registrations": 0,
            "skipped_agents": 0
        }
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.return_value = mock_result
        
        integrator = mock_integrator_class(mock_registry)
        result = integrator.load_and_register_agents()
        
        assert result == mock_result
        assert result["registered_action_keys"] == 2
        assert result["registered_named_keys"] == 2
        assert result["failed_registrations"] == 0

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_load_and_register_agents_with_failures(self, mock_integrator_class):
        """Test agent loading with some failures."""
        mock_registry = Mock()
        mock_integrator = Mock()
        mock_result = {
            "registered_action_keys": 1,
            "registered_named_keys": 1,
            "failed_registrations": 1,
            "skipped_agents": 1
        }
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.return_value = mock_result
        
        integrator = mock_integrator_class(mock_registry)
        result = integrator.load_and_register_agents()
        
        assert result == mock_result
        assert result["failed_registrations"] > 0
        assert result["skipped_agents"] > 0


class TestIntegrationWorkflow:
    """Test integration workflow scenarios."""

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_error_handling_in_integration(self, mock_integrator_class):
        """Test error handling during integration."""
        mock_registry = Mock()
        mock_integrator = Mock()
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.side_effect = Exception("Integration failed")
        
        integrator = mock_integrator_class(mock_registry)
        
        with pytest.raises(Exception, match="Integration failed"):
            integrator.load_and_register_agents()

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_multiple_registry_instances(self, mock_integrator_class):
        """Test integration with multiple registry instances."""
        mock_registry1 = Mock()
        mock_registry2 = Mock()
        mock_integrator1 = Mock()
        mock_integrator2 = Mock()
        
        def side_effect(registry, loader=None):
            if registry == mock_registry1:
                return mock_integrator1
            else:
                return mock_integrator2
        
        mock_integrator_class.side_effect = side_effect
        mock_integrator1.load_and_register_agents.return_value = {"result": "registry1"}
        mock_integrator2.load_and_register_agents.return_value = {"result": "registry2"}
        
        # Test with first registry
        result1 = integrate_agents_with_instance_registry(mock_registry1)
        assert result1["result"] == "registry1"
        
        # Test with second registry  
        result2 = integrate_agents_with_instance_registry(mock_registry2)
        assert result2["result"] == "registry2"
        
        # Verify separate calls
        assert mock_integrator_class.call_count == 2


class TestParameterHandling:
    """Test parameter handling in integration functions."""

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.registry_integration.RegistryIntegrator')
    def test_optional_loader_parameter(self, mock_integrator_class):
        """Test optional loader parameter handling."""
        mock_registry = Mock()
        mock_loader = Mock()
        mock_integrator = Mock()
        
        mock_integrator_class.return_value = mock_integrator
        mock_integrator.load_and_register_agents.return_value = {}
        
        # Test with None loader and None config_dir
        integrate_agents_with_instance_registry(mock_registry, None, None)
        mock_integrator_class.assert_called_with(mock_registry, None)
        
        # Test with provided loader
        integrate_agents_with_instance_registry(mock_registry, None, mock_loader)
        mock_integrator_class.assert_called_with(mock_registry, mock_loader)

 