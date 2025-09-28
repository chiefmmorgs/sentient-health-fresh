"""
Optimized tests for agent_configs.models module.
Tests all Pydantic models and validation functions using the ConfigFactory for clean, reusable test data.
"""

import pytest
from pydantic import ValidationError
from unittest.mock import patch
import os

from sentientresearchagent.hierarchical_agent_framework.agent_configs.models import (
    ModelConfig, ToolConfig, BinanceToolkitParams, ToolkitConfig,
    ActionKey, RegistrationConfig, AgnoParams, AdapterParams,
    AgentConfig, AgentsYAMLConfig, ProfileConfig, ProfileYAMLConfig,
    validate_agent_config, validate_agents_yaml, validate_profile_yaml,
    validate_toolkit_config
)


# ============================================================================
# MODEL CONFIGURATION TESTS
# ============================================================================

class TestModelConfig:
    """Test ModelConfig validation with comprehensive coverage."""

    def test_valid_model_config(self, config_factory, mock_environment_variables):
        """Test creating valid model configs with factory."""
        config_data = config_factory.model_config()
        config = ModelConfig(**config_data)
        
        assert config.provider == "litellm"
        assert config.model_id == "openai/gpt-4"
        assert config.temperature == 0.7
        assert config.max_tokens == 2000

    def test_provider_normalization(self, config_factory, mock_environment_variables):
        """Test provider normalization to lowercase."""
        config_data = config_factory.model_config(provider="litellm")
        config = ModelConfig(**config_data)
        assert config.provider == "litellm"
        
        # Test that invalid providers are rejected
        with pytest.raises(ValidationError):
            invalid_config = config_factory.model_config(provider="invalid_provider")
            ModelConfig(**invalid_config)

    @pytest.mark.parametrize("temperature,should_pass", [
        (0.0, True),
        (0.5, True),
        (1.0, True),
        (2.0, True),
        (2.0, True),
        (-0.1, False),
        (2.1, False),
        (5.0, False),
    ])
    def test_temperature_validation(self, config_factory, mock_environment_variables, temperature, should_pass):
        """Test temperature validation bounds."""
        config_data = config_factory.model_config(temperature=temperature)
        
        if should_pass:
            config = ModelConfig(**config_data)
            assert config.temperature == temperature
        else:
            with pytest.raises(ValidationError):
                ModelConfig(**config_data)

    @pytest.mark.parametrize("max_tokens,should_pass", [
        (1, True),
        (100, True),
        (4000, True),
        (8192, True),
        (0, False),
        (-1, False),
        (-100, False),
    ])
    def test_max_tokens_validation(self, config_factory, mock_environment_variables, max_tokens, should_pass):
        """Test max_tokens validation."""
        config_data = config_factory.model_config(max_tokens=max_tokens)
        
        if should_pass:
            config = ModelConfig(**config_data)
            assert config.max_tokens == max_tokens
        else:
            with pytest.raises(ValidationError):
                ModelConfig(**config_data)

    @pytest.mark.parametrize("provider,model_id,env_key", [
        ("litellm", "openai/gpt-4", "OPENAI_API_KEY"),
        ("litellm", "anthropic/claude-3", "ANTHROPIC_API_KEY"),
        ("litellm", "openrouter/meta/llama-2-70b", "OPENROUTER_API_KEY"),
        ("litellm", "gemini/gemini-pro", "GEMINI_API_KEY"),
        ("litellm", "azure/gpt-4", "AZURE_API_KEY"),
    ])
    def test_environment_validation_success(self, config_factory, mock_environment_variables, provider, model_id, env_key):
        """Test environment validation for different providers."""
        config_data = config_factory.model_config(provider=provider, model_id=model_id)
        config = ModelConfig(**config_data)
        
        # Environment should validate correctly
        assert config.provider == provider
        assert config.model_id == model_id
        assert env_key in mock_environment_variables

    def test_invalid_model_configs(self, config_factory, invalid_model_configs, mock_environment_variables):
        """Test various invalid model configurations."""
        for invalid_config in invalid_model_configs:
            with pytest.raises(ValidationError):
                ModelConfig(**invalid_config)

    def test_extra_parameters_allowed(self, config_factory, mock_environment_variables):
        """Test that extra model parameters are allowed."""
        config_data = config_factory.model_config(
            custom_param="value",
            another_param=123,
            nested_param={"key": "value"}
        )
        config = ModelConfig(**config_data)
        
        # Should accept extra parameters without validation error
        assert hasattr(config, 'custom_param')
        assert config.custom_param == "value"


# ============================================================================
# TOOLKIT AND TOOL CONFIGURATION TESTS
# ============================================================================

class TestBinanceToolkitParams:
    """Test BinanceToolkitParams validation."""

    def test_valid_binance_params(self, config_factory, mock_environment_variables):
        """Test creating valid Binance toolkit params."""
        params_data = config_factory.binance_toolkit_params()
        params = BinanceToolkitParams(**params_data)
        
        assert params.api_key == "a" * 64
        assert params.api_secret == "b" * 64
        assert params.default_market_type == "spot"

    @pytest.mark.parametrize("market_type", ["spot", "usdm", "coinm"])
    def test_market_validation(self, config_factory, mock_environment_variables, market_type):
        """Test market type validation."""
        params_data = config_factory.binance_toolkit_params(default_market_type=market_type)
        params = BinanceToolkitParams(**params_data)
        assert params.default_market_type == market_type
        
    def test_invalid_market_validation(self, config_factory, mock_environment_variables):
        """Test invalid market type validation."""
        with pytest.raises(ValidationError):
            params_data = config_factory.binance_toolkit_params(default_market_type="futures")
            BinanceToolkitParams(**params_data)


class TestToolkitConfig:
    """Test ToolkitConfig validation."""

    def test_valid_toolkit_config(self, config_factory, mock_environment_variables):
        """Test creating valid toolkit config."""
        config_data = config_factory.toolkit_config()
        config = ToolkitConfig(**config_data)
        
        assert config.name == "BinanceToolkit"
        assert config.params is not None

    def test_toolkit_config_variations(self, config_factory, mock_environment_variables):
        """Test toolkit config with different parameters."""
        # Custom parameters
        custom_params = {"custom_key": "custom_value", "timeout": 60}
        config_data = config_factory.toolkit_config(name="CustomToolkit", params=custom_params)
        config = ToolkitConfig(**config_data)
        
        assert config.name == "CustomToolkit"
        assert config.params == custom_params


class TestToolConfig:
    """Test ToolConfig validation."""

    def test_valid_tool_config(self, config_factory, mock_environment_variables):
        """Test creating valid tool config."""
        config_data = config_factory.tool_config()
        config = ToolConfig(**config_data)
        
        assert config.name == "web_search"
        assert config.params is not None

    def test_tool_config_variations(self, config_factory, mock_environment_variables):
        """Test tool config with different parameters."""
        custom_params = {"max_results": 5, "language": "en"}
        config_data = config_factory.tool_config(name="custom_search", params=custom_params)
        config = ToolConfig(**config_data)
        
        assert config.name == "custom_search"
        assert config.params == custom_params


# ============================================================================
# AGENT PARAMETER TESTS
# ============================================================================

class TestAgnoParams:
    """Test AgnoParams validation."""

    def test_valid_agno_params(self, config_factory, mock_environment_variables):
        """Test creating valid Agno params."""
        params_data = config_factory.agno_params()
        params = AgnoParams(**params_data)
        
        assert params.reasoning is True
        assert params.markdown is False
        assert params.debug_mode is False

    def test_agno_params_defaults(self, mock_environment_variables):
        """Test default Agno params."""
        params = AgnoParams()
        
        # Test defaults for optional fields (only reasoning exists in actual model)
        assert params.reasoning is None

    @pytest.mark.parametrize("reasoning", [True, False, None])
    def test_agno_params_combinations(self, mock_environment_variables, reasoning):
        """Test various combinations of Agno parameters."""
        params = AgnoParams(reasoning=reasoning)
        
        assert params.reasoning == reasoning


class TestAdapterParams:
    """Test AdapterParams validation."""

    def test_valid_adapter_params(self, config_factory, mock_environment_variables):
        """Test creating valid adapter params."""
        params_data = config_factory.adapter_params()
        params = AdapterParams(**params_data)
        
        assert params.max_retries == 3
        assert params.timeout == 30

    @pytest.mark.parametrize("search_context_size,should_pass", [
        ("low", True),
        ("medium", True), 
        ("high", True),
        ("invalid", False),  # Invalid search_context_size
        (1000, False),  # Invalid type
    ])
    def test_adapter_params_validation(self, mock_environment_variables, search_context_size, should_pass):
        """Test adapter params validation."""
        params_data = {
            "search_context_size": search_context_size
        }
        
        if should_pass:
            params = AdapterParams(**params_data)
            assert params.search_context_size == search_context_size
        else:
            with pytest.raises(ValidationError):
                AdapterParams(**params_data)


# ============================================================================
# REGISTRATION AND ACTION KEY TESTS
# ============================================================================

class TestActionKey:
    """Test ActionKey validation."""

    @pytest.mark.parametrize("action_verb,task_type", [
        ("plan", "SEARCH"),
        ("execute", "WRITE"),
        ("aggregate", "THINK"),
        ("atomize", "CODE_INTERPRET"),
    ])
    def test_valid_action_key(self, mock_environment_variables, action_verb, task_type):
        """Test creating valid action keys."""
        action_key = ActionKey(action_verb=action_verb, task_type=task_type)
        
        assert action_key.action_verb == action_verb
        assert action_key.task_type == task_type

    def test_invalid_task_type(self, mock_environment_variables):
        """Test invalid task type."""
        with pytest.raises(ValidationError):
            ActionKey(action_verb="plan", task_type="INVALID_TYPE")


class TestRegistrationConfig:
    """Test RegistrationConfig validation."""

    def test_valid_registration_config(self, config_factory, mock_environment_variables):
        """Test creating valid registration config."""
        config_data = config_factory.registration_config()
        config = RegistrationConfig(**config_data)
        
        assert len(config.action_keys) == 1
        assert config.action_keys[0].action_verb == "plan"
        assert config.action_keys[0].task_type == "SEARCH"
        assert "TestPlanner" in config.named_keys

    def test_empty_registration_config(self, mock_environment_variables):
        """Test empty registration config."""
        config = RegistrationConfig(action_keys=[], named_keys=[])
        
        assert config.action_keys == []
        assert config.named_keys == []


# ============================================================================
# AGENT CONFIGURATION TESTS
# ============================================================================

class TestAgentConfig:
    """Test AgentConfig validation with comprehensive scenarios."""

    @pytest.mark.parametrize("agent_type,adapter_class,prompt_source", [
        ("planner", "PlannerAdapter", "test.prompts.PLANNER_PROMPT"),
        ("executor", "ExecutorAdapter", "test.prompts.EXECUTOR_PROMPT"),
        ("atomizer", "AtomizerAdapter", "test.prompts.ATOMIZER_PROMPT"),
        ("aggregator", "AggregatorAdapter", "test.prompts.AGGREGATOR_PROMPT"),
    ])
    def test_valid_agent_configs(self, config_factory, mock_environment_variables, agent_type, adapter_class, prompt_source):
        """Test creating valid agent configs for different types."""
        config_data = config_factory.agent_config(
            name=f"Test{agent_type.capitalize()}",
            agent_type=agent_type,
            adapter_class=adapter_class,
            prompt_source=prompt_source
        )
        config = AgentConfig(**config_data)
        
        assert config.name == f"Test{agent_type.capitalize()}"
        assert config.type == agent_type
        assert config.adapter_class == adapter_class
        assert config.prompt_source == prompt_source

    def test_agent_config_defaults(self, config_factory, mock_environment_variables):
        """Test agent config with defaults."""
        # Create minimal executor config
        minimal_config = config_factory.agent_config(
            name="MinimalAgent",
            agent_type="executor",
            adapter_class="ExecutorAdapter",
            prompt_source="test.prompts.EXECUTOR_PROMPT"
        )
        
        # Remove optional fields to test defaults
        for key in ["description", "tools", "registration", "agno_params", "adapter_params"]:
            minimal_config.pop(key, None)
        
        config = AgentConfig(**minimal_config)
        
        assert config.enabled is True
        assert config.description is None
        assert config.tools == []

    def test_invalid_agent_configs(self, invalid_agent_configs, mock_environment_variables):
        """Test various invalid agent configurations."""
        for invalid_config in invalid_agent_configs:
            with pytest.raises(ValidationError):
                AgentConfig(**invalid_config)

    def test_custom_search_agent_config(self, config_factory, mock_environment_variables):
        """Test custom search agent configuration."""
        config_data = {
            "name": "CustomSearchAgent",
            "type": "custom_search",
            "adapter_class": "OpenAICustomSearchAdapter",
            "adapter_params": config_factory.adapter_params(),
            "enabled": True
        }
        
        config = AgentConfig(**config_data)
        
        assert config.name == "CustomSearchAgent"
        assert config.type == "custom_search"
        assert config.adapter_class == "OpenAICustomSearchAdapter"


# ============================================================================
# YAML CONFIGURATION TESTS
# ============================================================================

class TestAgentsYAMLConfig:
    """Test AgentsYAMLConfig validation."""

    def test_valid_agents_yaml_config(self, config_factory, mock_environment_variables):
        """Test creating valid agents YAML config."""
        config_data = config_factory.agents_yaml_config()
        config = AgentsYAMLConfig(**config_data)
        
        assert len(config.agents) == 2
        assert config.agents[0].name == "TestPlanner"
        assert config.agents[1].name == "TestExecutor"
        assert config.metadata["version"] == "1.0.0"

    def test_duplicate_agent_names(self, config_factory, mock_environment_variables):
        """Test validation fails with duplicate agent names."""
        duplicate_agents = [
            config_factory.agent_config(name="DuplicateAgent"),
            config_factory.agent_config(name="DuplicateAgent", agent_type="executor", adapter_class="ExecutorAdapter")
        ]
        
        config_data = config_factory.agents_yaml_config(agents=duplicate_agents)
        
        with pytest.raises(ValidationError, match="Duplicate agent names found"):
            AgentsYAMLConfig(**config_data)

    def test_empty_agents_list(self, config_factory, mock_environment_variables):
        """Test empty agents list."""
        config_data = config_factory.agents_yaml_config(agents=[])
        config = AgentsYAMLConfig(**config_data)
        
        assert config.agents == []


# ============================================================================
# PROFILE CONFIGURATION TESTS
# ============================================================================

class TestProfileConfig:
    """Test ProfileConfig validation."""

    def test_valid_profile_config(self, config_factory, mock_environment_variables):
        """Test creating valid profile config."""
        config_data = config_factory.profile_config()
        config = ProfileConfig(**config_data)
        
        assert config.name == "test_profile"
        assert config.description == "Test profile for testing"
        assert config.root_planner_adapter_name == "TestPlanner"

    @pytest.mark.parametrize("task_type", ["search", "write", "think", "aggregate"])  
    def test_task_type_validation(self, config_factory, mock_environment_variables, task_type):
        """Test task type key validation."""
        planner_names = {task_type: f"{task_type.capitalize()}Planner"}
        config_data = config_factory.profile_config(planner_adapter_names=planner_names)
        config = ProfileConfig(**config_data)
        
        assert config.planner_adapter_names[task_type] == f"{task_type.capitalize()}Planner"
        
    def test_invalid_task_type_validation(self, config_factory, mock_environment_variables):
        """Test invalid task type validation."""
        with pytest.raises(ValidationError):
            invalid_planner_names = {"invalid_task": "InvalidPlanner"}
            config_data = config_factory.profile_config(planner_adapter_names=invalid_planner_names)
            ProfileConfig(**config_data)


class TestProfileYAMLConfig:
    """Test ProfileYAMLConfig validation."""

    def test_valid_profile_yaml_config(self, config_factory, mock_environment_variables):
        """Test creating valid profile YAML config."""
        profile_data = {
            "profile": config_factory.profile_config(),
            "metadata": {"version": "1.0.0", "author": "test"}
        }
        
        config = ProfileYAMLConfig(**profile_data)
        
        assert config.profile.name == "test_profile"
        assert config.metadata["version"] == "1.0.0"


# ============================================================================
# VALIDATION FUNCTION TESTS
# ============================================================================

class TestValidationFunctions:
    """Test standalone validation functions."""

    def test_validate_agent_config(self, config_factory, mock_environment_variables):
        """Test validate_agent_config function."""
        config_data = config_factory.agent_config()
        validated = validate_agent_config(config_data)
        
        assert validated.name == "TestPlanner"
        assert validated.type == "planner"

    def test_validate_agents_yaml(self, config_factory, mock_environment_variables):
        """Test validate_agents_yaml function."""
        config_data = config_factory.agents_yaml_config()
        validated = validate_agents_yaml(config_data)
        
        assert len(validated.agents) == 2

    def test_validate_profile_yaml(self, config_factory, mock_environment_variables):
        """Test validate_profile_yaml function."""
        profile_data = {
            "profile": config_factory.profile_config(),
            "metadata": {"version": "1.0.0"}
        }
        
        validated = validate_profile_yaml(profile_data)
        
        assert validated.profile.name == "test_profile"

    def test_validate_toolkit_config(self, config_factory, mock_environment_variables):
        """Test validate_toolkit_config function."""
        config_data = config_factory.toolkit_config()
        validated = validate_toolkit_config(config_data)
        
        assert validated.name == "BinanceToolkit"


# ============================================================================
# INTEGRATION AND EDGE CASE TESTS
# ============================================================================

class TestIntegrationValidation:
    """Integration tests for complex validation scenarios."""

    def test_complex_agent_with_all_components(self, config_factory, mock_environment_variables):
        """Test agent config with all possible components."""
        complex_config = config_factory.agent_config(
            name="ComplexAgent",
            agent_type="custom_search",
            adapter_class="OpenAICustomSearchAdapter",
            description="Complex agent with all features",
            adapter_params=config_factory.adapter_params(max_retries=5, timeout=60),
            registration=config_factory.registration_config(
                action_keys=[
                    {"action_verb": "search", "task_type": "SEARCH"},
                    {"action_verb": "aggregate", "task_type": "AGGREGATE"}
                ],
                named_keys=["ComplexAgent", "complex_agent", "ca"]
            )
        )
        
        # Remove fields not allowed for custom search agents
        complex_config.pop("model", None)
        complex_config.pop("prompt_source", None)
        complex_config.pop("agno_params", None)
        complex_config.pop("tools", None)
        
        config = AgentConfig(**complex_config)
        
        assert config.name == "ComplexAgent"
        assert config.type == "custom_search"
        assert len(config.registration.action_keys) == 2
        assert len(config.registration.named_keys) == 3


class TestModelConfigAdvanced:
    """Advanced tests for ModelConfig edge cases."""

    def test_all_parameter_ranges(self, config_factory, mock_environment_variables):
        """Test all parameter validation ranges."""
        # Test extreme valid values
        config_data = config_factory.model_config(
            temperature=2.0,  # Maximum valid
            max_tokens=8192,  # Large but valid
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        
        config = ModelConfig(**config_data)
        
        assert config.temperature == 2.0
        assert config.max_tokens == 8192

    def test_parameter_boundary_validation(self, config_factory, mock_environment_variables):
        """Test parameter boundary validation."""
        # Test just within boundaries
        valid_config = config_factory.model_config(temperature=0.0, max_tokens=1)
        ModelConfig(**valid_config)  # Should not raise
        
        # Test just outside boundaries
        with pytest.raises(ValidationError):
            invalid_config = config_factory.model_config(temperature=-0.01)
            ModelConfig(**invalid_config) 

# ============================================================================
# ADDITIONAL EDGE CASE AND ERROR COVERAGE TESTS
# ============================================================================

class TestModelConfigEdgeCases:
    """Additional edge case tests for ModelConfig."""

    def test_environment_variable_edge_cases(self, config_factory, mock_environment_variables):
        """Test edge cases in environment variable validation."""
        # Test with empty environment variable
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            config_data = config_factory.model_config(model_id="openai/gpt-4")
            with pytest.raises(ValidationError):
                ModelConfig(**config_data)

    def test_model_id_edge_cases(self, config_factory, mock_environment_variables):
        """Test edge cases for model IDs."""
        edge_cases = [
            "openai/gpt-4-turbo-2024-04-09",  # Long specific version
            "anthropic/claude-3-5-sonnet-20241022",  # Date versioned
            "openrouter/microsoft/wizardlm-2-8x22b",  # Complex nested name
        ]
        
        for model_id in edge_cases:
            config_data = config_factory.model_config(model_id=model_id)
            config = ModelConfig(**config_data)
            assert config.model_id == model_id

    @pytest.mark.parametrize("param_name,invalid_value", [
        ("temperature", -0.1),
        ("temperature", 2.1),
        ("max_tokens", 0),
        ("top_p", -0.1),
        ("top_p", 1.1),
        ("frequency_penalty", -2.1),
        ("frequency_penalty", 2.1),
        ("presence_penalty", -2.1),
        ("presence_penalty", 2.1),
    ])
    def test_parameter_boundary_violations(self, config_factory, mock_environment_variables, param_name, invalid_value):
        """Test parameter boundary violations."""
        config_data = config_factory.model_config(**{param_name: invalid_value})
        with pytest.raises(ValidationError):
            ModelConfig(**config_data)


class TestBinanceToolkitParamsAdvanced:
    """Advanced tests for BinanceToolkitParams."""

    def test_symbols_validation_edge_cases(self, config_factory, mock_environment_variables):
        """Test edge cases in symbol validation."""
        # Valid symbols
        valid_symbols = ["BTCUSDT", "ETH_USDT", "BNB123"]
        params_data = config_factory.binance_toolkit_params(symbols=valid_symbols)
        params = BinanceToolkitParams(**params_data)
        assert params.symbols == ["BTCUSDT", "ETH_USDT", "BNB123"]

    def test_invalid_symbols(self, config_factory, mock_environment_variables):
        """Test invalid symbol formats."""
        invalid_symbols = ["btc@usdt", "ETH-USDT!", ""]
        for invalid_symbol in invalid_symbols:
            params_data = config_factory.binance_toolkit_params(symbols=[invalid_symbol])
            with pytest.raises(ValidationError):
                BinanceToolkitParams(**params_data)

    def test_parquet_threshold_validation(self, config_factory, mock_environment_variables):
        """Test parquet threshold validation."""
        # Valid threshold
        params_data = config_factory.binance_toolkit_params(parquet_threshold=500)
        params = BinanceToolkitParams(**params_data)
        assert params.parquet_threshold == 500

        # Invalid threshold (zero or negative)
        with pytest.raises(ValidationError):
            invalid_params = config_factory.binance_toolkit_params(parquet_threshold=0)
            BinanceToolkitParams(**invalid_params)


class TestAgentConfigValidationEdgeCases:
    """Edge case tests for AgentConfig validation."""

    def test_agent_type_adapter_mismatch(self, config_factory, mock_environment_variables):
        """Test mismatched agent type and adapter combinations."""
        # Planner agent with executor adapter should fail
        with pytest.raises(ValidationError):
            config_data = config_factory.agent_config(
                agent_type="planner",
                adapter_class="ExecutorAdapter"
            )
            AgentConfig(**config_data)

    def test_custom_search_agent_restrictions(self, config_factory, mock_environment_variables):
        """Test that custom search agents don't allow certain fields."""
        # Custom search agents shouldn't have models or prompts
        config_data = {
            "name": "SearchAgent",
            "type": "custom_search", 
            "adapter_class": "OpenAICustomSearchAdapter",
            "enabled": True
        }
        
        # Should work without model/prompt
        config = AgentConfig(**config_data)
        assert config.type == "custom_search"

    def test_tool_normalization_edge_cases(self, config_factory, mock_environment_variables):
        """Test edge cases in tool normalization."""
        # Mix of string and dict tools
        mixed_tools = [
            "web_search",
            {"name": "calculator", "params": {"precision": 10}},
            {"name": "python_tool"}
        ]
        
        config_data = config_factory.agent_config(tools=mixed_tools)
        config = AgentConfig(**config_data)
        
        assert len(config.tools) == 3
        assert config.tools[0] == "web_search"  # String preserved
        assert isinstance(config.tools[1], ToolConfig)  # Dict converted
        assert isinstance(config.tools[2], ToolConfig)  # Dict converted


class TestProfileConfigAdvanced:
    """Advanced tests for ProfileConfig."""

    def test_complex_task_mappings(self, config_factory, mock_environment_variables):
        """Test complex task type mappings."""
        complex_mappings = {
            "planner_adapter_names": {
                "search": "SearchPlanner",
                "write": "WritePlanner", 
                "think": "ThinkPlanner",
                "aggregate": "AggregateP‌lanner"
            },
            "executor_adapter_names": {
                "search": "SearchExecutor",
                "write": "WriteExecutor",
                "code_interpret": "CodeExecutor"
            }
        }
        
        config_data = config_factory.profile_config(**complex_mappings)
        config = ProfileConfig(**config_data)
        
        assert len(config.planner_adapter_names) == 4
        assert len(config.executor_adapter_names) == 3

    def test_minimal_profile_config(self, mock_environment_variables):
        """Test minimal profile configuration."""
        minimal_config = {
            "name": "minimal_profile"
        }
        
        config = ProfileConfig(**minimal_config)
        assert config.name == "minimal_profile"
        # All other fields should have defaults or be None


class TestValidationFunctionsEdgeCases:
    """Edge case tests for validation functions."""

    def test_validate_empty_configurations(self, mock_environment_variables):
        """Test validation of empty configurations."""
        # Empty agents list
        empty_agents_config = {"agents": [], "metadata": {"version": "1.0.0"}}
        validated = validate_agents_yaml(empty_agents_config)
        assert len(validated.agents) == 0

        # Empty profile
        empty_profile_config = {
            "profile": {"name": "empty"},
            "metadata": {"version": "1.0.0"}
        }
        validated_profile = validate_profile_yaml(empty_profile_config)
        assert validated_profile.profile.name == "empty"

    def test_validation_with_extra_fields(self, config_factory, mock_environment_variables):
        """Test validation with extra unknown fields."""
        # Agent config with extra fields
        agent_with_extras = config_factory.agent_config()
        agent_with_extras["unknown_field"] = "should be ignored"
        agent_with_extras["custom_setting"] = {"nested": "value"}
        
        # Should validate successfully and preserve extra fields
        validated = validate_agent_config(agent_with_extras)
        assert validated.name == "TestPlanner"


# ============================================================================
# PERFORMANCE AND STRESS TESTS
# ============================================================================

class TestPerformanceAndStress:
    """Performance and stress tests for configuration handling."""

    def test_large_agent_configuration(self, config_factory, mock_environment_variables):
        """Test handling of large agent configurations."""
        # Create agent with many tools and complex config
        large_tools = [
            config_factory.tool_config(name=f"tool_{i}", params={"setting": i})
            for i in range(20)
        ]
        
        large_config = config_factory.agent_config(
            name="LargeAgent",
            tools=large_tools,
            description="A" * 1000,  # Long description
            adapter_params=config_factory.adapter_params(
                custom_param_1="value1",
                custom_param_2="value2",
                nested_config={"deep": {"setting": "value"}}
            )
        )
        
        config = AgentConfig(**large_config)
        assert len(config.tools) == 20
        assert len(config.description) == 1000

    def test_many_agents_yaml_config(self, config_factory, mock_environment_variables):
        """Test configuration with many agents."""
        many_agents = []
        for i in range(100):
            agent_type = "planner" if i % 2 == 0 else "executor"
            adapter_class = "PlannerAdapter" if agent_type == "planner" else "ExecutorAdapter"
            prompt_source = f"test.prompts.{agent_type.upper()}_PROMPT"
            
            many_agents.append(config_factory.agent_config(
                name=f"Agent{i:03d}",
                agent_type=agent_type,
                adapter_class=adapter_class,
                prompt_source=prompt_source
            ))
        
        config_data = config_factory.agents_yaml_config(agents=many_agents)
        config = AgentsYAMLConfig(**config_data)
        
        assert len(config.agents) == 100
        # Verify no duplicate names
        names = [agent.name for agent in config.agents]
        assert len(set(names)) == 100

    def test_nested_configuration_depth(self, config_factory, mock_environment_variables):
        """Test deeply nested configuration structures."""
        deep_params = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep_value",
                            "array": [1, 2, 3, {"nested": "item"}]
                        }
                    }
                }
            }
        }
        
        config_data = config_factory.agent_config(
            adapter_params=AdapterParams(**{"deep_config": deep_params})
        )
        
        config = AgentConfig(**config_data)
        assert config.adapter_params.deep_config["level1"]["level2"]["level3"]["level4"]["value"] == "deep_value"


# ============================================================================
# INTEGRATION AND INTEROPERABILITY TESTS
# ============================================================================

class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_multi_provider_configuration(self, config_factory, mock_environment_variables):
        """Test configuration with multiple model providers."""
        providers_config = []
        provider_combinations = [
            ("litellm", "openai/gpt-4"),
            ("litellm", "anthropic/claude-3"),
            ("openai", "gpt-3.5-turbo"),
            ("gemini", "gemini-pro"),
        ]
        
        for i, (provider, model_id) in enumerate(provider_combinations):
            agent_config = config_factory.agent_config(
                name=f"Agent_{provider}_{i}",
                model=config_factory.model_config(provider=provider, model_id=model_id)
            )
            providers_config.append(agent_config)
        
        config_data = config_factory.agents_yaml_config(agents=providers_config)
        config = AgentsYAMLConfig(**config_data)
        
        assert len(config.agents) == 4
        providers_used = {agent.model.provider for agent in config.agents}
        assert len(providers_used) == 3  # litellm, openai, gemini

    def test_complete_workflow_configuration(self, config_factory, mock_environment_variables):
        """Test a complete workflow with all agent types."""
        workflow_agents = [
            # Root planner
            config_factory.agent_config(
                name="RootPlanner",
                agent_type="planner",
                adapter_class="PlannerAdapter",
                prompt_source="test.prompts.ROOT_PLANNER_PROMPT"
            ),
            # Specialized planners
            config_factory.agent_config(
                name="SearchPlanner", 
                agent_type="planner",
                adapter_class="PlannerAdapter",
                prompt_source="test.prompts.SEARCH_PLANNER_PROMPT"
            ),
            # Executors
            config_factory.agent_config(
                name="SearchExecutor",
                agent_type="executor", 
                adapter_class="ExecutorAdapter",
                prompt_source="test.prompts.SEARCH_EXECUTOR_PROMPT",
                tools=[config_factory.tool_config(name="web_search")]
            ),
            # Aggregator
            config_factory.agent_config(
                name="Aggregator",
                agent_type="aggregator",
                adapter_class="AggregatorAdapter", 
                prompt_source="test.prompts.AGGREGATOR_PROMPT"
            ),
            # Custom search
            {
                "name": "CustomSearchAgent",
                "type": "custom_search",
                "adapter_class": "OpenAICustomSearchAdapter",
                "adapter_params": config_factory.adapter_params(search_context_size="high")
            }
        ]
        
        # Create complete profile
        profile_config = config_factory.profile_config(
            name="CompleteWorkflow",
            root_planner_adapter_name="RootPlanner",
            root_aggregator_adapter_name="Aggregator",
            planner_adapter_names={"search": "SearchPlanner"},
            executor_adapter_names={"search": "SearchExecutor"}
        )
        
        # Validate all components
        agents_config = config_factory.agents_yaml_config(agents=workflow_agents)
        validated_agents = AgentsYAMLConfig(**agents_config)
        validated_profile = ProfileConfig(**profile_config)
        
        assert len(validated_agents.agents) == 5
        assert validated_profile.root_planner_adapter_name == "RootPlanner" 