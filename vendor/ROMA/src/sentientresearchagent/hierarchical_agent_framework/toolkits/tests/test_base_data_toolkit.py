"""
Tests for BaseDataToolkit using shared fixtures and best practices.
Focuses on core functionality with minimal code duplication.
"""
import pytest
import os
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit
from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import DataValidator


class TestInitialization:
    """Test BaseDataToolkit initialization."""
    
    def test_init_data_helpers(self, base_data_toolkit, temp_data_dir):
        """Test initialization with various parameters."""
        base_data_toolkit._init_data_helpers(
            temp_data_dir, 
            parquet_threshold=500, 
            file_prefix="test_"
        )
        
        assert base_data_toolkit.data_dir == temp_data_dir
        assert base_data_toolkit._parquet_threshold == 500
        assert base_data_toolkit._file_prefix == "test_"
        assert temp_data_dir.exists()
    
    def test_creates_nested_directory(self, base_data_toolkit, temp_data_dir):
        """Test creation of nested directories."""
        nested_path = temp_data_dir / "nested" / "data"
        base_data_toolkit._init_data_helpers(nested_path)
        
        assert nested_path.exists()
        assert nested_path.is_dir()


class TestParquetStorage:
    """Test parquet file storage functionality."""
    
    def test_store_list_data(self, initialized_base_toolkit, sample_crypto_data, assert_helpers):
        """Test storing list data as parquet."""
        file_path = initialized_base_toolkit._store_parquet(sample_crypto_data, "crypto")
        
        assert_helpers.assert_parquet_file_created(file_path, expected_rows=3)
        assert "test_crypto" in file_path  # Includes prefix
        
        # Verify data integrity
        df = pd.read_parquet(file_path)
        assert set(df.columns) == {"symbol", "price", "volume", "change"}
    
    def test_store_dataframe(self, initialized_base_toolkit, sample_dataframe):
        """Test storing DataFrame as parquet."""
        file_path = initialized_base_toolkit._store_parquet(sample_dataframe, "df_data")
        
        stored_df = pd.read_parquet(file_path)
        pd.testing.assert_frame_equal(sample_dataframe, stored_df)
    
    def test_store_with_subdirectory(self, initialized_base_toolkit, small_dataset):
        """Test storing with subdirectory creation."""
        file_path = initialized_base_toolkit._store_parquet(
            small_dataset, "test", subdirectory="crypto"
        )
        
        assert "crypto" in file_path
        assert (initialized_base_toolkit.data_dir / "crypto").exists()
    
    @pytest.mark.parametrize("data,error_match", [
        ([], "Cannot store empty list"),
        (pd.DataFrame(), "Cannot store empty DataFrame"),
    ])
    def test_empty_data_errors(self, initialized_base_toolkit, data, error_match):
        """Test error handling for empty data."""
        with pytest.raises(ValueError, match=error_match):
            initialized_base_toolkit._store_parquet(data, "test")
    
    def test_io_error_handling(self, initialized_base_toolkit, sample_crypto_data):
        """Test handling of parquet write errors."""
        with patch('pandas.DataFrame.to_parquet', side_effect=Exception("Write failed")):
            with pytest.raises(IOError, match="Cannot write parquet file"):
                initialized_base_toolkit._store_parquet(sample_crypto_data, "test")


class TestThresholdLogic:
    """Test parquet storage threshold decisions."""
    
    @pytest.mark.parametrize("data_fixture,expected", [
        ("large_dataset", True),
        ("small_dataset", False),
        ("sample_crypto_data", False),  # Only 3 items, below default threshold of 10
    ])
    def test_threshold_decisions(self, initialized_base_toolkit, data_fixture, expected, request):
        """Test parquet storage decisions for different data sizes."""
        data = request.getfixturevalue(data_fixture)
        result = initialized_base_toolkit._should_store_as_parquet(data)
        assert result == expected
    
    def test_dataframe_threshold(self, initialized_base_toolkit):
        """Test threshold logic for DataFrames."""
        large_df = pd.DataFrame({"value": range(15)})  # Above threshold
        small_df = pd.DataFrame({"value": range(5)})   # Below threshold
        
        assert initialized_base_toolkit._should_store_as_parquet(large_df) is True
        assert initialized_base_toolkit._should_store_as_parquet(small_df) is False
    
    @pytest.mark.parametrize("data,expected", [
        ({"data": [{"id": i} for i in range(15)]}, True),
        ({"count": 15}, True),
        ({"size": 15}, True),
        ({"count": 5}, False),
        ({"other_field": 100}, False),
    ])
    def test_dict_threshold_logic(self, initialized_base_toolkit, data, expected):
        """Test threshold logic for dictionary data."""
        result = initialized_base_toolkit._should_store_as_parquet(data)
        assert result == expected


class TestDataConversion:
    """Test DataFrame conversion utilities."""
    
    def test_convert_list_to_dataframe(self, base_data_toolkit, sample_crypto_data):
        """Test converting list to DataFrame."""
        df = base_data_toolkit._convert_to_dataframe(sample_crypto_data)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert set(df.columns) == {"symbol", "price", "volume", "change"}
    
    def test_convert_with_index_column(self, base_data_toolkit, sample_crypto_data):
        """Test conversion with custom index."""
        df = base_data_toolkit._convert_to_dataframe(sample_crypto_data, index_column="symbol")
        
        assert df.index.name == "symbol"
        assert "BTCUSDT" in df.index
    
    def test_convert_dict_to_dataframe(self, base_data_toolkit):
        """Test converting dict to DataFrame."""
        data = {"symbols": ["BTC", "ETH"], "prices": [50000, 3000]}
        df = base_data_toolkit._convert_to_dataframe(data)
        
        assert len(df) == 2
        assert set(df.columns) == {"symbols", "prices"}
    
    def test_dataframe_copy_behavior(self, base_data_toolkit, sample_dataframe):
        """Test that DataFrame conversion returns a copy."""
        df = base_data_toolkit._convert_to_dataframe(sample_dataframe)
        
        assert df is not sample_dataframe
        pd.testing.assert_frame_equal(df, sample_dataframe)
    
    @pytest.mark.parametrize("invalid_data,error_match", [
        ([], "Cannot convert empty list"),
        ("string", "Unsupported data type"),
        (123, "Unsupported data type"),
    ])
    def test_conversion_errors(self, base_data_toolkit, invalid_data, error_match):
        """Test error handling for invalid data types."""
        with pytest.raises(ValueError, match=error_match):
            base_data_toolkit._convert_to_dataframe(invalid_data)


class TestDataValidation:
    """Test data structure validation."""
    
    def test_successful_validation(self, base_data_toolkit, validation_test_cases):
        """Test successful validation scenarios."""
        result = DataValidator.validate_structure(
            validation_test_cases["valid_list"],
            required_fields=["symbol", "price"],
            expected_type=list
        )
        
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["data_type"] == "list"
        assert result["size"] == 1
    
    @pytest.mark.parametrize("test_case,error_substring", [
        ("invalid_list_missing_field", "Missing required fields in list items"),
        ("invalid_dict_missing_field", "Missing required fields"),
    ])
    def test_validation_errors(self, base_data_toolkit, validation_test_cases, test_case, error_substring):
        """Test validation error scenarios."""
        result = DataValidator.validate_structure(
            validation_test_cases[test_case],
            required_fields=["symbol", "price"]
        )
        
        assert result["valid"] is False
        assert any(error_substring in error for error in result["errors"])
    
    def test_type_validation_error(self, base_data_toolkit, sample_crypto_data):
        """Test type validation errors."""
        result = DataValidator.validate_structure(sample_crypto_data, expected_type=dict)
        
        assert result["valid"] is False
        assert "Expected dict, got list" in result["errors"][0]
    
    def test_dataframe_column_validation(self, base_data_toolkit):
        """Test DataFrame column validation."""
        df = pd.DataFrame({"symbol": ["BTC"], "price": [50000]})
        
        result = DataValidator.validate_structure(df, required_fields=["symbol", "volume"])
        
        assert result["valid"] is False
        assert "Missing required columns: ['volume']" in result["errors"][0]


class TestDataSummary:
    """Test data summary generation."""
    
    def test_list_data_summary(self, initialized_base_toolkit, sample_crypto_data):
        """Test summary for list data."""
        summary = initialized_base_toolkit._get_data_summary(sample_crypto_data)
        
        assert summary["type"] == "list"
        assert summary["size"] == 3
        assert summary["empty"] is False
        assert summary["fields"] == ["symbol", "price", "volume", "change"]
        assert summary["should_store_parquet"] is False  # Below threshold
        assert "timestamp" in summary
    
    def test_dataframe_summary(self, initialized_base_toolkit, sample_dataframe):
        """Test summary for DataFrame."""
        summary = initialized_base_toolkit._get_data_summary(sample_dataframe)
        
        assert summary["type"] == "DataFrame"
        assert summary["size"] == 3
        assert set(summary["columns"]) == {"symbol", "price", "volume", "change"}
        assert "memory_mb" in summary
    
    def test_nested_dict_summary(self, initialized_base_toolkit, nested_api_response):
        """Test summary for nested dictionary."""
        summary = initialized_base_toolkit._get_data_summary(nested_api_response)
        
        assert summary["type"] == "dict"
        assert "keys" in summary  # Should have keys field for dict type
    
    def test_threshold_integration_in_summary(self, initialized_base_toolkit, large_dataset, small_dataset):
        """Test that summary correctly integrates threshold logic."""
        large_summary = initialized_base_toolkit._get_data_summary(large_dataset)
        small_summary = initialized_base_toolkit._get_data_summary(small_dataset)
        
        assert large_summary["should_store_parquet"] is True
        assert small_summary["should_store_parquet"] is False


class TestDirectoryCleanup:
    """Test directory cleanup functionality."""
    
    def test_cleanup_dry_run(self, initialized_base_toolkit, temp_file_structure):
        """Test cleanup in dry run mode."""
        result = initialized_base_toolkit._clean_data_directory(max_age_hours=24, dry_run=True)
        
        assert result["dry_run"] is True
        assert result["old_files_found"] == 1  # Only old_data.parquet is old
        assert result["deleted_count"] == 0
        assert temp_file_structure["old_file"].exists()  # File preserved
    
    def test_actual_cleanup(self, initialized_base_toolkit, temp_file_structure):
        """Test actual file cleanup."""
        result = initialized_base_toolkit._clean_data_directory(max_age_hours=24, dry_run=False)
        
        assert result["deleted_count"] == 1
        assert not temp_file_structure["old_file"].exists()  # Old file removed
        assert temp_file_structure["new_file"].exists()     # New file preserved
    
    def test_custom_pattern_cleanup(self, initialized_base_toolkit, temp_file_structure):
        """Test cleanup with custom file pattern."""
        # Make txt file old
        import time
        old_timestamp = time.time() - (25 * 3600)
        os.utime(temp_file_structure["txt_file"], (old_timestamp, old_timestamp))
        
        result = initialized_base_toolkit._clean_data_directory(
            max_age_hours=24, pattern="*.txt", dry_run=True
        )
        
        assert result["old_files_found"] == 1  # Only txt file matches
    
    def test_cleanup_without_initialization(self, base_data_toolkit):
        """Test cleanup error when not initialized."""
        with pytest.raises(ValueError, match="Data directory not initialized"):
            base_data_toolkit._clean_data_directory()
    
    def test_cleanup_deletion_error_handling(self, initialized_base_toolkit, temp_file_structure):
        """Test graceful handling of deletion errors."""
        with patch('os.remove', side_effect=PermissionError("Cannot delete")):
            result = initialized_base_toolkit._clean_data_directory(max_age_hours=24, dry_run=False)
            
            assert result["old_files_found"] == 1
            assert result["deleted_count"] == 0  # Nothing successfully deleted


@pytest.mark.integration
class TestIntegrationWorkflows:
    """Integration tests combining multiple features."""
    
    def test_complete_large_data_workflow(self, initialized_base_toolkit, large_dataset, assert_helpers):
        """Test complete workflow for large dataset."""
        # 1. Validate data
        validation = DataValidator.validate_structure(
            large_dataset, required_fields=["id", "symbol"], expected_type=list
        )
        assert validation["valid"] is True
        
        # 2. Check if should store as parquet
        should_store = initialized_base_toolkit._should_store_as_parquet(large_dataset)
        assert should_store is True
        
        # 3. Store as parquet
        file_path = initialized_base_toolkit._store_parquet(large_dataset, "large_crypto")
        assert_helpers.assert_parquet_file_created(file_path, expected_rows=50)
        
        # 4. Generate and verify summary
        summary = initialized_base_toolkit._get_data_summary(large_dataset)
        assert summary["should_store_parquet"] is True
        assert summary["size"] == 50
        
        # 5. Verify stored data integrity
        stored_df = pd.read_parquet(file_path)
        assert len(stored_df) == len(large_dataset)
        assert set(stored_df.columns) == {"id", "symbol", "price", "volume"}
    
    def test_small_data_workflow(self, initialized_base_toolkit, small_dataset, assert_helpers):
        """Test workflow for small dataset (no parquet storage)."""
        # Should not trigger parquet storage
        should_store = initialized_base_toolkit._should_store_as_parquet(small_dataset)
        assert should_store is False
        
        # Convert to DataFrame for analysis
        df = initialized_base_toolkit._convert_to_dataframe(small_dataset)
        assert len(df) == len(small_dataset)
        assert_helpers.assert_data_structure_valid(df, expected_fields=["id", "symbol"])
        
        # Summary should reflect no parquet storage needed
        summary = initialized_base_toolkit._get_data_summary(small_dataset)
        assert summary["should_store_parquet"] is False
        assert summary["size"] == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.parametrize("edge_data", [
        [{"single": "item"}],                    # Single item list
        {"single_key": ["value1", "value2"]},   # Single key dict
        pd.DataFrame({"col": [1]}),             # Single row DataFrame
    ])
    def test_minimal_data_structures(self, initialized_base_toolkit, edge_data):
        """Test handling of minimal data structures."""
        # Should handle gracefully without errors
        df = initialized_base_toolkit._convert_to_dataframe(edge_data)
        assert isinstance(df, pd.DataFrame)
        
        summary = initialized_base_toolkit._get_data_summary(edge_data)
        assert "type" in summary
        assert "timestamp" in summary
    
    def test_validation_with_no_requirements(self, base_data_toolkit, sample_crypto_data):
        """Test validation with no requirements specified."""
        result = DataValidator.validate_structure(sample_crypto_data)
        
        # Should pass validation when no requirements
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["data_type"] == "list"
    
    def test_complex_nested_data_handling(self, initialized_base_toolkit, nested_api_response):
        """Test handling of complex nested structures."""
        summary = initialized_base_toolkit._get_data_summary(nested_api_response)
        
        # Should handle complex structures gracefully
        assert summary["type"] == "dict"
        assert "keys" in summary
        # Should not crash on complex nested structures