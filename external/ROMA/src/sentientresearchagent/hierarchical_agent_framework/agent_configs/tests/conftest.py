"""
Optimized pytest fixtures for agent_configs tests.
Provides clean, reusable mock data and fixtures with minimal dependencies.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock
import pytest
from omegaconf import OmegaConf, DictConfig


# ============================================================================
# GLOBAL MOCKS AND EXTERNAL DEPENDENCIES
# ============================================================================

@pytest.fixture(autouse=True)
def mock_external_dependencies():
    """Mock external dependencies to isolate tests."""
    mock_modules = {
        # Agno framework modules
        'agno.agent': Mock(),
        'agno.models.litellm': Mock(),
        'agno.models.openai': Mock(),
        'agno.tools.duckduckgo': Mock(),
        'agno.tools.python': Mock(),
        'agno.tools.reasoning': Mock(),
        'agno.tools.wikipedia': Mock(),
        
        # Internal agent framework modules
        'sentientresearchagent.hierarchical_agent_framework.agents.adapters': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.agents.definitions.custom_searchers': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.agents.definitions.exa_searcher': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.context.agent_io_models': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.agents.base_adapter': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.agents.registry': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.agent_blueprints': Mock(),
        'sentientresearchagent.hierarchical_agent_framework.toolkits.data': Mock(),
    }
    
    with patch.dict('sys.modules', mock_modules):
        yield


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for all LLM providers and services."""
    env_vars = {
        # LLM Provider API Keys
        'OPENAI_API_KEY': 'test_openai_key_123',
        'ANTHROPIC_API_KEY': 'test_anthropic_key_123',
        'OPENROUTER_API_KEY': 'test_openrouter_key_123',
        'GEMINI_API_KEY': 'test_gemini_key_123',
        
        # Azure OpenAI
        'AZURE_API_KEY': 'test_azure_key_123',
        'AZURE_ENDPOINT': 'https://test-resource.openai.azure.com/',
        
        # External Services
        'BINANCE_API_KEY': 'test_binance_key_123',
        'BINANCE_SECRET_KEY': 'test_binance_secret_123',
        
        # Additional test variables
        'TEST_ENV_VAR': 'test_value'
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


# ============================================================================
# DATA FACTORIES FOR CONFIGURATION OBJECTS
# ============================================================================

class ConfigFactory:
    """Factory class for creating test configuration objects."""
    
    @staticmethod
    def model_config(
        provider: str = "litellm",
        model_id: str = "openai/gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a model configuration."""
        config = {
            "provider": provider,
            "model_id": model_id,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def binance_toolkit_params(
        api_key: str = "a" * 64,  # Mock 64-character Binance API key
        api_secret: str = "b" * 64,  # Mock 64-character Binance API secret  
        default_market_type: str = "spot",
        **kwargs
    ) -> Dict[str, Any]:
        """Create Binance toolkit parameters."""
        config = {
            "api_key": api_key,
            "api_secret": api_secret,
            "default_market_type": default_market_type
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def toolkit_config(
        name: str = "BinanceToolkit",
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a toolkit configuration."""
        if params is None:
            params = ConfigFactory.binance_toolkit_params()
        
        config = {
            "name": name,
            "params": params
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def tool_config(
        name: str = "web_search",
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a tool configuration."""
        if params is None:
            params = {"max_results": 10, "timeout": 30}
        
        config = {
            "name": name,
            "params": params
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def agno_params(
        reasoning: bool = True,
        markdown: bool = False,
        debug_mode: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create Agno parameters."""
        config = {
            "reasoning": reasoning,
            "markdown": markdown,
            "debug_mode": debug_mode
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def adapter_params(
        max_retries: int = 3,
        timeout: int = 30,
        **kwargs
    ) -> Dict[str, Any]:
        """Create adapter parameters."""
        config = {
            "max_retries": max_retries,
            "timeout": timeout
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def registration_config(
        action_keys: Optional[List[Dict[str, str]]] = None,
        named_keys: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create registration configuration."""
        if action_keys is None:
            action_keys = [{"action_verb": "plan", "task_type": "SEARCH"}]
        if named_keys is None:
            named_keys = ["TestPlanner", "test_planner"]
        
        config = {
            "action_keys": action_keys,
            "named_keys": named_keys
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def agent_config(
        name: str = "TestPlanner",
        agent_type: str = "planner",
        adapter_class: str = "PlannerAdapter",
        model: Optional[Dict[str, Any]] = None,
        prompt_source: str = "test.prompts.TEST_PROMPT",
        **kwargs
    ) -> Dict[str, Any]:
        """Create a complete agent configuration."""
        if model is None:
            model = ConfigFactory.model_config()
        
        config = {
            "name": name,
            "type": agent_type,
            "adapter_class": adapter_class,
            "description": f"Test {agent_type} agent",
            "model": model,
            "prompt_source": prompt_source,
            "response_model": "PlanOutput" if agent_type == "planner" else None,
            "agno_params": ConfigFactory.agno_params(),
            "adapter_params": ConfigFactory.adapter_params(),
            "tools": [ConfigFactory.tool_config()],
            "registration": ConfigFactory.registration_config(),
            "enabled": True
        }
        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}
        config.update(kwargs)
        return config
    
    @staticmethod
    def agents_yaml_config(
        agents: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create agents YAML configuration."""
        if agents is None:
            agents = [
                ConfigFactory.agent_config(name="TestPlanner", agent_type="planner"),
                ConfigFactory.agent_config(
                    name="TestExecutor",
                    agent_type="executor",
                    adapter_class="ExecutorAdapter",
                    prompt_source="test.prompts.EXECUTOR_PROMPT",
                    response_model=None
                )
            ]
        
        if metadata is None:
            metadata = {"version": "1.0.0", "created_by": "test"}
        
        config = {
            "agents": agents,
            "metadata": metadata
        }
        config.update(kwargs)
        return config
    
    @staticmethod
    def profile_config(
        name: str = "test_profile",
        description: str = "Test profile for testing",
        root_planner_adapter_name: str = "TestPlanner",
        **kwargs
    ) -> Dict[str, Any]:
        """Create profile configuration."""
        config = {
            "name": name,
            "description": description,
            "root_planner_adapter_name": root_planner_adapter_name,
            "root_aggregator_adapter_name": "TestAggregator",
            "planner_adapter_names": {"search": "SearchPlanner", "write": "WritePlanner"},
            "executor_adapter_names": {"search": "SearchExecutor", "write": "WriteExecutor"},
            "aggregator_adapter_names": {"search": "SearchAggregator"},
            "atomizer_adapter_name": "TestAtomizer",
            "default_planner_adapter_name": "DefaultPlanner",
            "default_executor_adapter_name": "DefaultExecutor"
        }
        config.update(kwargs)
        return config


# ============================================================================
# PYTEST FIXTURES USING FACTORY
# ============================================================================

@pytest.fixture
def config_factory():
    """Provide the ConfigFactory for dynamic config creation."""
    return ConfigFactory


@pytest.fixture
def sample_model_config():
    """Sample model configuration."""
    return ConfigFactory.model_config()


@pytest.fixture
def sample_binance_toolkit_params():
    """Sample Binance toolkit parameters."""
    return ConfigFactory.binance_toolkit_params()


@pytest.fixture
def sample_toolkit_config():
    """Sample toolkit configuration."""
    return ConfigFactory.toolkit_config()


@pytest.fixture
def sample_tool_config():
    """Sample tool configuration."""
    return ConfigFactory.tool_config()


@pytest.fixture
def sample_agno_params():
    """Sample Agno parameters."""
    return ConfigFactory.agno_params()


@pytest.fixture
def sample_adapter_params():
    """Sample adapter parameters."""
    return ConfigFactory.adapter_params()


@pytest.fixture
def sample_registration_config():
    """Sample registration configuration."""
    return ConfigFactory.registration_config()


@pytest.fixture
def sample_agent_config():
    """Sample agent configuration."""
    return ConfigFactory.agent_config()


@pytest.fixture
def sample_agents_yaml_config():
    """Sample agents YAML configuration."""
    return ConfigFactory.agents_yaml_config()


@pytest.fixture
def sample_profile_config():
    """Sample profile configuration."""
    return ConfigFactory.profile_config()


@pytest.fixture
def sample_profile_yaml_config():
    """Sample profile YAML configuration."""
    return {
        "profile": ConfigFactory.profile_config(),
        "metadata": {"version": "1.0.0"}
    }


# ============================================================================
# FILESYSTEM AND MOCK HELPERS
# ============================================================================

@pytest.fixture
def mock_yaml_file(tmp_path):
    """Create temporary YAML files for testing."""
    def _create_yaml_file(content: Dict[str, Any], filename: str = "test.yaml") -> Path:
        yaml_file = tmp_path / filename
        config = OmegaConf.create(content)
        OmegaConf.save(config, yaml_file)
        return yaml_file
    return _create_yaml_file


@pytest.fixture
def mock_config_directory(tmp_path, sample_agents_yaml_config):
    """Create a temporary config directory with test files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create agents.yaml
    agents_file = config_dir / "agents.yaml"
    config = OmegaConf.create(sample_agents_yaml_config)
    OmegaConf.save(config, agents_file)
    
    # Create profiles directory
    profiles_dir = config_dir / "profiles"
    profiles_dir.mkdir()
    
    # Create a test profile
    test_profile = {
        "profile": ConfigFactory.profile_config(),
        "metadata": {"version": "1.0.0"}
    }
    profile_file = profiles_dir / "test_profile.yaml"
    profile_config = OmegaConf.create(test_profile)
    OmegaConf.save(profile_config, profile_file)
    
    return config_dir


@pytest.fixture
def mock_prompt_module():
    """Mock prompt module for testing prompt resolution."""
    mock_module = Mock()
    mock_module.TEST_PROMPT = "Test prompt content for planner"
    mock_module.PLANNER_PROMPT = "Planner system message"
    mock_module.EXECUTOR_PROMPT = "Executor system message"
    mock_module.COMPLEX_PROMPT = "Complex prompt for testing"
    return mock_module


@pytest.fixture
def mock_agent_registry():
    """Mock agent registry with common methods."""
    registry = Mock()
    registry.register_agent_adapter = Mock()
    registry.register_named_agent = Mock()
    registry.get_agent = Mock()
    registry.get_instance = Mock(return_value=registry)
    return registry


@pytest.fixture
def mock_agent_adapter():
    """Mock agent adapter instance."""
    adapter = Mock()
    adapter.name = "TestAdapter"
    adapter.__class__.__name__ = "MockAdapter"
    return adapter


@pytest.fixture
def mock_agent_blueprint():
    """Mock agent blueprint instance."""
    blueprint = Mock()
    blueprint.name = "TestBlueprint"
    blueprint.planner_adapter_names = {}
    blueprint.executor_adapter_names = {}
    blueprint.aggregator_adapter_names = {}
    return blueprint


# ============================================================================
# VALIDATION ERROR FIXTURES
# ============================================================================

@pytest.fixture
def invalid_model_configs():
    """Invalid model configurations for testing validation errors."""
    return [
        {"model_id": "openai/gpt-4", "temperature": 0.7},  # Missing provider
        {"provider": "litellm", "temperature": 0.7},  # Missing model_id
        {"provider": "invalid_provider", "model_id": "openai/gpt-4"},  # Invalid provider
        {"provider": "litellm", "model_id": "openai/gpt-4", "temperature": 3.0},  # Invalid temp range
        {"provider": "litellm", "model_id": "openai/gpt-4", "max_tokens": -100},  # Invalid max_tokens
    ]


@pytest.fixture
def invalid_agent_configs():
    """Invalid agent configurations for testing validation errors."""
    base_model = ConfigFactory.model_config()
    return [
        {"type": "planner", "adapter_class": "PlannerAdapter", "model": base_model},  # Missing name
        {"name": "TestAgent", "adapter_class": "PlannerAdapter", "model": base_model},  # Missing type
        {"name": "TestAgent", "type": "invalid_type", "adapter_class": "PlannerAdapter", "model": base_model},  # Invalid type
        {"name": "TestAgent", "type": "planner", "adapter_class": "PlannerAdapter"},  # Missing model
    ]


# ============================================================================
# PARAMETERIZED TEST DATA
# ============================================================================

@pytest.fixture
def provider_test_data():
    """Test data for different LLM providers."""
    return [
        ("litellm", "openai/gpt-4", "OPENAI_API_KEY"),
        ("litellm", "anthropic/claude-3", "ANTHROPIC_API_KEY"),
        ("litellm", "openrouter/meta/llama-2-70b", "OPENROUTER_API_KEY"),
        ("litellm", "gemini/gemini-pro", "GEMINI_API_KEY"),
        ("litellm", "azure/gpt-4", "AZURE_API_KEY"),
    ]


@pytest.fixture
def task_type_test_data():
    """Test data for different task types."""
    return ["WRITE", "THINK", "SEARCH", "AGGREGATE", "CODE_INTERPRET", "IMAGE_GENERATION"]


@pytest.fixture
def agent_type_test_data():
    """Test data for different agent types."""
    return [
        ("planner", "PlannerAdapter", "test.prompts.PLANNER_PROMPT"),
        ("executor", "ExecutorAdapter", "test.prompts.EXECUTOR_PROMPT"),
        ("atomizer", "AtomizerAdapter", "test.prompts.ATOMIZER_PROMPT"),
        ("aggregator", "AggregatorAdapter", "test.prompts.AGGREGATOR_PROMPT"),
    ] 