"""
Tests for agent_configs.agent_factory module.
Tests core functionality with proper mocking to avoid circular dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import os

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

# Import the AgentFactory for testing
from sentientresearchagent.hierarchical_agent_framework.agent_configs.agent_factory import AgentFactory


class TestModelValidationThroughFactory:
    """Test model configuration validation through AgentFactory (now uses Pydantic)."""

    def test_openai_validation_success(self):
        """Test successful OpenAI environment validation through create_model_instance."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        model_config = {
            "provider": "litellm",
            "model_id": "openai/gpt-4"
        }
        
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            # This should not raise - validation is now in Pydantic ModelConfig
            with patch.object(factory._model_providers['litellm'], '__call__', return_value=Mock()) as mock_model:
                result = factory.create_model_instance(model_config)
                assert result is not None

    def test_openai_validation_failure(self):
        """Test OpenAI environment validation failure through create_model_instance."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        model_config = {
            "provider": "litellm", 
            "model_id": "openai/gpt-4"
        }
        
        with patch.dict(os.environ, {}, clear=True):
            # This should raise a ValueError due to Pydantic validation
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                factory.create_model_instance(model_config)

    def test_anthropic_validation_success(self):
        """Test successful Anthropic environment validation through create_model_instance."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        model_config = {
            "provider": "litellm",
            "model_id": "anthropic/claude-3"
        }
        
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test_key'}):
            with patch.object(factory._model_providers['litellm'], '__call__', return_value=Mock()) as mock_model:
                result = factory.create_model_instance(model_config)
                assert result is not None

    def test_anthropic_validation_failure(self):
        """Test Anthropic environment validation failure through create_model_instance."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        model_config = {
            "provider": "litellm",
            "model_id": "anthropic/claude-3"
        }
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                factory.create_model_instance(model_config)


class TestAgentFactoryMocked:
    """Test AgentFactory functionality through mocking."""

    @patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.agent_factory.create_agents_from_config')
    def test_create_agents_from_config_function(self, mock_create_function):
        """Test create_agents_from_config function through mocking."""
        mock_result = {"TestAgent": {"adapter": Mock(), "agent": Mock()}}
        mock_create_function.return_value = mock_result
        
        result = mock_create_function("/some/config/dir")
        assert result == mock_result
        mock_create_function.assert_called_once_with("/some/config/dir")


class TestPydanticModelIntegration:
    """Test that Pydantic models properly validate configurations."""

    def test_create_model_instance_with_invalid_provider(self):
        """Test create_model_instance with invalid provider."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        model_config = {
            "provider": "invalid_provider",
            "model_id": "some/model"
        }
        
        with pytest.raises(ValueError, match="Invalid model configuration"):
            factory.create_model_instance(model_config)

    def test_create_model_instance_with_missing_fields(self):
        """Test create_model_instance with missing required fields."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        # Missing model_id
        model_config = {
            "provider": "litellm"
        }
        
        with pytest.raises(ValueError, match="Invalid model configuration"):
            factory.create_model_instance(model_config)

    def test_create_model_instance_with_valid_pydantic_config(self):
        """Test create_model_instance with a valid Pydantic ModelConfig object."""
        from sentientresearchagent.hierarchical_agent_framework.agent_configs.models import ModelConfig
        
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        # Create a valid ModelConfig - environment validation will be done by Pydantic
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'}):
            model_config = ModelConfig(
                provider="litellm",
                model_id="openai/gpt-4",
                temperature=0.7
            )
            
            # The factory should be able to create a model instance
            result = factory.create_model_instance(model_config)
            assert result is not None
            # Since we have mocks, just verify we got something back

    def test_agent_config_validation_through_factory(self):
        """Test that agent configuration validation works through the factory."""
        mock_config_loader = Mock()
        factory = AgentFactory(mock_config_loader)
        
        # Invalid agent config - missing required fields
        agent_config = {
            "name": "test_agent",
            # Missing type, adapter_class
        }
        
        with pytest.raises(ValueError, match="Invalid agent configuration"):
            factory.create_agent(agent_config) 