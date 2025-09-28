"""
Tests for agent_configs.profile_loader module.
Tests ProfileLoader class with mocks and fixtures.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from omegaconf import OmegaConf, DictConfig

from sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader import ProfileLoader


class TestProfileLoader:
    """Test ProfileLoader class."""

    def test_init_with_profiles_dir(self, mock_config_directory):
        """Test initialization with provided profiles directory."""
        profiles_dir = mock_config_directory / "profiles"
        loader = ProfileLoader(profiles_dir)
        assert loader.profiles_dir == profiles_dir

    def test_init_without_profiles_dir(self):
        """Test initialization without profiles directory (uses default)."""
        with patch.object(Path, 'exists', return_value=True):
            loader = ProfileLoader()
            expected_dir = Path(__file__).parent.parent / "profiles"
            assert loader.profiles_dir == expected_dir

    def test_init_profiles_dir_not_exists(self, tmp_path):
        """Test initialization fails when profiles directory doesn't exist."""
        non_existent_dir = tmp_path / "non_existent_profiles"
        with pytest.raises(FileNotFoundError, match="Profiles directory not found"):
            ProfileLoader(non_existent_dir)

    def test_list_available_profiles(self, mock_config_directory):
        """Test listing available profiles."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        profiles = loader.list_available_profiles()
        
        assert isinstance(profiles, list)
        assert "test_profile" in profiles

    def test_list_available_profiles_empty_directory(self, tmp_path):
        """Test listing profiles in empty directory."""
        empty_profiles_dir = tmp_path / "empty_profiles"
        empty_profiles_dir.mkdir()
        
        loader = ProfileLoader(empty_profiles_dir)
        profiles = loader.list_available_profiles()
        
        assert profiles == []

    def test_list_available_profiles_no_yaml_files(self, tmp_path):
        """Test listing profiles with no YAML files."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        
        # Create non-YAML files
        (profiles_dir / "not_yaml.txt").write_text("not yaml")
        (profiles_dir / "another.json").write_text("{}")
        
        loader = ProfileLoader(profiles_dir)
        profiles = loader.list_available_profiles()
        
        assert profiles == []

    def test_load_profile_success(self, mock_config_directory):
        """Test successful profile loading."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.logger'):
            blueprint = loader.load_profile("test_profile")
        
        # Mock should return an AgentBlueprint
        assert blueprint is not None

    def test_load_profile_file_not_found(self, mock_config_directory):
        """Test loading non-existent profile."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        
        with pytest.raises(FileNotFoundError, match="Profile 'nonexistent' not found"):
            loader.load_profile("nonexistent")

    def test_load_profile_validation_error(self, mock_config_directory):
        """Test profile loading with validation error."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        
        # Mock validation to raise error
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.validate_profile_yaml') as mock_validate:
            mock_validate.side_effect = ValueError("Invalid profile")
            
            with pytest.raises(ValueError, match="Invalid profile configuration"):
                loader.load_profile("test_profile")

    def test_load_profile_with_task_type_conversion(self, tmp_path, sample_profile_yaml_config):
        """Test profile loading with task type conversion."""
        # Create a profiles directory
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        
        # Create a profile file with task type mappings
        profile_file = profiles_dir / "test_profile.yaml"
        config = OmegaConf.create(sample_profile_yaml_config)
        OmegaConf.save(config, profile_file)
        
        loader = ProfileLoader(profiles_dir)
        
        # Mock the AgentBlueprint creation and validation
        mock_blueprint = Mock()
        
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.validate_profile_yaml') as mock_validate:
            with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.AgentBlueprint', return_value=mock_blueprint) as mock_blueprint_class:
                with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.TaskType') as mock_task_type:
                    # Mock TaskType enum
                    mock_task_type.__getitem__ = Mock(side_effect=lambda x: f"TaskType.{x}")
                    
                    # Mock validation to return valid config
                    mock_validated = Mock()
                    mock_validated.profile = Mock()
                    mock_validated.profile.name = "test_profile"
                    mock_validated.profile.description = "Test profile"
                    mock_validated.profile.root_planner_adapter_name = "TestPlanner"
                    mock_validated.profile.planner_adapter_names = {"search": "SearchPlanner"}
                    mock_validated.profile.executor_adapter_names = {"search": "SearchExecutor"}
                    mock_validated.profile.aggregator_adapter_names = None
                    mock_validated.profile.atomizer_adapter_name = None
                    mock_validated.profile.aggregator_adapter_name = None
                    mock_validated.profile.plan_modifier_adapter_name = None
                    mock_validated.profile.default_planner_adapter_name = None
                    mock_validated.profile.default_executor_adapter_name = None
                    mock_validated.profile.default_node_agent_name_prefix = None
                    mock_validate.return_value = mock_validated
                    
                    blueprint = loader.load_profile("test_profile")
                    
                    # Verify blueprint was created
                    assert blueprint == mock_blueprint

    def test_get_all_profiles(self, mock_config_directory):
        """Test getting all available profiles."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        
        # Mock the load_profile method to avoid actual loading
        with patch.object(loader, 'load_profile') as mock_load:
            mock_blueprint = Mock()
            mock_load.return_value = mock_blueprint
            
            with patch.object(loader, 'list_available_profiles', return_value=["test_profile", "another_profile"]):
                profiles = loader.load_all_profiles()
        
        assert isinstance(profiles, dict)
        assert len(profiles) == 2
        assert "test_profile" in profiles
        assert "another_profile" in profiles

    def test_get_all_profiles_empty(self, tmp_path):
        """Test getting all profiles when none exist."""
        empty_profiles_dir = tmp_path / "empty_profiles"
        empty_profiles_dir.mkdir()
        
        loader = ProfileLoader(empty_profiles_dir)
        profiles = loader.load_all_profiles()
        
        assert profiles == {}

    def test_get_all_profiles_with_loading_error(self, mock_config_directory):
        """Test getting all profiles when some fail to load."""
        loader = ProfileLoader(mock_config_directory / "profiles")
        
        def mock_load_profile(name):
            if name == "bad_profile":
                raise ValueError("Bad profile")
            return Mock()
        
        with patch.object(loader, 'load_profile', side_effect=mock_load_profile):
            with patch.object(loader, 'list_available_profiles', return_value=["good_profile", "bad_profile"]):
                with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.logger') as mock_logger:
                    profiles = loader.load_all_profiles()
        
        # Should only have the good profile
        assert len(profiles) == 1
        assert "good_profile" in profiles
        assert "bad_profile" not in profiles
        
        # Should have logged the error
        mock_logger.error.assert_called()


class TestProfileLoaderIntegration:
    """Integration tests for ProfileLoader."""

    def test_profile_loader_error_handling(self, tmp_path):
        """Test error handling in various scenarios."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        
        # Create corrupted YAML file
        corrupted_file = profiles_dir / "corrupted.yaml"
        corrupted_file.write_text("invalid: yaml: content: [unclosed")
        
        loader = ProfileLoader(profiles_dir)
        
        # Should be listed as available (we don't validate file content during listing)
        available = loader.list_available_profiles()
        assert "corrupted" in available
        
        # But should fail when trying to load
        with pytest.raises(Exception):  # OmegaConf will raise an exception for invalid YAML
            loader.load_profile("corrupted")

    def test_profile_loader_file_permissions(self, tmp_path):
        """Test profile loader with file permission issues."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        
        # Create a profile file
        profile_file = profiles_dir / "restricted.yaml"
        profile_file.write_text("profile:\n  name: restricted")
        
        loader = ProfileLoader(profiles_dir)
        
        # Mock file reading to raise permission error
        with patch('sentientresearchagent.hierarchical_agent_framework.agent_configs.profile_loader.OmegaConf.load') as mock_load:
            mock_load.side_effect = PermissionError("Permission denied")
            
            with pytest.raises(PermissionError):
                loader.load_profile("restricted")

 