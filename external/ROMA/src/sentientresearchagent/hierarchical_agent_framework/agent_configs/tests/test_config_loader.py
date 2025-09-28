"""
Optimized tests for agent_configs.config_loader module.
Tests AgentConfigLoader class and related functions using ConfigFactory for clean, maintainable tests.
"""

import pytest
import os
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import tempfile
from omegaconf import DictConfig, OmegaConf

from sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader import (
    AgentConfigLoader, load_agent_configs
)


# ============================================================================
# AGENT CONFIG LOADER CORE TESTS
# ============================================================================

class TestAgentConfigLoader:
    """Test AgentConfigLoader class with comprehensive coverage."""

    def test_init_with_config_dir(self, mock_config_directory):
        """Test initialization with provided config directory."""
        loader = AgentConfigLoader(mock_config_directory)
        
        assert loader.config_dir == mock_config_directory
        assert loader.agents_config_file == mock_config_directory / "agents.yaml"

    def test_init_without_config_dir(self):
        """Test initialization without config directory (uses default)."""
        with patch.object(Path, 'exists', return_value=True):
            loader = AgentConfigLoader()
            
            # Should use the directory containing the config_loader.py file
            assert loader.config_dir is not None

    def test_init_config_dir_not_exists(self, tmp_path):
        """Test initialization fails when config directory doesn't exist."""
        non_existent_dir = tmp_path / "non_existent"
        
        with pytest.raises(FileNotFoundError, match="Config directory not found"):
            AgentConfigLoader(non_existent_dir)

    def test_init_agents_file_not_exists(self, tmp_path):
        """Test initialization fails when agents.yaml doesn't exist."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        with pytest.raises(FileNotFoundError, match="Agents config file not found"):
            AgentConfigLoader(config_dir)


# ============================================================================
# CONFIG LOADING TESTS
# ============================================================================

class TestConfigLoading:
    """Test configuration loading functionality."""

    def test_load_config_success(self, mock_config_directory, mock_environment_variables):
        """Test successful config loading."""
        loader = AgentConfigLoader(mock_config_directory)
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger'):
            config = loader.load_config()
        
        assert isinstance(config, DictConfig)
        assert 'agents' in config
        assert len(config.agents) > 0

    def test_load_config_validation_error(self, mock_config_directory):
        """Test config loading with validation error."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Mock validation to fail by mocking validate_agents_yaml
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.validate_agents_yaml') as mock_validate:
            mock_validate.side_effect = ValueError("Test validation error")
            
            with pytest.raises(ValueError, match="Test validation error"):
                loader.load_config()

    def test_load_config_file_error(self, tmp_path):
        """Test config loading with file reading error."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create an invalid YAML file
        agents_file = config_dir / "agents.yaml"
        agents_file.write_text("invalid: yaml: content: [unclosed")
        
        loader = AgentConfigLoader(config_dir)
        
        with pytest.raises(Exception):  # Should raise YAML parsing error
            loader.load_config()


# ============================================================================
# PROMPT RESOLUTION TESTS
# ============================================================================

class TestPromptResolution:
    """Test prompt resolution functionality."""

    @pytest.mark.parametrize("prompt_source,expected_content", [
        ("test.prompts.PLANNER_PROMPT", "Planner system message"),
        ("test.prompts.EXECUTOR_PROMPT", "Executor system message"),
        ("test.prompts.COMPLEX_PROMPT", "Complex prompt for testing"),
    ])
    def test_resolve_prompt_success(self, mock_config_directory, mock_prompt_module, prompt_source, expected_content):
        """Test successful prompt resolution."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Set up the mock module with the expected attribute
        setattr(mock_prompt_module, prompt_source.split('.')[-1], expected_content)
        
        with patch('importlib.import_module', return_value=mock_prompt_module):
            result = loader.resolve_prompt(prompt_source)
            
        assert result == expected_content

    @pytest.mark.parametrize("invalid_prompt_source", [
        "invalid_format",
        "",
        "single_word",
    ])
    def test_resolve_prompt_invalid_format(self, mock_config_directory, invalid_prompt_source):
        """Test prompt resolution with invalid format."""
        loader = AgentConfigLoader(mock_config_directory)
        
        with pytest.raises(ValueError, match="Invalid prompt source format"):
            loader.resolve_prompt(invalid_prompt_source)

    def test_resolve_prompt_module_not_found(self, mock_config_directory):
        """Test prompt resolution with module not found."""
        loader = AgentConfigLoader(mock_config_directory)
        
        with patch('importlib.import_module', side_effect=ModuleNotFoundError("No module named 'nonexistent'")):
            with pytest.raises(ModuleNotFoundError, match="No module named"):
                loader.resolve_prompt("nonexistent.module.PROMPT")

    def test_resolve_prompt_attribute_not_found(self, mock_config_directory):
        """Test prompt resolution with attribute not found."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Create a module mock that doesn't have the attribute
        mock_module = type('TestModule', (), {})()
        
        with patch('importlib.import_module', return_value=mock_module):
            with pytest.raises(AttributeError, match="has no attribute"):
                loader.resolve_prompt("test.prompts.NONEXISTENT_PROMPT")

    def test_resolve_prompt_not_string(self, mock_config_directory, mock_prompt_module):
        """Test prompt resolution with non-string attribute."""
        loader = AgentConfigLoader(mock_config_directory)
        mock_prompt_module.NOT_A_STRING = 123  # Non-string attribute
        
        with patch('importlib.import_module', return_value=mock_prompt_module):
            with pytest.raises(TypeError, match="is not a string"):
                loader.resolve_prompt("test.prompts.NOT_A_STRING")


# ============================================================================
# VALIDATION TESTS
# ============================================================================

class TestConfigValidation:
    """Test configuration validation functionality."""

    def test_validate_agent_config_invalid(self, mock_config_directory):
        """Test validation of invalid agent config."""
        loader = AgentConfigLoader(mock_config_directory)
        
        invalid_config = {
            "name": "TestAgent",
            "type": "invalid_type",  # Invalid type
            "adapter_class": "TestAdapter"
        }
        
        errors = loader.validate_agent_config(invalid_config)
        assert len(errors) > 0

    def test_validate_agent_config_with_prompt_resolution(self, mock_config_directory, config_factory, mock_environment_variables):
        """Test agent config validation with prompt resolution."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Create a valid minimal config that won't trigger model validation
        valid_config = {
            "name": "TestAgent",
            "type": "custom_search",
            "adapter_class": "OpenAICustomSearchAdapter",
            "enabled": True
        }
        
        with patch.object(loader, 'resolve_prompt', return_value="Resolved prompt"):
            errors = loader.validate_agent_config(valid_config)
            
        assert errors == []

    def test_validate_config_success(self, mock_config_directory, config_factory, mock_environment_variables):
        """Test successful config validation."""
        loader = AgentConfigLoader(mock_config_directory)
        
        config_data = config_factory.agents_yaml_config()
        config = OmegaConf.create(config_data)
        
        # Mock prompt resolution to succeed for all agents
        with patch.object(loader, 'resolve_prompt', return_value="Mock prompt"):
            result = loader.validate_config(config)
            
        assert result["valid"] is True
        assert result["agent_count"] == 2
        assert result["enabled_count"] >= 0
        assert result["errors"] == []

    def test_validate_config_with_errors(self, mock_config_directory, config_factory):
        """Test config validation with errors."""
        loader = AgentConfigLoader(mock_config_directory)
        
        config_data = config_factory.agents_yaml_config()
        config = OmegaConf.create(config_data)
        
        # Mock validation to return errors
        with patch.object(loader, 'validate_agent_config', return_value=["Validation error"]):
            result = loader.validate_config(config)
            
        assert result["valid"] is False
        assert len(result["errors"]) > 0

    def test_validate_config_duplicate_names(self, mock_config_directory, config_factory, mock_environment_variables):
        """Test config validation with duplicate agent names - handled by Pydantic."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Create config with duplicate names using custom_search agents to avoid model validation
        duplicate_agents = [
            {
                "name": "DuplicateAgent",
                "type": "custom_search",
                "adapter_class": "OpenAICustomSearchAdapter",
                "description": "First duplicate",
                "enabled": True
            },
            {
                "name": "DuplicateAgent", 
                "type": "custom_search",
                "adapter_class": "GeminiCustomSearchAdapter",
                "description": "Second duplicate",
                "enabled": True
            }
        ]
        config_data = config_factory.agents_yaml_config(agents=duplicate_agents)
        config = OmegaConf.create(config_data)
        
        # Pydantic validation should catch duplicates before individual agent validation
        result = loader.validate_config(config)
            
        assert result["valid"] is False
        assert any("duplicate" in error.lower() for error in result["errors"])

    def test_validate_config_enabled_disabled_count(self, mock_config_directory, config_factory):
        """Test config validation counts enabled/disabled agents correctly."""
        loader = AgentConfigLoader(mock_config_directory)
        
        # Create config with enabled and disabled agents
        agents = [
            config_factory.agent_config(name="EnabledAgent", enabled=True),
            config_factory.agent_config(name="DisabledAgent", enabled=False),
            config_factory.agent_config(name="AnotherEnabledAgent", enabled=True),
        ]
        config_data = config_factory.agents_yaml_config(agents=agents)
        config = OmegaConf.create(config_data)
        
        with patch.object(loader, 'validate_agent_config', return_value=[]):
            result = loader.validate_config(config)
            
        assert result["agent_count"] == 3
        assert result["enabled_count"] == 2
        assert result["disabled_count"] == 1


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================

class TestLoadAgentConfigs:
    """Test load_agent_configs convenience function."""

    def test_load_agent_configs_validation_failure(self, mock_config_directory):
        """Test config loading failure due to validation."""
        # Mock environment variables to be missing to trigger validation error
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="validation errors"):
                load_agent_configs(mock_config_directory)

    def test_load_agent_configs_with_warnings(self, mock_config_directory, mock_environment_variables):
        """Test config loading with warnings."""
        with patch.object(AgentConfigLoader, 'validate_config') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "errors": [],
                "warnings": ["Test warning"],
                "agent_count": 1,
                "enabled_count": 1,
                "disabled_count": 0
            }
            
            with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger') as mock_logger:
                config = load_agent_configs(mock_config_directory)
                
                mock_logger.warning.assert_called()
                assert isinstance(config, DictConfig)

    def test_load_agent_configs_default_dir(self, mock_environment_variables):
        """Test config loading with default directory."""
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.AgentConfigLoader') as mock_loader_class:
            mock_loader = Mock()
            mock_config = Mock()
            mock_loader_class.return_value = mock_loader
            mock_loader.load_config.return_value = mock_config
            mock_loader.validate_config.return_value = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "enabled_count": 1,
                "disabled_count": 0
            }
            
            result = load_agent_configs()
            
            mock_loader_class.assert_called_once_with(None)
            mock_loader.load_config.assert_called_once()
            assert result == mock_config


# ============================================================================
# INTEGRATION AND ERROR HANDLING TESTS
# ============================================================================

class TestConfigLoaderIntegration:
    """Integration tests for AgentConfigLoader."""

    def test_config_loader_error_handling(self, tmp_path):
        """Test error handling in various scenarios."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create a corrupted YAML file
        agents_file = config_dir / "agents.yaml"
        agents_file.write_text("agents:\n  - name: Agent\n    invalid_yaml: [unclosed")
        
        loader = AgentConfigLoader(config_dir)
        
        # Should handle YAML parsing errors gracefully
        with pytest.raises(Exception):
            loader.load_config()

    @pytest.mark.parametrize("input_path,prompt_name,expected_module", [
        ("prompts.planner_prompts", "DEFAULT_PROMPT", "sentientresearchagent.hierarchical_agent_framework.agent_configs.prompts.planner_prompts"),
        ("prompts.executor", "SYSTEM_MESSAGE", "sentientresearchagent.hierarchical_agent_framework.agent_configs.prompts.executor"),
        ("custom.prompts", "COMPLEX_PROMPT", "sentientresearchagent.hierarchical_agent_framework.agent_configs.custom.prompts"),
    ])
    def test_prompt_resolution_module_paths(self, mock_config_directory, mock_prompt_module, input_path, prompt_name, expected_module):
        """Test prompt resolution constructs correct module paths."""
        loader = AgentConfigLoader(mock_config_directory)
        prompt_source = f"{input_path}.{prompt_name}"
        
        # Mock the expected attribute
        setattr(mock_prompt_module, prompt_name, "Test prompt content")
        
        with patch('importlib.import_module', return_value=mock_prompt_module) as mock_import:
            result = loader.resolve_prompt(prompt_source)
            
            mock_import.assert_called_once_with(expected_module)
            assert result == "Test prompt content"

    @pytest.mark.parametrize("agent_config_data", [
        # Missing required fields
        {"name": "Agent"},
        {"type": "planner"},
        {"adapter_class": "PlannerAdapter"},
        # Invalid field values
        {"name": "", "type": "planner", "adapter_class": "PlannerAdapter"},
        {"name": "Agent", "type": "invalid_type", "adapter_class": "PlannerAdapter"},
    ])
    def test_config_validation_edge_cases(self, mock_config_directory, agent_config_data):
        """Test config validation edge cases."""
        loader = AgentConfigLoader(mock_config_directory)
        
        errors = loader.validate_agent_config(agent_config_data)
        
        # Should have validation errors for all these cases
        assert len(errors) > 0

    def test_config_loading_with_complex_structure(self, tmp_path, config_factory, mock_environment_variables):
        """Test loading config with complex nested structure."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create complex agents configuration
        complex_agents = [
            config_factory.agent_config(
                name="ComplexPlanner",
                agent_type="planner",
                description="Complex planner with all features",
                tools=[
                    config_factory.tool_config(name="web_search"),
                    config_factory.tool_config(name="calculator", params={"precision": 10}),
                ]
            ),
            config_factory.agent_config(
                name="ComplexExecutor",
                agent_type="executor",
                adapter_class="ExecutorAdapter",
                prompt_source="test.prompts.EXECUTOR_PROMPT",
                agno_params=config_factory.agno_params(reasoning=True, debug_mode=True),
            )
        ]
        
        config_data = config_factory.agents_yaml_config(
            agents=complex_agents,
            metadata={"version": "2.0.0", "description": "Complex test config"}
        )
        
        # Save to file
        agents_file = config_dir / "agents.yaml"
        omegaconf_config = OmegaConf.create(config_data)
        OmegaConf.save(omegaconf_config, agents_file)
        
        # Test loading
        loader = AgentConfigLoader(config_dir)
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger'):
            config = loader.load_config()
            
        assert isinstance(config, DictConfig)
        assert len(config.agents) == 2
        assert config.metadata.version == "2.0.0"

    def test_concurrent_config_loading(self, mock_config_directory, mock_environment_variables):
        """Test that config loading is thread-safe."""
        import threading
        import time
        
        results = []
        errors = []
        
        def load_config_worker():
            try:
                loader = AgentConfigLoader(mock_config_directory)
                with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger'):
                    config = loader.load_config()
                results.append(config)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=load_config_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 5
        
        # All results should be similar
        for result in results:
            assert isinstance(result, DictConfig)
            assert 'agents' in result


# ============================================================================
# PERFORMANCE AND OPTIMIZATION TESTS
# ============================================================================

class TestConfigLoaderPerformance:
    """Test configuration loader performance and optimization."""

    def test_config_caching_behavior(self, mock_config_directory, mock_environment_variables):
        """Test that repeated config loads don't unnecessarily re-parse."""
        loader = AgentConfigLoader(mock_config_directory)
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger'):
            # Load config multiple times
            config1 = loader.load_config()
            config2 = loader.load_config()
            
        # Should return equivalent configs
        assert config1.agents[0].name == config2.agents[0].name

    def test_large_config_handling(self, tmp_path, config_factory, mock_environment_variables):
        """Test handling of large configuration files."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create a large config with many agents
        large_agents = []
        for i in range(50):  # Create 50 agents
            agent_type = "planner" if i % 2 == 0 else "executor"
            adapter_class = "PlannerAdapter" if agent_type == "planner" else "ExecutorAdapter"
            prompt_source = f"test.prompts.{agent_type.upper()}_PROMPT"
            
            large_agents.append(config_factory.agent_config(
                name=f"Agent{i:02d}",
                agent_type=agent_type,
                adapter_class=adapter_class,
                prompt_source=prompt_source,
                description=f"Generated agent number {i}"
            ))
        
        config_data = config_factory.agents_yaml_config(agents=large_agents)
        
        # Save to file
        agents_file = config_dir / "agents.yaml"
        omegaconf_config = OmegaConf.create(config_data)
        OmegaConf.save(omegaconf_config, agents_file)
        
        # Test loading large config
        loader = AgentConfigLoader(config_dir)
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.config_loader.logger'):
            config = loader.load_config()
            
        assert isinstance(config, DictConfig)
        assert len(config.agents) == 50
        
        # Test validation performance with large config
        with patch.object(loader, 'resolve_prompt', return_value="Mock prompt"):
            validation_result = loader.validate_config(config)
            
        assert validation_result["valid"] is True
        assert validation_result["agent_count"] == 50 