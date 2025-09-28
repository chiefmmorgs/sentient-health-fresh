"""
Shared fixtures and configuration for toolkit tests.
This file provides common fixtures, mocks, and utilities used across all toolkit tests.
"""
import pytest
import tempfile
import time
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd
import asyncio


# ============================================================================
# SHARED MOCKS AND PATCHES
# ============================================================================

@pytest.fixture(autouse=True)
def mock_logger():
    """Auto-use fixture to mock logger across all toolkit tests."""
    with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.base.base_data.logger') as mock_log, \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.utils.http_client.logger') as mock_http_log, \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.binance_toolkit.logger') as mock_binance_log, \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.coingecko_toolkit.logger') as mock_coingecko_log:
        yield {
            'base': mock_log,
            'http': mock_http_log,
            'binance': mock_binance_log,
            'coingecko': mock_coingecko_log
        }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for HTTP testing."""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": []}
    mock_response.text = '{"status": "success"}'
    mock_response.raise_for_status = Mock()
    
    mock_client.request.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client.aclose = AsyncMock()
    
    return mock_client


# ============================================================================
# FILE SYSTEM FIXTURES
# ============================================================================

@pytest.fixture
def temp_data_dir():
    """Temporary directory for test data storage."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def temp_file_structure(temp_data_dir):
    """Create a temporary file structure for testing."""
    # Create subdirectories
    (temp_data_dir / "binance").mkdir()
    (temp_data_dir / "coingecko").mkdir()
    
    # Create test files with different ages
    old_file = temp_data_dir / "old_data.parquet"
    new_file = temp_data_dir / "new_data.parquet"
    txt_file = temp_data_dir / "readme.txt"
    
    for file in [old_file, new_file, txt_file]:
        file.touch()
    
    # Make old_file appear old (25 hours ago)
    old_timestamp = time.time() - (25 * 3600)
    os.utime(old_file, (old_timestamp, old_timestamp))
    
    return {
        'base_dir': temp_data_dir,
        'old_file': old_file,
        'new_file': new_file,
        'txt_file': txt_file,
        'binance_dir': temp_data_dir / "binance",
        'coingecko_dir': temp_data_dir / "coingecko"
    }


# ============================================================================
# DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_crypto_data():
    """Sample cryptocurrency data for testing."""
    return [
        {"symbol": "BTCUSDT", "price": 50000.0, "volume": 1000.0, "change": 2.5},
        {"symbol": "ETHUSDT", "price": 3000.0, "volume": 500.0, "change": 1.8},
        {"symbol": "ADAUSDT", "price": 1.5, "volume": 2000.0, "change": -0.5}
    ]


@pytest.fixture
def sample_dataframe(sample_crypto_data):
    """Sample DataFrame created from crypto data."""
    return pd.DataFrame(sample_crypto_data)


@pytest.fixture
def large_dataset():
    """Large dataset exceeding typical parquet thresholds."""
    return [
        {"id": i, "symbol": f"COIN{i}", "price": 1000 + i, "volume": 100 * i}
        for i in range(50)  # Large enough to trigger parquet storage
    ]


@pytest.fixture
def small_dataset():
    """Small dataset below parquet thresholds."""
    return [
        {"id": i, "symbol": f"COIN{i}", "price": 1000 + i}
        for i in range(3)  # Small dataset
    ]


@pytest.fixture
def nested_api_response():
    """Sample nested API response structure."""
    return {
        "status": "success",
        "data": {
            "prices": [50000, 3000, 1.5],
            "symbols": ["BTC", "ETH", "ADA"],
            "metadata": {
                "timestamp": 1640995200,
                "source": "binance_api",
                "count": 3
            }
        },
        "pagination": {
            "page": 1,
            "total_pages": 1,
            "total_items": 3
        }
    }


# ============================================================================
# TOOLKIT INSTANCE FIXTURES
# ============================================================================

@pytest.fixture
def base_data_toolkit():
    """Basic BaseDataToolkit instance."""
    from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit
    return BaseDataToolkit()


@pytest.fixture
def initialized_base_toolkit(base_data_toolkit, temp_data_dir):
    """Initialized BaseDataToolkit with temp directory."""
    base_data_toolkit._init_data_helpers(
        temp_data_dir, 
        parquet_threshold=10, 
        file_prefix="test_"
    )
    return base_data_toolkit


@pytest.fixture
def http_client():
    """HTTP client instance for testing."""
    from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import DataHTTPClient
    return DataHTTPClient(default_timeout=5.0)


@pytest.fixture
async def configured_http_client(mock_httpx_client):
    """HTTP client with pre-configured endpoints."""
    from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import DataHTTPClient
    
    with patch('httpx.AsyncClient', return_value=mock_httpx_client):
        client = DataHTTPClient(default_timeout=5.0)
        await client.add_endpoint("test_api", "https://api.example.com")
        await client.add_endpoint("binance", "https://api.binance.com")
        yield client
        await client.aclose()


# ============================================================================
# ASYNC TESTING UTILITIES
# ============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_context():
    """Async context manager for testing."""
    async def _context():
        # Setup
        yield
        # Teardown
    
    async with _context():
        yield


# ============================================================================
# VALIDATION AND ERROR TESTING FIXTURES
# ============================================================================

@pytest.fixture
def validation_test_cases():
    """Test cases for data validation testing."""
    return {
        'valid_list': [{"symbol": "BTC", "price": 50000, "volume": 100}],
        'invalid_list_missing_field': [{"symbol": "BTC", "volume": 100}],  # Missing price
        'valid_dict': {"symbol": "BTC", "price": 50000, "volume": 100},
        'invalid_dict_missing_field': {"symbol": "BTC", "volume": 100},  # Missing price
        'valid_dataframe': pd.DataFrame({"symbol": ["BTC"], "price": [50000]}),
        'invalid_dataframe': pd.DataFrame({"symbol": ["BTC"]}),  # Missing price column
        'empty_list': [],
        'empty_dict': {},
        'empty_dataframe': pd.DataFrame()
    }


@pytest.fixture
def http_error_scenarios():
    """Common HTTP error scenarios for testing."""
    return {
        'timeout': {'exception': 'TimeoutError', 'message': 'Request timeout'},
        'connection_error': {'exception': 'ConnectionError', 'message': 'Connection failed'},
        'http_404': {'status_code': 404, 'message': 'Not found'},
        'http_500': {'status_code': 500, 'message': 'Internal server error'},
        'invalid_json': {'status_code': 200, 'invalid_json': True}
    }


# ============================================================================
# PARAMETERIZED TEST DATA
# ============================================================================

@pytest.fixture
def threshold_test_data():
    """Data for testing parquet threshold logic."""
    return [
        # (data, threshold, expected_result, description)
        ([{"id": i} for i in range(5)], 10, False, "small_list_below_threshold"),
        ([{"id": i} for i in range(15)], 10, True, "large_list_above_threshold"), 
        (pd.DataFrame({"col": range(5)}), 10, False, "small_df_below_threshold"),
        (pd.DataFrame({"col": range(15)}), 10, True, "large_df_above_threshold"),
        ({"data": [{"id": i} for i in range(15)]}, 10, True, "dict_with_large_data_field"),
        ({"count": 15}, 10, True, "dict_with_count_above_threshold"),
        ({"size": 15}, 10, True, "dict_with_size_above_threshold"),
        ({"count": 5}, 10, False, "dict_with_count_below_threshold"),
    ]


@pytest.fixture 
def data_conversion_test_cases():
    """Test cases for DataFrame conversion testing."""
    return [
        # (input_data, expected_shape, expected_columns, description)
        ([{"a": 1, "b": 2}], (1, 2), ["a", "b"], "single_dict_list"),
        ([{"a": 1}, {"a": 2}], (2, 1), ["a"], "multi_dict_list"),
        ({"a": [1, 2], "b": [3, 4]}, (2, 2), ["a", "b"], "dict_of_lists"),
        (pd.DataFrame({"x": [1, 2]}), (2, 1), ["x"], "existing_dataframe"),
    ]


# ============================================================================
# MOCK FACTORIES
# ============================================================================

@pytest.fixture
def mock_api_response_factory():
    """Factory for creating mock API responses."""
    def _create_response(data=None, status_code=200, headers=None):
        mock_response = Mock()
        mock_response.status_code = status_code
        mock_response.headers = headers or {}
        mock_response.json.return_value = data or {"success": True}
        mock_response.text = str(data) if data else '{"success": true}'
        mock_response.raise_for_status = Mock()
        
        if status_code >= 400:
            from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import HTTPClientError
            mock_response.raise_for_status.side_effect = HTTPClientError(
                f"HTTP {status_code} error", status_code, mock_response.text
            )
        
        return mock_response
    
    return _create_response


@pytest.fixture
def mock_file_operations():
    """Mock file operations for testing without actual file I/O."""
    with patch('pandas.DataFrame.to_parquet') as mock_to_parquet, \
         patch('pandas.read_parquet') as mock_read_parquet, \
         patch('os.path.exists') as mock_exists, \
         patch('pathlib.Path.exists') as mock_path_exists:
        
        mock_exists.return_value = True
        mock_path_exists.return_value = True
        mock_to_parquet.return_value = None
        mock_read_parquet.return_value = pd.DataFrame({"test": [1, 2, 3]})
        
        yield {
            'to_parquet': mock_to_parquet,
            'read_parquet': mock_read_parquet,
            'exists': mock_exists,
            'path_exists': mock_path_exists
        }


# ============================================================================
# CUSTOM PYTEST MARKERS
# ============================================================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "async_test: marks tests as async tests"
    )
    config.addinivalue_line(
        "markers", "requires_network: marks tests that require network access"
    )


# ============================================================================
# TEST UTILITIES
# ============================================================================

@pytest.fixture
def assert_helpers():
    """Helper functions for common assertions."""
    class AssertHelpers:
        @staticmethod
        def assert_successful_response(response):
            """Assert that a response indicates success."""
            assert response.get("success") is True
            assert "error" not in response or response["error"] is None
        
        @staticmethod
        def assert_error_response(response, error_type=None):
            """Assert that a response indicates an error."""
            assert response.get("success") is False
            assert "message" in response
            if error_type:
                assert response.get("error_type") == error_type
        
        @staticmethod
        def assert_parquet_file_created(file_path, expected_rows=None):
            """Assert that a parquet file was created with expected content."""
            assert os.path.exists(file_path)
            assert file_path.endswith('.parquet')
            
            if expected_rows:
                df = pd.read_parquet(file_path)
                assert len(df) == expected_rows
        
        @staticmethod
        def assert_data_structure_valid(data, expected_fields=None):
            """Assert that data has expected structure."""
            if isinstance(data, list) and data:
                if expected_fields:
                    assert all(field in data[0] for field in expected_fields)
            elif isinstance(data, dict) and expected_fields:
                assert all(field in data for field in expected_fields)
            elif isinstance(data, pd.DataFrame) and expected_fields:
                assert all(field in data.columns for field in expected_fields)
    
    return AssertHelpers()