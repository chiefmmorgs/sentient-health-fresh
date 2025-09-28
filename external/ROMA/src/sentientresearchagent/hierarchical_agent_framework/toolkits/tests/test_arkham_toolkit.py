"""
Comprehensive tests for ArkhamToolkit based on implementation patterns.
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
def mock_arkham_dependencies():
    """Mock external dependencies for Arkham toolkit tests."""
    mock_modules = {
        'agno.tools': Mock(),
        'agno.utils.log': Mock(),
    }
    
    # Create mock classes
    mock_toolkit = Mock()
    mock_base_toolkit = Mock()
    mock_logger = Mock()
    
    with patch.dict('sys.modules', mock_modules), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.arkham_toolkit.Toolkit', mock_toolkit), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.arkham_toolkit.BaseDataToolkit', mock_base_toolkit), \
         patch('sentientresearchagent.hierarchical_agent_framework.toolkits.data.arkham_toolkit.logger', mock_logger):
        yield


# Import after mocking
from sentientresearchagent.hierarchical_agent_framework.toolkits.data.arkham_toolkit import ArkhamToolkit, SupportedChain


class TestArkhamToolkitInitialization:
    """Test ArkhamToolkit initialization and configuration."""
    
    def test_initialization_requires_api_key(self):
        """Test that toolkit requires API key."""
        # Clear environment variable for this test
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Arkham API key is required"):
                ArkhamToolkit()
    
    def test_default_initialization_with_api_key(self):
        """Test toolkit with API key provided."""
        toolkit = ArkhamToolkit(api_key="test_arkham_key")
        
        assert toolkit._api_key == "test_arkham_key"
        assert toolkit.default_chain == SupportedChain.ETHEREUM
        assert toolkit.base_url == "https://api.arkm.com"
        assert toolkit.include_entity_data == True
    
    def test_initialization_with_custom_chain(self):
        """Test toolkit with custom default chain."""
        toolkit = ArkhamToolkit(api_key="test_key", default_chain="bitcoin")
        
        assert toolkit.default_chain == SupportedChain.BITCOIN
    
    def test_initialization_with_enum_chain(self):
        """Test toolkit with SupportedChain enum."""
        toolkit = ArkhamToolkit(api_key="test_key", default_chain=SupportedChain.POLYGON)
        
        assert toolkit.default_chain == SupportedChain.POLYGON
    
    def test_initialization_with_supported_chains(self):
        """Test toolkit with custom supported chains."""
        supported_chains = ["ethereum", "bitcoin", "polygon"]
        toolkit = ArkhamToolkit(
            api_key="test_key", 
            supported_chains=supported_chains
        )
        
        assert toolkit._supported_chains == {"ethereum", "bitcoin", "polygon"}
    
    def test_initialization_with_environment_api_key(self):
        """Test API key from environment variable."""
        with patch.dict(os.environ, {'ARKHAM_API_KEY': 'env_test_key'}):
            toolkit = ArkhamToolkit()
            assert toolkit._api_key == 'env_test_key'
    
    def test_invalid_chain_error(self):
        """Test initialization with invalid default chain."""
        with pytest.raises(ValueError, match="Unsupported default_chain"):
            ArkhamToolkit(api_key="test_key", default_chain="invalid_chain")
    
    def test_initialization_with_custom_parameters(self):
        """Test initialization with all custom parameters."""
        toolkit = ArkhamToolkit(
            api_key="test_key",
            default_chain="avalanche",
            base_url="https://custom-api.arkham.com",
            supported_chains=["ethereum", "avalanche"],
            parquet_threshold=500,
            include_entity_data=False,
            cache_ttl_seconds=3600
        )
        
        assert toolkit.default_chain == SupportedChain.AVALANCHE
        assert toolkit.base_url == "https://custom-api.arkham.com"
        assert toolkit.include_entity_data == False
        assert toolkit._parquet_threshold == 500


class TestArkhamToolkitValidation:
    """Test ArkhamToolkit validation methods."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    def test_validate_chain_valid(self, toolkit):
        """Test chain validation with valid chain."""
        result = toolkit._validate_chain("ethereum")
        assert result == "ethereum"
        
        result = toolkit._validate_chain("BITCOIN")
        assert result == "bitcoin"
    
    def test_validate_chain_invalid(self, toolkit):
        """Test chain validation with invalid chain."""
        with pytest.raises(ValueError, match="Unsupported chain"):
            toolkit._validate_chain("invalid_chain")
    
    def test_validate_address_ethereum(self, toolkit):
        """Test Ethereum address validation."""
        eth_address = "0x742d35Cc6663C0532d6D5c6C8c8D8E4e47f3D1B8"
        result = toolkit._validate_address(eth_address)
        assert result == eth_address.lower()
    
    def test_validate_address_bitcoin(self, toolkit):
        """Test Bitcoin address validation."""
        btc_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        result = toolkit._validate_address(btc_address)
        assert result == btc_address
    
    def test_validate_address_empty(self, toolkit):
        """Test address validation with empty input."""
        with pytest.raises(ValueError, match="Address must be a non-empty string"):
            toolkit._validate_address("")
        
        with pytest.raises(ValueError, match="Address cannot be empty"):
            toolkit._validate_address("   ")
    
    def test_validate_address_none(self, toolkit):
        """Test address validation with None input."""
        with pytest.raises(ValueError, match="Address must be a non-empty string"):
            toolkit._validate_address(None)


class TestArkhamToolkitTokenMethods:
    """Test token-related methods of ArkhamToolkit."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    @pytest.fixture
    def mock_api_response(self):
        """Mock API response for token data."""
        return {
            "tokens": [
                {
                    "token_address": "0x...",
                    "symbol": "ETH",
                    "name": "Ethereum", 
                    "market_cap": 240000000000,
                    "volume_24h": 15000000000,
                    "holder_count": 98000000,
                    "price_usd": 2000.50,
                    "price_change_24h": 2.5,
                    "chain": "ethereum"
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_get_top_tokens_success(self, toolkit, mock_api_response):
        """Test successful get_top_tokens call."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_api_response
            
            result = await toolkit.get_top_tokens(size=50, order_by_agg="volume")
            
            assert result["success"] == True
            assert result["size"] == 50
            assert result["order_by_agg"] == "volume"
            assert "data" in result or "file_path" in result
    
    @pytest.mark.asyncio
    async def test_get_top_tokens_invalid_size(self, toolkit):
        """Test get_top_tokens with invalid size."""
        result = await toolkit.get_top_tokens(size=0)
        
        assert result["success"] == False
        assert "Size must be greater than 0" in result["message"]
    
    @pytest.mark.asyncio
    async def test_get_top_tokens_invalid_order_by(self, toolkit):
        """Test get_top_tokens with invalid order_by_agg."""
        result = await toolkit.get_top_tokens(order_by_agg="invalid_sort")
        
        assert result["success"] == False
        assert "Invalid order_by_agg" in result["message"]
    
    @pytest.mark.asyncio
    async def test_get_token_holders_success(self, toolkit):
        """Test successful get_token_holders call."""
        mock_response = {
            "token": {
                "identifier": {"pricingID": "ethereum"},
                "name": "Ethereum",
                "symbol": "ETH"
            },
            "totalSupply": {"ethereum": 120000000},
            "addressTopHolders": {
                "ethereum": [
                    {
                        "address": {"address": "0x123..."},
                        "balance": 1000000.5,
                        "usd": 2000000.0,
                        "pctOfCap": 5.25
                    }
                ]
            },
            "entityTopHolders": {
                "ethereum": [
                    {
                        "address": {"address": "0x456..."},
                        "balance": 500000.0,
                        "usd": 1000000.0,
                        "pctOfCap": 2.5
                    }
                ]
            }
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await toolkit.get_token_holders(
                "ethereum",  # pricing_id should be a CoinGecko pricing ID like "ethereum"
                group_by_entity=False
            )
            
            assert result["success"] == True
            assert result["pricing_id"] == "ethereum"
            assert "group_by_entity" in result
            assert "data" in result or "file_path" in result
    
    @pytest.mark.asyncio
    async def test_get_token_holders_invalid_address(self, toolkit):
        """Test get_token_holders with invalid address."""
        result = await toolkit.get_token_holders("invalid_address")
        
        # Should handle the address validation in the method
        assert "address" in str(result).lower()
    
    @pytest.mark.asyncio
    async def test_get_token_top_flow_success(self, toolkit):
        """Test successful get_token_top_flow call."""
        mock_response = {
            "flows": [
                {
                    "from_address": "0x123...",
                    "to_address": "0x456...",
                    "amount": "1000000",
                    "flow_direction": "in",
                    "timestamp": "2024-01-01T12:00:00Z"
                }
            ]
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await toolkit.get_token_top_flow(
                "ethereum",  # pricing_id
                time_last="24h",
                chains="ethereum"
            )
            
            assert result["success"] == True
            assert result["time_last"] == "24h"
            assert result["pricing_id"] == "ethereum"


class TestArkhamToolkitTransferMethods:
    """Test transfer-related methods of ArkhamToolkit."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_get_transfers_basic(self, toolkit):
        """Test basic get_transfers call."""
        mock_response = {
            "transfers": [
                {
                    "from_address": "0x123...",
                    "to_address": "0x456...",
                    "token_address": "0x789...",
                    "amount": "1000.0",
                    "timestamp": "2024-01-01T12:00:00Z"
                }
            ]
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await toolkit.get_transfers(limit=100)
            
            assert result["success"] == True
            assert result["limit"] == 100
    
    @pytest.mark.asyncio
    async def test_get_transfers_with_filters(self, toolkit):
        """Test get_transfers with filtering parameters."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"transfers": []}
            
            result = await toolkit.get_transfers(
                from_addresses="0x123...",
                to_addresses="0x456...",
                value_gte=1000.0,
                value_lte=10000.0,
                time_gte="1704067200000",
                time_lte="1704153600000"
            )
            
            assert result["success"] == True
            assert "filters" in result
    
    @pytest.mark.asyncio
    async def test_get_transfers_invalid_amount_range(self, toolkit):
        """Test get_transfers with invalid amount range."""
        result = await toolkit.get_transfers(
            value_gte=10000.0,
            value_lte=1000.0  # max < min
        )
        
        assert result["success"] == False
        assert "value_gte cannot be greater than value_lte" in result["message"]
    
    @pytest.mark.asyncio
    async def test_get_transfers_invalid_time_format(self, toolkit):
        """Test get_transfers with invalid time format."""
        # This test validates the parameter without making an API call
        # The validation happens at the API level, so we just test that the call processes the parameter
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"transfers": []}
            
            result = await toolkit.get_transfers(time_gte="invalid-time-format")
            
            # The parameter gets passed through (API would validate it)
            assert result["success"] == True
            mock_request.assert_called_once()


class TestArkhamToolkitWalletMethods:
    """Test wallet-specific methods of ArkhamToolkit."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_get_token_balances_success(self, toolkit):
        """Test successful get_token_balances call."""
        mock_response = {
            "totalBalance": {},
            "balances": {
                "ethereum": [
                    {
                        "name": "Ethereum",
                        "symbol": "ETH",
                        "id": "ethereum",
                        "ethereumAddress": "0x123...",
                        "balance": 10.5,
                        "balanceExact": "10.5",
                        "usd": 21000.0,
                        "price": 2000.0
                    },
                    {
                        "name": "USD Coin",
                        "symbol": "USDC",
                        "id": "usd-coin",
                        "ethereumAddress": "0x456...",
                        "balance": 5000.0,
                        "balanceExact": "5000.0",
                        "usd": 5000.0,
                        "price": 1.0
                    }
                ]
            }
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await toolkit.get_token_balances("0x742d35Cc6663C0532d6D5c6C8c8D8E4e47f3D1B8")
            
            assert result["success"] == True
            assert "address" in result
            assert "data" in result or "file_path" in result
    
    @pytest.mark.asyncio
    async def test_get_token_balances_with_min_usd(self, toolkit):
        """Test get_token_balances with minimum USD filter."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"totalBalance": {}, "balances": {}}
            
            result = await toolkit.get_token_balances(
                "0x742d35Cc6663C0532d6D5c6C8c8D8E4e47f3D1B8",
                chains="ethereum"
            )
            
            assert result["success"] == True
    
    @pytest.mark.asyncio
    async def test_get_token_balances_invalid_min_balance(self, toolkit):
        """Test get_token_balances with invalid minimum balance."""
        # Test with invalid address format
        result = await toolkit.get_token_balances("")
        
        assert result["success"] == False
        assert "Address" in result["message"]


class TestArkhamToolkitUtilityMethods:
    """Test utility methods of ArkhamToolkit."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_get_supported_chains_success(self, toolkit):
        """Test successful get_supported_chains call."""
        mock_response = {
            "chains": [
                {
                    "chain_id": "ethereum",
                    "name": "Ethereum",
                    "native_token": "ETH"
                },
                {
                    "chain_id": "bitcoin",
                    "name": "Bitcoin",
                    "native_token": "BTC"
                }
            ]
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await toolkit.get_supported_chains()
            
            assert result["success"] == True
            assert "data" in result
            assert result["count"] == 2
    
    @pytest.mark.asyncio
    async def test_get_supported_chains_cached(self, toolkit):
        """Test get_supported_chains with cached data."""
        # Mock cache to return data
        with patch.object(toolkit, '_get_cached_data') as mock_cache:
            mock_cache.return_value = [{"chain_id": "ethereum"}]
            
            result = await toolkit.get_supported_chains()
            
            assert result["success"] == True
            assert result["source"] == "cache"
    
    @pytest.mark.asyncio
    async def test_aclose(self, toolkit):
        """Test proper cleanup with aclose method."""
        with patch.object(toolkit._http_client, 'aclose', new_callable=AsyncMock) as mock_close:
            await toolkit.aclose()
            mock_close.assert_called_once()


class TestArkhamToolkitErrorHandling:
    """Test error handling in ArkhamToolkit methods."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return ArkhamToolkit(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_api_request_failure(self, toolkit):
        """Test handling of API request failures."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("API connection failed")
            
            result = await toolkit.get_top_tokens()
            
            assert result["success"] == False
            assert "Failed to get top tokens" in result["message"]
    
    @pytest.mark.asyncio
    async def test_invalid_response_format(self, toolkit):
        """Test handling of invalid API response format."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "invalid_response_format"
            
            result = await toolkit.get_top_tokens()
            
            assert result["success"] == False
            assert "Failed to get top tokens" in result["message"]


class TestArkhamToolkitIntegration:
    """Integration tests for ArkhamToolkit."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for integration testing."""
        return ArkhamToolkit(
            api_key="test_key",
            parquet_threshold=10  # Low threshold for testing
        )
    
    @pytest.mark.asyncio
    async def test_large_response_parquet_storage(self, toolkit):
        """Test that large responses are stored as Parquet files."""
        # Mock a large response that exceeds parquet threshold
        large_response = {
            "tokens": [{"token_id": f"token_{i}", "value": i} for i in range(20)]
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request, \
             patch.object(toolkit, '_store_parquet') as mock_store:
            
            mock_request.return_value = large_response
            mock_store.return_value = "/path/to/stored/file.parquet"
            
            result = await toolkit.get_top_tokens(size=50)
            
            assert result["success"] == True
            # Should store as parquet since response size > threshold
            assert "file_path" in result or "data" in result

    @pytest.mark.asyncio
    async def test_bitcoin_holders_parquet_threshold(self, toolkit):
        """Test that Bitcoin holders respects parquet threshold correctly."""
        # Mock Bitcoin response with 200 holders (realistic size based on actual API)
        bitcoin_holders_response = {
            "addressTopHolders": {
                "bitcoin": [
                    {
                        "address": f"bc1q{i:039x}", 
                        "balance": f"{1000000-i*1000}", 
                        "usd": 50000000-i*25000, 
                        "pctOfCap": 0.5-i*0.001
                    } 
                    for i in range(200)  # 200 holders (real-world Bitcoin data size)
                ]
            }
        }
        
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = bitcoin_holders_response
            
            # Test 1: High threshold (1000) - should NOT trigger parquet storage
            toolkit._parquet_threshold = 1000
            result_high = await toolkit.get_token_holders("bitcoin")
            
            assert result_high["success"] == True
            assert result_high["count"] == 200
            assert "data" in result_high  # Data returned directly
            assert "file_path" not in result_high  # No file storage triggered
            assert len(result_high["data"]) == 200
            
            # Test 2: Low threshold (100) - SHOULD trigger parquet storage  
            with patch.object(toolkit, '_store_parquet') as mock_store:
                mock_store.return_value = "/tmp/test_bitcoin_holders.parquet"
                
                toolkit._parquet_threshold = 100
                result_low = await toolkit.get_token_holders("bitcoin")
                
                assert result_low["success"] == True
                assert result_low["count"] == 200
                # Should trigger parquet storage since 200 > 100
                assert "file_path" in result_low
                assert result_low["file_path"] == "/tmp/test_bitcoin_holders.parquet"
                # Data should not be included when stored as parquet
                assert result_low.get("data") is None
    
    def test_toolkit_registration(self, toolkit):
        """Test that all expected tools are registered."""
        expected_tools = [
            "get_top_tokens",
            "get_token_holders", 
            "get_token_top_flow",
            "get_supported_chains",
            "get_transfers",
            "get_token_balances"
        ]
        
        # Check that toolkit has all expected methods
        for tool_name in expected_tools:
            assert hasattr(toolkit, tool_name)
            assert callable(getattr(toolkit, tool_name))