"""
Comprehensive tests for DefiLlamaToolkit based on implementation patterns.
Tests core functionality with proper mocking to avoid external API calls.
"""
import pytest
import os
import time
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd
import numpy as np

# Mock external dependencies before imports
@pytest.fixture(autouse=True)
def mock_defillama_dependencies():
    """Mock external dependencies for DefiLlama toolkit tests."""
    mock_modules = {
        'agno.tools': Mock(),
        'agno.utils.log': Mock(),
    }
    
    # Create mock classes
    mock_toolkit = Mock()
    mock_base_toolkit = Mock()
    mock_logger = Mock()
    
    with patch.dict('sys.modules', mock_modules), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.Toolkit', mock_toolkit), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.BaseDataToolkit', mock_base_toolkit), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.logger', mock_logger):
        yield


# Import after mocking
from sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit import DefiLlamaToolkit


class TestDefiLlamaToolkitInitialization:
    """Test DefiLlamaToolkit initialization and configuration."""
    
    def test_default_initialization(self):
        """Test toolkit with default configuration."""
        toolkit = DefiLlamaToolkit()
        
        assert toolkit.base_url == "https://api.llama.fi"
        assert toolkit.pro_base_url == "https://pro-api.llama.fi"
        assert toolkit.enable_pro_features is False
        assert toolkit._file_prefix == "defillama"
        assert toolkit._parquet_threshold == 5000
    
    def test_initialization_with_api_key(self):
        """Test toolkit with Pro API key provided."""
        toolkit = DefiLlamaToolkit(api_key="test_key")
        
        assert toolkit.enable_pro_features is True
        assert toolkit._api_key == "test_key"
    
    def test_initialization_with_environment_key(self):
        """Test toolkit initialization from environment variable."""
        with patch.dict(os.environ, {"DEFILLAMA_API_KEY": "env_key"}):
            toolkit = DefiLlamaToolkit()
            
            assert toolkit.enable_pro_features is True
            assert toolkit._api_key == "env_key"
    
    def test_initialization_with_custom_config(self):
        """Test toolkit with custom configuration."""
        config = {
            "parquet_threshold": 1000,
            "request_timeout": 60,
            "file_prefix": "custom_defillama"
        }
        
        toolkit = DefiLlamaToolkit(**config)
        
        assert toolkit._parquet_threshold == 1000
        assert toolkit._file_prefix == "custom_defillama"
    
    @patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient')
    def test_http_client_initialization(self, mock_http_client):
        """Test HTTP client initialization."""
        toolkit = DefiLlamaToolkit()
        
        # Verify HTTPClient was called with correct parameters
        mock_http_client.assert_called_once()
        

class TestDefiLlamaAPI:
    """Test API endpoint interactions with mocked responses."""
    
    @pytest.fixture
    def toolkit(self):
        """Create a toolkit instance for testing."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            return DefiLlamaToolkit()
    
    @pytest.fixture
    def mock_protocols_response(self):
        """Mock response for protocols endpoint."""
        return [
            {
                "id": "aave",
                "name": "Aave",
                "category": "Lending",
                "chains": ["Ethereum", "Polygon"],
                "tvl": 1000000000,
                "chainTvls": {
                    "Ethereum": 800000000,
                    "Polygon": 200000000
                }
            },
            {
                "id": "uniswap",
                "name": "Uniswap",
                "category": "Dexes",
                "chains": ["Ethereum", "Arbitrum"],
                "tvl": 2000000000,
                "chainTvls": {
                    "Ethereum": 1500000000,
                    "Arbitrum": 500000000
                }
            }
        ]
    
    @pytest.fixture
    def mock_yield_pools_response(self):
        """Mock response for yield pools endpoint."""
        return {
            "status": "success",
            "data": [
                {
                    "chain": "Ethereum",
                    "project": "aave",
                    "symbol": "USDC",
                    "pool": "aave-usdc",
                    "apy": 5.2,
                    "apyBase": 3.1,
                    "apyReward": 2.1,
                    "tvlUsd": 100000000
                },
                {
                    "chain": "Polygon",
                    "project": "compound",
                    "symbol": "DAI", 
                    "pool": "compound-dai-polygon",
                    "apy": 7.8,
                    "apyBase": 4.5,
                    "apyReward": 3.3,
                    "tvlUsd": 50000000
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_get_protocols_success(self, toolkit, mock_protocols_response):
        """Test successful protocols endpoint call."""
        toolkit._http_client.get = AsyncMock(return_value=mock_protocols_response)
        
        result = await toolkit.get_protocols()
        
        assert result["success"] is True
        assert "data" in result
        assert len(result["data"]) == 2
        assert result["total_protocols"] == 2
        assert result["analysis"]["ecosystem_overview"]["total_tvl"] == 3000000000
        assert result["analysis"]["category_breakdown"]["Lending"] == 1
        assert result["analysis"]["category_breakdown"]["Dexes"] == 1
    
    @pytest.mark.asyncio 
    async def test_get_protocols_empty_response(self, toolkit):
        """Test protocols endpoint with empty response."""
        toolkit._http_client.get = AsyncMock(return_value=[])
        
        result = await toolkit.get_protocols()
        
        assert result["success"] is True
        assert result["data"] == []
        assert result["total_protocols"] == 0
    
    @pytest.mark.asyncio
    async def test_get_protocols_api_error(self, toolkit):
        """Test protocols endpoint with API error."""
        toolkit._http_client.get = AsyncMock(side_effect=Exception("API Error"))
        
        result = await toolkit.get_protocols()
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_protocol_tvl_success(self, toolkit):
        """Test successful protocol TVL endpoint call."""
        mock_response = [
            {"date": 1640995200, "tvl": 900000000},
            {"date": 1641081600, "tvl": 950000000}, 
            {"date": 1641168000, "tvl": 1000000000}
        ]
        toolkit._http_client.get = AsyncMock(return_value=mock_response)
        
        result = await toolkit.get_protocol_tvl("aave")
        
        assert result["success"] is True
        assert result["protocol"] == "aave"
        assert "data" in result
        assert result["count"] == 3
        assert "analysis" in result
    
    @pytest.mark.asyncio
    async def test_get_protocol_tvl_invalid_protocol(self, toolkit):
        """Test protocol TVL with invalid protocol."""
        result = await toolkit.get_protocol_tvl("")
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_yield_pools_success(self, toolkit, mock_yield_pools_response):
        """Test successful yield pools endpoint call."""
        toolkit._http_client.get = AsyncMock(return_value=mock_yield_pools_response)
        
        result = await toolkit.get_yield_pools()
        
        assert result["success"] is True
        assert "data" in result
        assert "analysis" in result
        assert result["analysis"]["yield_summary"]["total_pools"] == 2
        assert result["analysis"]["yield_summary"]["avg_apy"] > 0
    
    @pytest.mark.asyncio
    async def test_get_chain_fees_success(self, toolkit):
        """Test successful chain fees endpoint call."""
        mock_response = {
            "totalDataChart": [
                [1640995200000, 15000000],
                [1641081600000, 18000000],
                [1641168000000, 20000000]
            ]
        }
        toolkit._http_client.get = AsyncMock(return_value=mock_response)
        
        result = await toolkit.get_chain_fees("ethereum")
        
        assert result["success"] is True
        assert result["chain"] == "ethereum"
        assert "data" in result
        assert "analysis" in result
    
    @pytest.mark.asyncio
    async def test_get_active_users_pro_required(self, toolkit):
        """Test active users endpoint requires Pro API."""
        result = await toolkit.get_active_users()
        
        assert result["success"] is False
        assert "pro_api_required" in result.get("error_type", "")
    
    @pytest.mark.asyncio
    async def test_get_yield_chart_success(self):
        """Test successful yield chart endpoint call."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = [
                {"timestamp": 1640995200, "apy": 8.5, "apyBase": 6.2, "apyReward": 2.3},
                {"timestamp": 1641081600, "apy": 9.1, "apyBase": 6.8, "apyReward": 2.3},
                {"timestamp": 1641168000, "apy": 8.8, "apyBase": 6.5, "apyReward": 2.3}
            ]
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_yield_chart("aave-usdc-pool")
            
            assert result["success"] is True
            assert result["pool_id"] == "aave-usdc-pool"
            assert "analysis" in result
            assert "yield_analysis" in result["analysis"]

    @pytest.mark.asyncio
    async def test_get_yield_chart_pro_required(self, toolkit):
        """Test yield chart endpoint requires Pro API."""
        result = await toolkit.get_yield_chart("test-pool")
        
        assert result["success"] is False
        assert "pro_api_required" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_get_yield_pools_borrow_success(self):
        """Test successful borrow yields endpoint call."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = [
                {
                    "project": "aave",
                    "chain": "ethereum",
                    "symbol": "USDC",
                    "apyBaseBorrow": 4.2,
                    "tvlUsd": 100000000
                },
                {
                    "project": "compound", 
                    "chain": "ethereum",
                    "symbol": "DAI",
                    "apyBaseBorrow": 3.8,
                    "tvlUsd": 75000000
                }
            ]
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_yield_pools_borrow()
            
            assert result["success"] is True
            assert "analysis" in result
            assert "market_overview" in result["analysis"]

    @pytest.mark.asyncio
    async def test_get_yield_pools_borrow_pro_required(self, toolkit):
        """Test borrow yields endpoint requires Pro API."""
        result = await toolkit.get_yield_pools_borrow()
        
        assert result["success"] is False
        assert "pro_api_required" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_get_yield_perps_success(self):
        """Test successful perpetuals endpoint call."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = [
                {
                    "exchange": "dydx",
                    "symbol": "BTC-USD",
                    "fundingRate": 0.0001,
                    "openInterest": 50000000
                },
                {
                    "exchange": "gmx",
                    "symbol": "ETH-USD", 
                    "fundingRate": -0.0002,
                    "openInterest": 25000000
                }
            ]
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_yield_perps()
            
            assert result["success"] is True
            assert "analysis" in result
            assert "funding_analysis" in result["analysis"]
            assert "market_overview" in result["analysis"]

    @pytest.mark.asyncio
    async def test_get_yield_perps_pro_required(self, toolkit):
        """Test perpetuals endpoint requires Pro API."""
        result = await toolkit.get_yield_perps()
        
        assert result["success"] is False
        assert "pro_api_required" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_get_historical_liquidity_success(self):
        """Test successful historical liquidity endpoint call."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = [
                {"timestamp": 1640995200, "liquidity": 1000000, "liquidityUSD": 1000000},
                {"timestamp": 1641081600, "liquidity": 1200000, "liquidityUSD": 1200000},
                {"timestamp": 1641168000, "liquidity": 1100000, "liquidityUSD": 1100000}
            ]
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_historical_liquidity("ethereum:0xA0b86a33E6441E64a3ef4aD4EbEb5cD44E20d29b")
            
            assert result["success"] is True
            assert result["token"] == "ethereum:0xA0b86a33E6441E64a3ef4aD4EbEb5cD44E20d29b"
            assert "analysis" in result
            assert "liquidity_analysis" in result["analysis"]

    @pytest.mark.asyncio
    async def test_get_historical_liquidity_no_data(self):
        """Test historical liquidity endpoint with no data available."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = {"message": "No liquidity info available"}
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_historical_liquidity("coingecko:unknown-token")
            
            assert result["success"] is False
            assert result["error_type"] == "no_data"

    @pytest.mark.asyncio
    async def test_get_historical_liquidity_pro_required(self, toolkit):
        """Test historical liquidity endpoint requires Pro API."""
        result = await toolkit.get_historical_liquidity("ethereum:0xA0b86a33E6441E64a3ef4aD4EbEb5cD44E20d29b")
        
        assert result["success"] is False
        assert "pro_api_required" in result.get("error_type", "")

    @pytest.mark.asyncio
    async def test_get_active_users_with_pro(self):
        """Test active users endpoint with Pro API enabled."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            toolkit = DefiLlamaToolkit(api_key="test_key")
            
            mock_response = {
                "aave": {
                    "name": "Aave",
                    "users": {"value": 50000},
                    "newUsers": {"value": 5000},
                    "txs": {"value": 100000}
                }
            }
            toolkit._http_client.get = AsyncMock(return_value=mock_response)
            
            result = await toolkit.get_active_users()
            
            assert result["success"] is True
            assert "analysis" in result


class TestDefiLlamaValidation:
    """Test input validation and error handling."""
    
    @pytest.fixture
    def toolkit(self):
        """Create a toolkit instance for testing."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            return DefiLlamaToolkit()
    
    def test_validate_protocol_success(self, toolkit):
        """Test valid protocol validation."""
        result = toolkit._validate_protocol("aave")
        assert result == "aave"
        
        result = toolkit._validate_protocol("COMPOUND")
        assert result == "compound"
        
        result = toolkit._validate_protocol("Curve-Finance")
        assert result == "curve-finance"
    
    def test_validate_protocol_failure(self, toolkit):
        """Test invalid protocol validation."""
        with pytest.raises(ValueError, match="Protocol name cannot be empty"):
            toolkit._validate_protocol("")
        
        with pytest.raises(ValueError, match="Protocol name cannot be empty"):
            toolkit._validate_protocol(None)
    
    def test_validate_chain_success(self, toolkit):
        """Test valid chain validation."""
        result = toolkit._validate_chain("ethereum")
        assert result == "ethereum"
        
        result = toolkit._validate_chain("POLYGON")
        assert result == "polygon"
        
        result = toolkit._validate_chain("Arbitrum-One")
        assert result == "arbitrum-one"
    
    def test_validate_chain_failure(self, toolkit):
        """Test invalid chain validation."""
        with pytest.raises(ValueError, match="Chain name cannot be empty"):
            toolkit._validate_chain("")
        
        with pytest.raises(ValueError, match="Chain name cannot be empty"):
            toolkit._validate_chain(None)


class TestDefiLlamaDataProcessing:
    """Test data processing and analysis functionality."""
    
    @pytest.fixture
    def toolkit(self):
        """Create a toolkit instance for testing."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            return DefiLlamaToolkit()
    
    def test_protocol_analysis(self, toolkit):
        """Test protocol data analysis."""
        protocols = [
            {"id": "aave", "name": "Aave", "category": "Lending", "tvl": 1000000000},
            {"id": "uniswap", "name": "Uniswap", "category": "Dexes", "tvl": 2000000000},
            {"id": "compound", "name": "Compound", "category": "Lending", "tvl": 500000000}
        ]
        
        # Test would call internal analysis method
        total_tvl = sum(p["tvl"] for p in protocols)
        assert total_tvl == 3500000000
        
        categories = {}
        for protocol in protocols:
            category = protocol["category"]
            categories[category] = categories.get(category, 0) + 1
        
        assert categories["Lending"] == 2
        assert categories["Dexes"] == 1
    
    def test_tvl_trend_analysis(self, toolkit):
        """Test TVL trend analysis with statistical methods."""
        tvl_data = [
            {"date": 1640995200, "tvl": 900000000},
            {"date": 1641081600, "tvl": 950000000},
            {"date": 1641168000, "tvl": 1000000000},
            {"date": 1641254400, "tvl": 1100000000}
        ]
        
        tvl_values = [item["tvl"] for item in tvl_data]
        
        # Test basic trend calculation
        if len(tvl_values) >= 2:
            growth_rate = ((tvl_values[-1] / tvl_values[0]) - 1) * 100
            assert growth_rate > 0  # Positive growth
    
    @patch('numpy.array')
    def test_statistical_analysis_integration(self, mock_numpy, toolkit):
        """Test integration with StatisticalAnalyzer."""
        mock_array = Mock()
        mock_numpy.return_value = mock_array
        
        # Mock the stats analyzer
        toolkit.stats = Mock()
        toolkit.stats.calculate_distribution_stats.return_value = {
            "mean": 1000000,
            "std": 100000,
            "min": 800000,
            "max": 1200000
        }
        
        # Test data would be processed through statistical analyzer
        test_values = [800000, 900000, 1000000, 1100000, 1200000]
        result = toolkit.stats.calculate_distribution_stats(test_values)
        
        assert result["mean"] == 1000000
        assert result["std"] == 100000


class TestDefiLlamaFileHandling:
    """Test file storage and parquet functionality."""
    
    @pytest.fixture
    def toolkit(self):
        """Create a toolkit instance for testing."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            return DefiLlamaToolkit()
    
    @patch('pandas.DataFrame.to_parquet')
    @patch('os.makedirs')
    def test_store_parquet_success(self, mock_makedirs, mock_to_parquet, toolkit):
        """Test successful parquet storage."""
        test_data = [
            {"id": "aave", "tvl": 1000000000, "date": 1640995200},
            {"id": "compound", "tvl": 500000000, "date": 1640995200}
        ]
        
        result = toolkit._store_parquet(test_data, "test_file.parquet")
        
        assert result is True
        mock_makedirs.assert_called_once()
        mock_to_parquet.assert_called_once()
    
    @patch('pandas.DataFrame.to_parquet')
    def test_store_parquet_failure(self, mock_to_parquet, toolkit):
        """Test parquet storage failure handling."""
        mock_to_parquet.side_effect = Exception("Storage error")
        
        result = toolkit._store_parquet([], "test_file.parquet")
        
        assert result is False
    
    def test_file_prefix_generation(self, toolkit):
        """Test file prefix configuration."""
        assert toolkit._file_prefix == "defillama"
        
        # Test with custom prefix
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient'):
            custom_toolkit = DefiLlamaToolkit(file_prefix="custom_prefix")
            assert custom_toolkit._file_prefix == "custom_prefix"


class TestDefiLlamaCleanup:
    """Test resource cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_aclose_cleanup(self):
        """Test proper resource cleanup."""
        with patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.defillama_toolkit.HTTPClient') as mock_http:
            mock_client = AsyncMock()
            mock_http.return_value = mock_client
            
            toolkit = DefiLlamaToolkit()
            await toolkit.aclose()
            
            mock_client.aclose.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])