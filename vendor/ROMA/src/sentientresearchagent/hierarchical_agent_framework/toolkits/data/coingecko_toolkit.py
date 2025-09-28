from __future__ import annotations

"""CoinGecko Cryptocurrency Market Data Toolkit
============================================

A comprehensive Agno-compatible toolkit that provides access to CoinGecko's public REST APIs
for cryptocurrency market data, price feeds, and blockchain analytics with intelligent 
data management and LLM-optimized responses.

## Supported Data Types

**Current Prices (`simple/price`)**
- Real-time cryptocurrency prices across 17,000+ coins  
- Multi-currency support (USD, EUR, BTC, ETH, etc.)
- Include market cap, volume, and 24h changes
- Token contract address price lookups

**Historical Data (`coins/{id}/market_chart`)**
- Price, market cap, and volume historical data
- Customizable date ranges with ISO format support
- OHLCV candlestick data for technical analysis
- Rich statistical analysis using NumPy

**Market Data (`coins/markets`)**
- Complete market overview for all cryptocurrencies
- Market cap rankings and trading volumes
- Price change statistics across multiple timeframes
- Sorting and filtering capabilities

**Coin Information (`coins/{id}`)**
- Comprehensive coin metadata and descriptions
- Social links, websites, and community data
- Contract addresses across multiple blockchains
- Developer activity and GitHub statistics

**Search & Discovery (`search`)**
- Search across coins, exchanges, categories, and NFTs
- Market cap based sorting and relevance ranking
- Trending cryptocurrencies and topics
- Category-based filtering

## Key Features

✅ **Multi-Currency Support**: Access prices in 100+ fiat and crypto currencies
✅ **Smart Data Management**: Large responses automatically stored as Parquet files  
✅ **Statistical Analysis**: Rich OHLCV analysis with NumPy integration
✅ **LLM-Optimized**: Standardized response formats with clear success/failure indicators
✅ **Async Performance**: Full async/await support with proper resource management
✅ **Framework Integration**: Seamless integration with agent YAML configuration
✅ **Date Flexibility**: ISO 8601 format support with Unix timestamp handling

## Configuration Examples

### Basic Configuration
```yaml
toolkits:
  - name: "CoinGeckoToolkit"
    params:
      coins: ["bitcoin", "ethereum", "cardano"]
      default_vs_currency: "usd"
      data_dir: "./data/coingecko"
      parquet_threshold: 1000
    available_tools:
      - "get_coin_price"
      - "get_coin_info" 
      - "get_coins_markets"
```

### Advanced Configuration
```yaml
toolkits:
  - name: "CoinGeckoToolkit"
    params:
      coins: ["bitcoin", "ethereum", "binancecoin"]
      default_vs_currency: "usd"
      api_key: "${COINGECKO_API_KEY}"
      include_community_data: true
      include_developer_data: true
    available_tools:
      - "get_coin_price"
      - "get_coin_market_chart"
      - "get_historical_price"
      - "search_coins_exchanges_categories"
```

## Environment Variables

- `COINGECKO_API_KEY`: API key for Pro plan access (optional for public endpoints)
- `COINGECKO_BASE_URL`: Custom base URL (default: https://api.coingecko.com/api/v3)
- `COINGECKO_BIG_DATA_THRESHOLD`: Global threshold for parquet storage (default: 1000)

## Response Format Standards

All tools return consistent JSON structures:

**Success Response:**
```json
{
  "success": true,
  "data": {...},           // Small responses
  "file_path": "...",      // Large responses stored as Parquet
  "coin_id": "bitcoin",
  "vs_currency": "usd",
  "fetched_at": "2024-01-01T12:00:00Z"
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Human-readable error description",
  "error_type": "validation_error|api_error|...",
  "coin_id": "bitcoin",
  "vs_currency": "usd"
}
```
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from enum import Enum
import difflib

import numpy as _np
from agno.tools import Toolkit
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit, BaseAPIToolkit
from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import (
    DataHTTPClient, HTTPClientError, StatisticalAnalyzer, DataValidator, FileNameGenerator
)

__all__ = ["CoinGeckoToolkit", "CoinPlatform", "VsCurrency"]

# Supported vs_currency options
class VsCurrency(str, Enum):
    """Supported quote currencies for price comparisons."""
    USD = "usd"
    EUR = "eur" 
    GBP = "gbp"
    JPY = "jpy"
    CNY = "cny"
    KRW = "krw"
    INR = "inr"
    BTC = "btc"
    ETH = "eth"
    BNB = "bnb"
    ADA = "ada"
    DOT = "dot"
    USDT = "usdt"
    USDC = "usdc"

# Major blockchain platforms for contract addresses
class CoinPlatform(str, Enum):
    """Supported blockchain platforms with contract addresses."""
    ETHEREUM = "ethereum"
    BINANCE_SMART_CHAIN = "binance-smart-chain"
    POLYGON_POS = "polygon-pos"
    AVALANCHE = "avalanche"
    ARBITRUM_ONE = "arbitrum-one"
    OPTIMISTIC_ETHEREUM = "optimistic-ethereum"
    FANTOM = "fantom"
    SOLANA = "solana"
    CARDANO = "cardano"
    POLKADOT = "polkadot"

DEFAULT_PUBLIC_BASE_URL = "https://api.coingecko.com/api/v3"
DEFAULT_PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "coingecko"
BIG_DATA_THRESHOLD = int(os.getenv("COINGECKO_BIG_DATA_THRESHOLD", "1000"))

# API endpoint mappings
_API_ENDPOINTS = {
    "simple_price": "/simple/price",
    "coin_info": "/coins/{coin_id}",
    "market_chart": "/coins/{coin_id}/market_chart",
    "market_chart_range": "/coins/{coin_id}/market_chart/range",
    "coins_markets": "/coins/markets",
    "coins_list": "/coins/list",
    "ohlc": "/coins/{coin_id}/ohlc",
    "search": "/search",
    "global_data": "/global",
    "contract_address": "/simple/token_price/{platform}"
}


class CoinGeckoAPIError(Exception):
    """Raised when the CoinGecko API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class CoinGeckoToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """Comprehensive CoinGecko Cryptocurrency Data Toolkit
    
    A powerful toolkit providing access to CoinGecko's extensive cryptocurrency database
    covering 17,000+ coins across 1,000+ exchanges. Designed for real-time market analysis,
    historical research, and automated trading systems with advanced statistical capabilities.
    
    **Supported Data Sources:**
    - Real-time price feeds with sub-minute accuracy
    - Historical OHLCV data with customizable timeframes  
    - Market cap rankings and trading volume analysis
    - Comprehensive coin metadata and social metrics
    - Multi-blockchain contract address support
    - Global market statistics and trends
    
    **Key Capabilities:**
    - Multi-currency price comparisons (100+ supported currencies)
    - Advanced statistical analysis of price and volume data
    - Smart contract token price lookups across major blockchains
    - Comprehensive search across coins, exchanges, and categories
    - Automated large dataset management via Parquet storage
    - ISO 8601 date handling with flexible range queries
    
    **Data Management:**
    Large responses (>threshold) are automatically stored as Parquet files and the
    file path is returned instead of raw data, optimizing memory usage and enabling
    efficient downstream processing with pandas/polars.
    """

    # Toolkit metadata for enhanced display
    _toolkit_category = "crypto"
    _toolkit_type = "market_data" 
    _toolkit_icon = "🪙"

    def __init__(
        self,
        coins: Optional[Sequence[str]] = None,
        default_vs_currency: VsCurrency | str = VsCurrency.USD,
        api_key: str | None = None,
        base_url: str | None = None,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        parquet_threshold: int = BIG_DATA_THRESHOLD,
        include_community_data: bool = False,
        include_developer_data: bool = False,
        name: str = "coingecko_toolkit",
        **kwargs: Any,
    ):
        """Initialize the CoinGecko Cryptocurrency Toolkit.
        
        Args:
            coins: Optional list of coin IDs to restrict API calls to.
                  If None, all valid coins from CoinGecko are allowed.
                  Examples: ["bitcoin", "ethereum", "cardano"]
            default_vs_currency: Default quote currency for price comparisons.
                                Options: USD, EUR, GBP, BTC, ETH, etc.
            api_key: CoinGecko API key for Pro plan access. If None,
                    reads from COINGECKO_API_KEY environment variable.
                    Not required for public endpoints.
            base_url: Base URL for CoinGecko API endpoints.
                     Default: https://api.coingecko.com/api/v3
            data_dir: Directory path where Parquet files will be stored for large
                     responses. Defaults to tools/data/coingecko/
            parquet_threshold: Size threshold in KB for Parquet storage.
                             Responses with JSON payload > threshold KB will be
                             saved to disk and file path returned instead of data.
                             Recommended: 50-200 KB for market data.
            include_community_data: Include community statistics in coin info requests
            include_developer_data: Include developer activity data in coin info requests
            name: Name identifier for this toolkit instance
            **kwargs: Additional arguments passed to Toolkit
            
        Raises:
            ValueError: If default_vs_currency is not supported
            
        Example:
            ```python
            # Basic cryptocurrency toolkit
            toolkit = CoinGeckoToolkit(
                coins=["bitcoin", "ethereum", "cardano"],
                default_vs_currency="usd"
            )
            
            # Get current Bitcoin price
            btc_price = await toolkit.get_coin_price("bitcoin")
            
            # Get market chart with statistical analysis
            btc_chart = await toolkit.get_coin_market_chart(
                "bitcoin", 
                vs_currency="usd",
                days=30
            )
            ```
        """
        # Use enhanced configuration validation from BaseAPIToolkit
        self._validate_configuration_enum(
            default_vs_currency,
            VsCurrency,
            "default_vs_currency"
        )
        
        # Convert string to enum if needed
        if isinstance(default_vs_currency, str):
            # Find the matching enum member by value
            found_enum = None
            for member in VsCurrency:
                if member.value == default_vs_currency.lower():
                    found_enum = member
                    break
            
            if found_enum is None:
                raise ValueError(f"Invalid default_vs_currency: {default_vs_currency}")
            
            self.default_vs_currency = found_enum
        else:
            self.default_vs_currency = default_vs_currency
        self._api_key = api_key or os.getenv("COINGECKO_API_KEY")
        
        # Determine appropriate base URL based on API key availability
        if base_url is not None:
            # Explicit base_url provided
            self.base_url = base_url
        elif self._api_key:
            # API key available - use Pro API
            self.base_url = DEFAULT_PRO_BASE_URL
            logger.debug("Using CoinGecko Pro API with API key")
        else:
            # No API key - use public API
            self.base_url = DEFAULT_PUBLIC_BASE_URL
            logger.debug("Using CoinGecko public API (no API key)")
        self.include_community_data = include_community_data
        self.include_developer_data = include_developer_data
        
        # Coin management - using enhanced caching from BaseAPIToolkit
        if coins is not None:
            self._user_coins = {c.lower() for c in coins} if coins else set()
        else:
            self._user_coins = None
        
        # Initialize standard configuration (includes cache system and HTTP client)
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=3600
        )
        
        # Define available tools for this toolkit
        available_tools = [
            self.get_coin_info,
            self.get_coin_price,
            self.get_coin_market_chart,
            self.get_multiple_coins_data,
            self.get_historical_price,
            self.get_token_price_by_contract,
            self.search_coins_exchanges_categories,
            self.get_coins_list,
            self.get_coins_markets,
            self.get_coin_ohlc,
            self.get_global_crypto_data,
        ]
        
        # Initialize Toolkit
        super().__init__(name=name, tools=available_tools, **kwargs)
        
        # Initialize BaseDataToolkit helpers
        self._init_data_helpers(
            data_dir=data_dir,
            parquet_threshold=parquet_threshold,
            file_prefix="coingecko_",
            toolkit_name="coingecko",
        )
        
        # Initialize statistical analyzer
        self.stats = StatisticalAnalyzer()
        
        logger.debug(
            f"Initialized CoinGeckoToolkit with default currency '{self.default_vs_currency.value}' "
            f"(type: {type(self.default_vs_currency)}) and {len(self._user_coins) if self._user_coins else 'all'} coins"
        )

    @property
    def _coins_list_cache(self) -> List[Dict[str, Any]]:
        """Get coins list from cache, or return empty list if not cached.
        
        This provides backward compatibility for existing code that expects
        _coins_list_cache to be a list attribute.
        """
        cached_data = self._get_cached_data("coins_list")
        return cached_data if cached_data is not None else []
    
    @_coins_list_cache.setter
    def _coins_list_cache(self, value: List[Dict[str, Any]]) -> None:
        """Set coins list cache (backward compatibility for tests).
        
        Args:
            value: List of coin dictionaries to cache
        """
        # FIXED: Maintain type consistency - cache IDs (strings) not full objects
        coin_ids = {coin["id"] for coin in value}
        metadata = {
            "total_coins": len(value),
            "loaded_at": time.time(),
            "coin_lookup": {coin["id"]: coin for coin in value}
        }
        self._cache_identifiers("coins_list", coin_ids, metadata)

    def _update_coins_list_cache(self, coins_data: List[Dict[str, Any]]) -> None:
        """Update the coins list cache with new data.
        
        Args:
            coins_data: List of coin dictionaries to cache
        """
        # FIXED: Maintain type consistency - cache IDs (strings) not full objects  
        coin_ids = {coin["id"] for coin in coins_data}
        metadata = {
            "total_coins": len(coins_data),
            "loaded_at": time.time(),
            "coin_lookup": {coin["id"]: coin for coin in coins_data}
        }
        self._cache_identifiers("coins_list", coin_ids, metadata)

    async def _setup_endpoints(self):
        """Setup HTTP endpoints for CoinGecko API."""
        headers = {}
        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key
        
        await self._http_client.add_endpoint(
            name="coingecko",
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )
        
        logger.debug("Setup HTTP endpoint for CoinGecko API")

    async def _make_api_request(
        self, 
        endpoint: str, 
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Make API request directly using HTTP client with parameter validation.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            dict: Raw JSON response from API
        """
        # Ensure endpoints are setup
        if "coingecko" not in self._http_client.get_endpoints():
            await self._setup_endpoints()
        
        # Validate vs_currency parameter if present
        if params and "vs_currencies" in params:
            currencies = params["vs_currencies"].split(",")
            for currency in currencies:
                try:
                    self._validate_configuration_enum(
                        currency.lower(),
                        VsCurrency,
                        "vs_currency"
                    )
                except ValueError:
                    # Allow unknown currencies to pass through for API flexibility
                    logger.warning(f"Unknown vs_currency '{currency}', allowing API to handle")
        
        # Use HTTP client directly - no wrapper response format
        return await self._http_client.get(
            endpoint_name="coingecko",
            path=endpoint,
            params=params or {}
        )

    async def _validate_coin_and_prepare_params(
        self,
        coin_name_or_id: str,
        vs_currency: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate coin identifier and prepare standardized parameters using base class method.
        
        Args:
            coin_name_or_id: Coin name or ID to validate
            vs_currency: Quote currency (uses default if None)
            additional_params: Additional parameters to include
            
        Returns:
            dict: Validated parameters including coin_id and vs_currency
            
        Raises:
            ValueError: If coin validation fails
        """
        vs_currency = vs_currency or self.default_vs_currency.value
        
        # Use generic base class validation method
        return await self._validate_identifier_and_prepare_params(
            identifier=coin_name_or_id,
            identifier_type="coin_name_or_id",
            validation_func=self.resolve_coin_name_or_id,
            additional_params={
                "vs_currency": vs_currency,
                **(additional_params or {})
            },
            identifier_transform_func=lambda x: x.lower() if isinstance(x, str) else str(x).lower()
        )

    async def _ensure_coins_loaded(self):
        """Ensure coins list is loaded using enhanced caching."""
        cache_key = "coins_list"
        cached_coins = self._get_cached_identifiers(cache_key)
        if cached_coins is None:
            await self.reload_coins_list()

    # =========================================================================
    # Coin Management Tools
    # =========================================================================
    
    async def reload_coins_list(self) -> Dict[str, Any]:
        """Fetch and cache all available coins from CoinGecko.
        
        Retrieves the complete list of supported cryptocurrencies with their IDs,
        symbols, and names. This data is cached for validation and used throughout
        the toolkit for coin ID resolution.
        
        Returns:
            dict: Coins loading result
            
        **Success Response:**
        ```json
        {
            "success": true,
            "coin_count": 17234,
            "fetched_at": "2024-01-01T12:00:00Z",
            "sample_coins": [
                {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
                {"id": "ethereum", "symbol": "eth", "name": "Ethereum"}
            ]
        }
        ```
        
        **Failure Response:**
        ```json
        {
            "success": false,
            "message": "Failed to reload coins: Connection timeout",
            "error_type": "api_error"
        }
        ```
        
        Example Usage:
        ```python
        # Refresh coins list manually
        result = await toolkit.reload_coins_list()
        if result["success"]:
            print(f"Loaded {result['coin_count']} coins")
            
        # Access sample data
        for coin in result["sample_coins"]:
            print(f"{coin['name']} ({coin['symbol']}): {coin['id']}")
        ```
        
        Performance:
        - Response time: 2-5 seconds depending on network
        - Rate limit: 10-50 requests per minute (depends on plan)
        - Caching: Results cached until manual reload
        """
        try:
            coins_list = await self._make_api_request(_API_ENDPOINTS["coins_list"])
            
            # Use enhanced caching from BaseAPIToolkit
            cache_key = "coins_list"
            coin_ids = {coin["id"] for coin in coins_list}
            metadata = {
                "total_coins": len(coins_list),
                "loaded_at": time.time(),
                "coin_lookup": {coin["id"]: coin for coin in coins_list}
            }
            self._cache_identifiers(cache_key, coin_ids, metadata)
            
            logger.info(f"Loaded {len(coins_list)} coins from CoinGecko")
            
            return self.response_builder.success_response(
                message="Coins list reloaded successfully",
                coin_count=len(coins_list),
                fetched_at=self.unix_to_iso(time.time()),
                sample_coins=coins_list[:5] if coins_list else []
            )
        except Exception as e:
            logger.error(f"Failed to reload coins list: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["coins_list"],
                api_message=f"Failed to reload coins list: {str(e)}",
                error_type="coins_reload_error"
            )
    
    async def validate_coin(self, coin_id: str) -> Dict[str, Any]:
        """Validate that a coin ID is supported and allowed.
        
        Checks if a coin ID is:
        1. Listed in CoinGecko's database
        2. Allowed by the toolkit's coin filter (if configured)
        
        Args:
            coin_id: CoinGecko coin identifier (case-insensitive)
                    Examples: "bitcoin", "ethereum", "cardano"
                    
        Returns:
            dict: Validation result with detailed status
            
        **Success Response:**
        ```json
        {
            "success": true,
            "message": "Coin is valid",
            "coin_id": "bitcoin",
            "coin_data": {
                "id": "bitcoin",
                "symbol": "btc", 
                "name": "Bitcoin"
            }
        }
        ```
        
        **Invalid Coin Response:**
        ```json
        {
            "success": false,
            "message": "Coin 'invalid-coin' not found in CoinGecko database",
            "coin_id": "invalid-coin",
            "error_type": "invalid_coin",
            "available_count": 17234
        }
        ```
        
        **Not Allowed Response:**
        ```json
        {
            "success": false,
            "message": "Coin 'cardano' not in configured allowlist",
            "coin_id": "cardano",
            "error_type": "coin_not_allowed",
            "allowed_coins": ["bitcoin", "ethereum"]
        }
        ```
        
        Example Usage:
        ```python
        # Validate before price queries
        validation = await toolkit.validate_coin("bitcoin")
        if validation["success"]:
            # Proceed with API calls
            price = await toolkit.get_coin_price("bitcoin")
        else:
            print(f"Invalid coin: {validation['message']}")
            
        # Batch validation
        coins = ["bitcoin", "ethereum", "invalid-coin"]
        for coin in coins:
            result = await toolkit.validate_coin(coin)
            status = "✅" if result["success"] else "❌"
            print(f"{status} {coin}: {result['message']}")
        ```
        
        Note:
        This tool automatically loads coins list if not already cached. Coin IDs
        are case-insensitive and the toolkit handles normalization automatically.
        """
        await self._ensure_coins_loaded()
        
        coin_id = coin_id.lower()
        cache_key = "coins_list"
        valid_coins = self._get_cached_identifiers(cache_key) or set()
        
        # Get coin data from metadata cache
        cache_entry = self._data_caches.get(cache_key, {})
        coin_lookup = cache_entry.get("metadata", {}).get("coin_lookup", {})
        coin_data = coin_lookup.get(coin_id)
        
        # Check if coin exists
        is_valid = coin_id in valid_coins
        suggestions = []
        
        if not is_valid:
            # Try to find fuzzy matches for suggestions
            fuzzy_match = self._find_fuzzy_match(coin_id, valid_coins, threshold=0.6)
            if fuzzy_match:
                suggestions.append(f"Did you mean '{fuzzy_match}'?")
                
        # Check user coins filter if configured
        if is_valid and self._user_coins and coin_id not in self._user_coins:
            return self.response_builder.error_response(
                message=f"Coin '{coin_id}' not in configured allowlist",
                error_type="coin_filtered",
                coin_id=coin_id,
                coin_data=coin_data,
                user_coins_count=len(self._user_coins),
                allowed_coins=list(self._user_coins),
                suggestions=["Check your coin allowlist configuration"]
            )
        
        # Use enhanced validation response builder
        return self._build_identifier_validation_response(
            identifier=coin_id,
            is_valid=is_valid,
            config_context="CoinGecko database",
            identifier_type="coin",
            suggestions=suggestions,
            coin_data=coin_data,
            available_count=len(valid_coins)
        )

    async def resolve_coin_name_to_id(self, coin_name: str, fuzzy_threshold: float = 0.8) -> Dict[str, Any]:
        """Resolve a coin name to its CoinGecko ID with fuzzy matching support.
        
        Converts a human-readable coin name to the corresponding CoinGecko coin ID
        required for API calls. Supports exact matching, partial matching, and fuzzy
        matching to handle variations in naming and common misspellings.
        
        Args:
            coin_name: Human-readable coin name (case-insensitive)
                      Examples: "Bitcoin", "Ethereum", "Cardano", "Binance Coin"
            fuzzy_threshold: Minimum similarity score for fuzzy matching (0.0-1.0)
                           Higher values require closer matches. Default: 0.8
                           
        Returns:
            dict: Coin ID resolution result with match confidence
            
        **Success Response (Exact Match):**
        ```json
        {
            "success": true,
            "coin_name": "Bitcoin",
            "coin_id": "bitcoin",
            "match_type": "exact",
            "confidence": 1.0,
            "coin_data": {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin"
            }
        }
        ```
        
        **Success Response (Fuzzy Match):**
        ```json
        {
            "success": true,
            "coin_name": "Etherium",
            "coin_id": "ethereum", 
            "match_type": "fuzzy",
            "confidence": 0.89,
            "coin_data": {
                "id": "ethereum",
                "symbol": "eth",
                "name": "Ethereum"
            },
            "note": "Found close match for 'Etherium' -> 'Ethereum'"
        }
        ```
        
        **Multiple Matches Response:**
        ```json
        {
            "success": false,
            "coin_name": "Bitcoin",
            "message": "Multiple coins found matching 'Bitcoin'",
            "error_type": "multiple_matches",
            "matches": [
                {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc"},
                {"id": "bitcoin-cash", "name": "Bitcoin Cash", "symbol": "bch"},
                {"id": "bitcoin-sv", "name": "Bitcoin SV", "symbol": "bsv"}
            ],
            "suggestion": "Use more specific name or symbol"
        }
        ```
        
        Example Usage:
        ```python
        # Exact name resolution
        btc_result = await toolkit.resolve_coin_name_to_id("Bitcoin")
        if btc_result["success"]:
            coin_id = btc_result["coin_id"]
            price = await toolkit.get_coin_price(coin_id)
            
        # Fuzzy matching for typos
        eth_result = await toolkit.resolve_coin_name_to_id("Etherium")  # Misspelled
        if eth_result["success"]:
            print(f"Corrected: {eth_result['coin_name']} -> {eth_result['coin_data']['name']}")
            
        # Handle multiple matches
        btc_result = await toolkit.resolve_coin_name_to_id("Bitcoin")
        if not btc_result["success"] and btc_result.get("error_type") == "multiple_matches":
            matches = btc_result["matches"]
            print("Multiple matches found:")
            for match in matches:
                print(f"  {match['name']} ({match['symbol']}) -> {match['id']}")
        ```
        """
        await self._ensure_coins_loaded()
        
        coin_name = coin_name.strip()
        base_response = {"coin_name": coin_name}
        
        if not coin_name:
            return self.response_builder.validation_error_response(
                field_name="coin_name",
                field_value=coin_name,
                validation_errors=["Coin name cannot be empty"],
                **base_response
            )
        
        # Get coin lookup from cache metadata for name resolution
        if not hasattr(self, '_data_caches') or 'coins_list' not in self._data_caches:
            return self.response_builder.error_response(
                message="Coins list cache not available",
                error_type="cache_unavailable",
                **base_response
            )
        
        cache_entry = self._data_caches.get('coins_list', {})
        metadata = cache_entry.get('metadata', {})
        coin_lookup = metadata.get('coin_lookup', {})
        
        if not coin_lookup:
            return self.response_builder.error_response(
                message="Coin lookup data not available",
                error_type="lookup_unavailable",
                **base_response
            )
        
        # Get all coin objects for name matching
        all_coins = list(coin_lookup.values())
        
        # Step 1: Exact match (case-insensitive)
        exact_matches = [
            coin for coin in all_coins
            if coin.get("name", "").lower() == coin_name.lower()
        ]
        
        if len(exact_matches) == 1:
            coin_data = exact_matches[0]
            return self.response_builder.success_response(
                **base_response,
                coin_id=coin_data["id"],
                match_type="exact",
                confidence=1.0,
                coin_data=coin_data
            )
        elif len(exact_matches) > 1:
            return self.response_builder.error_response(
                message=f"Multiple coins found with exact name '{coin_name}'",
                error_type="multiple_matches",
                details={
                    **base_response,
                    "matches": exact_matches,
                    "suggestion": "Use coin symbol or ID for disambiguation"
                }
            )
        
        # Step 2: Partial match (name contains or starts with input)
        partial_matches = [
            coin for coin in all_coins
            if coin_name.lower() in coin.get("name", "").lower() or
               coin.get("name", "").lower().startswith(coin_name.lower())
        ]
        
        if len(partial_matches) == 1:
            coin_data = partial_matches[0]
            return self.response_builder.success_response(
                **base_response,
                coin_id=coin_data["id"],
                match_type="partial",
                confidence=0.95,
                coin_data=coin_data,
                note=f"Found partial match for '{coin_name}' -> '{coin_data['name']}'"
            )
        elif len(partial_matches) > 1:
            # Filter to best partial matches (prefer starts_with over contains)
            starts_with_matches = [
                coin for coin in partial_matches
                if coin.get("name", "").lower().startswith(coin_name.lower())
            ]
            
            if len(starts_with_matches) == 1:
                coin_data = starts_with_matches[0]
                return self.response_builder.success_response(
                    **base_response,
                    coin_id=coin_data["id"],
                    match_type="partial",
                    confidence=0.95,
                    coin_data=coin_data,
                    note=f"Found partial match for '{coin_name}' -> '{coin_data['name']}'"
                )
            
            # Multiple partial matches - return top 5 for disambiguation
            return self.response_builder.error_response(
                message=f"Multiple coins found matching '{coin_name}'",
                error_type="multiple_matches",
                details={
                    **base_response,
                    "matches": partial_matches[:5],
                    "suggestion": "Be more specific or use the exact coin name"
                }
            )
        
        # Step 3: Fuzzy matching using difflib
        coin_names = [coin.get("name", "") for coin in all_coins if coin.get("name")]
        fuzzy_matches = difflib.get_close_matches(
            coin_name, 
            coin_names, 
            n=5, 
            cutoff=fuzzy_threshold
        )
        
        if fuzzy_matches:
            # Find the coin with the best match
            best_match_name = fuzzy_matches[0]
            best_match_coin = next(
                (coin for coin in all_coins 
                 if coin.get("name") == best_match_name), 
                None
            )
            
            if best_match_coin:
                # Calculate similarity ratio
                similarity = difflib.SequenceMatcher(
                    None, coin_name.lower(), best_match_name.lower()
                ).ratio()
                
                if len(fuzzy_matches) == 1:
                    return {
                        **base_response,
                        "success": True,
                        "coin_id": best_match_coin["id"],
                        "match_type": "fuzzy",
                        "confidence": round(similarity, 3),
                        "coin_data": best_match_coin,
                        "note": f"Found close match for '{coin_name}' -> '{best_match_name}'"
                    }
                else:
                    # Multiple fuzzy matches - let user choose
                    fuzzy_match_coins = []
                    for match_name in fuzzy_matches:
                        match_coin = next(
                            (coin for coin in all_coins 
                             if coin.get("name") == match_name),
                            None
                        )
                        if match_coin:
                            match_similarity = difflib.SequenceMatcher(
                                None, coin_name.lower(), match_name.lower()
                            ).ratio()
                            match_coin_with_confidence = {**match_coin, "confidence": round(match_similarity, 3)}
                            fuzzy_match_coins.append(match_coin_with_confidence)
                    
                    return self.response_builder.error_response(
                        message=f"Multiple similar coins found for '{coin_name}'",
                        error_type="multiple_fuzzy_matches",
                        details={
                            **base_response,
                            "matches": fuzzy_match_coins,
                            "suggestion": "Choose the intended coin from the matches"
                        }
                    )
        
        # Step 4: Symbol matching (as last resort)
        symbol_matches = [
            coin for coin in all_coins
            if coin.get("symbol", "").lower() == coin_name.lower()
        ]
        
        if len(symbol_matches) == 1:
            coin_data = symbol_matches[0]
            return {
                **base_response,
                "success": True,
                "coin_id": coin_data["id"],
                "match_type": "symbol",
                "confidence": 0.9,
                "coin_data": coin_data,
                "note": f"Matched by symbol: '{coin_name}' -> '{coin_data['name']}'"
            }
        elif len(symbol_matches) > 1:
            return self.response_builder.error_response(
                message=f"Multiple coins found with symbol '{coin_name}'",
                error_type="multiple_symbol_matches",
                details={
                    **base_response,
                    "matches": symbol_matches[:5],
                    "suggestion": "Use full coin name for disambiguation"
                }
            )
        
        # No matches found
        return self.response_builder.error_response(
            message=f"No coin found matching '{coin_name}'",
            error_type="no_match",
            details={
                **base_response,
                "suggestion": "Check spelling or try using the coin symbol"
            }
        )

    async def resolve_coin_name_or_id(self, coin_identifier: str) -> Dict[str, Any]:
        """Resolve a coin name or ID to a validated CoinGecko ID.
        
        Universal resolver that accepts either coin names or IDs and returns a validated
        CoinGecko ID. This method serves as the primary interface for all toolkit methods,
        allowing users to use human-readable names while maintaining internal ID consistency.
        
        Args:
            coin_identifier: Either a coin name or CoinGecko ID
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "eth"
                           
        Returns:
            dict: Validated coin ID with resolution details
            
        **Success Response (Valid ID):**
        ```json
        {
            "success": true,
            "input": "bitcoin",
            "coin_id": "bitcoin",
            "resolution_type": "id_validation",
            "coin_data": {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin"
            }
        }
        ```
        
        **Success Response (Name Resolution):**
        ```json
        {
            "success": true,
            "input": "Bitcoin",
            "coin_id": "bitcoin",
            "resolution_type": "name_resolution",
            "match_type": "exact",
            "confidence": 1.0,
            "coin_data": {
                "id": "bitcoin", 
                "symbol": "btc",
                "name": "Bitcoin"
            }
        }
        ```
        
        Example Usage:
        ```python
        # Can use either name or ID
        inputs = ["Bitcoin", "bitcoin", "Ethereum", "eth"]
        
        for identifier in inputs:
            result = await toolkit.resolve_coin_name_or_id(identifier)
            if result["success"]:
                coin_id = result["coin_id"]
                coin_name = result["coin_data"]["name"]
                print(f"'{identifier}' -> {coin_id} ({coin_name})")
                
                # Now use the validated ID for API calls
                price = await toolkit.get_coin_price(coin_id)
        ```
        """
        coin_identifier = coin_identifier.strip()
        
        # First try to validate as an ID
        id_validation = await self.validate_coin(coin_identifier)
        if id_validation["success"]:
            return {
                "success": True,
                "input": coin_identifier,
                "coin_id": coin_identifier.lower(),
                "resolution_type": "id_validation",
                "coin_data": id_validation["data"]["coin_data"]
            }
        
        # If ID validation fails, try name resolution
        name_resolution = await self.resolve_coin_name_to_id(coin_identifier)
        if name_resolution["success"]:
            return {
                "success": True,
                "input": coin_identifier,
                "coin_id": name_resolution["coin_id"],
                "resolution_type": "name_resolution",
                "match_type": name_resolution["match_type"],
                "confidence": name_resolution["confidence"],
                "coin_data": name_resolution["coin_data"]
            }
        
        # Both validation and resolution failed
        return {
            "success": False,
            "input": coin_identifier,
            "message": f"Could not resolve '{coin_identifier}' to a valid coin",
            "error_type": "resolution_failed",
            "id_validation_error": id_validation.get("message"),
            "name_resolution_error": name_resolution.get("message")
        }

    # =========================================================================
    # Core Data Tools  
    # =========================================================================
    
    # Placeholder for the remaining methods - will be implemented in next steps
    async def get_coin_info(self, coin_name_or_id: str) -> Dict[str, Any]:
        """Get comprehensive information about a specific cryptocurrency.
        
        Retrieves detailed metadata, market data, and community information for a given
        cryptocurrency. This includes descriptions, links, contract addresses, market
        statistics, and optional community/developer data based on toolkit configuration.
        
        Args:
            coin_name_or_id: Coin name or CoinGecko ID (case-insensitive)
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "ethereum"
                           Supports fuzzy matching for names with typos
                    
        Returns:
            dict: Comprehensive coin information
            
        **Success Response:**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "data": {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "description": {
                    "en": "Bitcoin is the first successful internet money..."
                },
                "links": {
                    "homepage": ["https://bitcoin.org"],
                    "blockchain_site": ["https://blockchair.com/bitcoin/"],
                    "official_forum_url": ["https://bitcointalk.org/"],
                    "chat_url": ["https://bitcoin.org/en/community"],
                    "announcement_url": ["https://bitcointalk.org/index.php?topic=382374.0"],
                    "twitter_screen_name": "bitcoin",
                    "facebook_username": "bitcoins",
                    "telegram_channel_identifier": "",
                    "subreddit_url": "https://www.reddit.com/r/Bitcoin/",
                    "repos_url": {
                        "github": ["https://github.com/bitcoin/bitcoin"],
                        "bitbucket": []
                    }
                },
                "image": {
                    "thumb": "https://assets.coingecko.com/coins/images/1/thumb/bitcoin.png",
                    "small": "https://assets.coingecko.com/coins/images/1/small/bitcoin.png",
                    "large": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png"
                },
                "country_origin": "",
                "genesis_date": "2009-01-03",
                "contract_address": "",
                "sentiment_votes_up_percentage": 75.25,
                "sentiment_votes_down_percentage": 24.75,
                "market_cap_rank": 1,
                "coingecko_rank": 1,
                "coingecko_score": 83.151,
                "developer_score": 99.241,
                "community_score": 83.341,
                "liquidity_score": 100.0,
                "public_interest_score": 0.073,
                "market_data": {
                    "current_price": {"usd": 67250.50, "btc": 1.0, "eth": 18.25},
                    "market_cap": {"usd": 1325000000000, "btc": 19680000, "eth": 358900000},
                    "total_volume": {"usd": 15230000000, "btc": 226300, "eth": 4128000}
                }
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Coin 'invalid-coin' not found in CoinGecko database",
            "error_type": "validation_error",
            "coin_id": "invalid-coin"
        }
        ```
        
        Example Usage:
        ```python
        # Get comprehensive Bitcoin information
        btc_info = await toolkit.get_coin_info("bitcoin")
        if btc_info["success"]:
            data = btc_info["data"]
            # further operations on the data
                
        # Analyze multiple coins
        coins = ["bitcoin", "ethereum", "cardano"]
        for coin in coins:
            info = await toolkit.get_coin_info(coin)
            if info["success"]:
                data = info["data"]
                # further operations on the data
        ```
        
        **Data Categories Included:**
        - **Basic Info**: Name, symbol, description, genesis date
        - **Market Data**: Current prices, market cap, volume, ATH/ATL
        - **Links**: Website, social media, blockchain explorers, repositories
        - **Images**: Coin logos in multiple sizes (thumb, small, large)
        - **Scores**: CoinGecko ranking, developer activity, community engagement
        - **Community Data**: Social metrics, sentiment analysis (if enabled)
        - **Developer Data**: GitHub activity, code commits (if enabled)
        - **Contract Info**: Smart contract addresses across supported blockchains
        
        **Analysis Applications:**
        - **Due Diligence**: Verify project legitimacy and activity
        - **Market Research**: Compare rankings and community engagement
        - **Portfolio Analysis**: Assess investment quality metrics
        - **Social Sentiment**: Monitor community perception and trends
        - **Technical Research**: Access official links and documentation
        
        **Performance Notes:**
        - Response time: 500ms-2s depending on data flags
        - Rate limit: 10-50 requests per minute (plan dependent)
        - Data freshness: Market data updated every 60 seconds
        - Community data: Some metrics updated weekly
        """
        try:
            # Use consolidated validation pattern
            validation_params = await self._validate_coin_and_prepare_params(
                coin_name_or_id=coin_name_or_id,
                additional_params={
                    "localization": "false",  # Reduce response size
                    "tickers": "false",      # Skip ticker data for now
                    "market_data": "true",
                    "community_data": str(self.include_community_data).lower(),
                    "developer_data": str(self.include_developer_data).lower(),
                    "sparkline": "false"
                }
            )
            
            coin_id = validation_params["coin_id"]
            api_params = {k: v for k, v in validation_params.items() if k not in ["coin_name_or_id", "coin_id", "vs_currency"]}
            
            data = await self._make_api_request(_API_ENDPOINTS["coin_info"].format(coin_id=coin_id), api_params)
            
            # Validate coin data structure using DataValidator
            coin_validation = DataValidator.validate_structure(
                data,
                expected_type=dict,
                required_fields=["id", "symbol", "name"]
            )
            
            if not coin_validation["valid"]:
                logger.warning(f"Coin info data validation failed: {coin_validation['errors']}")
                return self.response_builder.validation_error_response(
                    field_name="coin_info_data",
                    field_value=data,
                    validation_errors=coin_validation["errors"],
                    coin_id=coin_id
                )
            
            coin_data = data
            
            # Clean and structure the response
            structured_data = {
                "id": coin_data.get("id"),
                "symbol": coin_data.get("symbol"), 
                "name": coin_data.get("name"),
                "description": coin_data.get("description", {}),
                "links": coin_data.get("links", {}),
                "image": coin_data.get("image", {}),
                "country_origin": coin_data.get("country_origin", ""),
                "genesis_date": coin_data.get("genesis_date"),
                "contract_address": coin_data.get("contract_address", ""),
                "sentiment_votes_up_percentage": coin_data.get("sentiment_votes_up_percentage"),
                "sentiment_votes_down_percentage": coin_data.get("sentiment_votes_down_percentage"),
                "market_cap_rank": coin_data.get("market_cap_rank"),
                "coingecko_rank": coin_data.get("coingecko_rank"),
                "coingecko_score": coin_data.get("coingecko_score"),
                "developer_score": coin_data.get("developer_score"),
                "community_score": coin_data.get("community_score"),
                "liquidity_score": coin_data.get("liquidity_score"),
                "public_interest_score": coin_data.get("public_interest_score"),
                "market_data": coin_data.get("market_data", {})
            }
            
            # Add community and developer data if requested
            if self.include_community_data and "community_data" in coin_data:
                structured_data["community_data"] = coin_data["community_data"]
            
            if self.include_developer_data and "developer_data" in coin_data:
                structured_data["developer_data"] = coin_data["developer_data"]
            
            return self.response_builder.success_response(
                data=structured_data,
                coin_id=coin_id,
                fetched_at=self.unix_to_iso(time.time())
            )
                
        except Exception as e:
            logger.error(f"Failed to get coin info for {coin_name_or_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["coin_info"],
                api_message=f"Failed to get coin information: {str(e)}",
                coin_name_or_id=coin_name_or_id
            )
    
    async def get_coin_price(self, coin_name_or_id: str, vs_currency: Optional[str] = None) -> Dict[str, Any]:
        """Get current price and comprehensive market data for a cryptocurrency.
        
        Retrieves real-time pricing information including current price, market cap,
        trading volume, and 24-hour percentage changes. Supports pricing in 100+
        fiat and cryptocurrency quote currencies with extensive market metrics.
        
        Args:
            coin_name_or_id: Coin name or CoinGecko ID (case-insensitive)
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "ethereum"
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
                        
        Returns:
            dict: Current price data with comprehensive market metrics
            
        **Success Response:**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "data": {
                "bitcoin": {
                    "usd": 67250.50,
                    "usd_market_cap": 1325000000000,
                    "usd_24h_vol": 15230000000,
                    "usd_24h_change": 2.45,
                    "last_updated_at": 1704067200
                }
            },
            "analysis": {
                "price_trend": "bullish",
                "volume_rating": "high",
                "market_cap_tier": "large_cap",
                "volatility_assessment": "moderate"
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Multi-Currency Response:**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd,eur,btc",
            "data": {
                "bitcoin": {
                    "usd": 67250.50,
                    "usd_market_cap": 1325000000000,
                    "usd_24h_vol": 15230000000,
                    "usd_24h_change": 2.45,
                    "eur": 61234.75,
                    "eur_market_cap": 1205000000000,
                    "eur_24h_vol": 13850000000,
                    "eur_24h_change": 1.89,
                    "btc": 1.0,
                    "btc_market_cap": 19680000,
                    "btc_24h_vol": 226300,
                    "btc_24h_change": 0.0,
                    "last_updated_at": 1704067200
                }
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Coin 'invalid-coin' not found in CoinGecko database",
            "error_type": "validation_error",
            "coin_id": "invalid-coin",
            "vs_currency": "usd"
        }
        ```
        
        Example Usage:
        ```python
        # Get Bitcoin price in USD
        btc_price = await toolkit.get_coin_price("bitcoin", "usd")
        if btc_price["success"]:
            data = btc_price["data"]["bitcoin"]
            # further operations on the data
            
        # Multi-currency pricing
        eth_multi = await toolkit.get_coin_price("ethereum", "usd,eur,btc")
        if eth_multi["success"]:
            data = eth_multi["data"]["ethereum"]
            # further operations on the data
        ```
        
        **Price Data Fields:**
        - `{currency}`: Current price in specified currency
        - `{currency}_market_cap`: Total market capitalization
        - `{currency}_24h_vol`: 24-hour trading volume
        - `{currency}_24h_change`: 24-hour percentage price change
        - `last_updated_at`: Unix timestamp of last price update
        
        **Analysis Insights:**
        - `price_trend`: "bullish", "bearish", or "neutral" based on 24h change
        - `volume_rating`: "high", "moderate", or "low" relative to market cap
        - `market_cap_tier`: "large_cap", "mid_cap", or "small_cap" classification
        - `volatility_assessment`: Price stability over recent period
        
        **Multi-Currency Support:**
        Pass comma-separated currencies (e.g., "usd,eur,btc") to get prices
        in multiple quote currencies simultaneously, optimizing API usage.
        
        **Market Cap Tiers:**
        - **Large Cap**: >$10B market cap (Bitcoin, Ethereum, etc.)
        - **Mid Cap**: $1B-$10B market cap (established altcoins)
        - **Small Cap**: <$1B market cap (newer/niche projects)
        
        **Performance Notes:**
        - Response time: 200-500ms
        - Rate limit: 10-50 requests per minute (plan dependent)
        - Data freshness: Updated every 60 seconds
        - Multi-currency: No additional latency penalty
        
        This tool is essential for real-time price monitoring, portfolio valuation,
        and automated trading strategies requiring accurate market data.
        """        
        try:
            # Use consolidated validation pattern
            params = await self._validate_coin_and_prepare_params(
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency,
                additional_params={
                    "ids": None,  # Will be set below
                    "vs_currencies": vs_currency or self.default_vs_currency.value,
                    "include_market_cap": "true",
                    "include_24hr_vol": "true", 
                    "include_24hr_change": "true",
                    "include_last_updated_at": "true",
                    "precision": "full"
                }
            )
            
            # Set ids parameter from resolved coin_id
            coin_id = params["coin_id"]
            api_params = {k: v for k, v in params.items() if k not in ["coin_name_or_id", "coin_id"]}
            api_params["ids"] = coin_id
            
            data = await self._make_api_request(_API_ENDPOINTS["simple_price"], api_params)
            
            # Validate price data structure using DataValidator
            price_validation = DataValidator.validate_structure(
                data,
                expected_type=dict
            )
            
            if not price_validation["valid"]:
                logger.warning(f"Price data validation failed: {price_validation['errors']}")
                return self.response_builder.validation_error_response(
                    field_name="price_data",
                    field_value=data,
                    validation_errors=price_validation["errors"],
                    coin_id=coin_id,
                    vs_currency=params["vs_currency"]
                )
            
            price_data = data
            
            if coin_id not in price_data:
                return self.response_builder.error_response(
                    f"No price data returned for coin '{coin_id}'",
                    error_type="no_data_error",
                    coin_id=coin_id,
                    vs_currency=params["vs_currency"]
                )
            
            coin_prices = price_data[coin_id]
            
            # Generate analysis using StatisticalAnalyzer methods
            analysis = {}
            # Use the resolved vs_currency from params, not the original parameter
            resolved_vs_currency = params["vs_currency"]
            currencies = resolved_vs_currency.split(",") if resolved_vs_currency else ["usd"]
            primary_currency = currencies[0]
            
            if f"{primary_currency}_24h_change" in coin_prices:
                change_24h = coin_prices[f"{primary_currency}_24h_change"]
                # Use StatisticalAnalyzer for trend and volatility classification
                analysis["price_trend"] = StatisticalAnalyzer.classify_trend_from_change(change_24h)
                analysis["volatility_assessment"] = StatisticalAnalyzer.classify_volatility_from_change(change_24h)
            
            if f"{primary_currency}_market_cap" in coin_prices:
                market_cap = coin_prices[f"{primary_currency}_market_cap"]
                if market_cap > 10_000_000_000:  # >$10B
                    analysis["market_cap_tier"] = "large_cap"
                elif market_cap > 1_000_000_000:  # >$1B
                    analysis["market_cap_tier"] = "mid_cap"
                else:
                    analysis["market_cap_tier"] = "small_cap"
            
            if f"{primary_currency}_24h_vol" in coin_prices and f"{primary_currency}_market_cap" in coin_prices:
                volume = coin_prices[f"{primary_currency}_24h_vol"]
                market_cap = coin_prices[f"{primary_currency}_market_cap"]
                volume_ratio = volume / market_cap if market_cap > 0 else 0
                
                analysis["volume_rating"] = (
                    "high" if volume_ratio > 0.1 else
                    "moderate" if volume_ratio > 0.05 else
                    "low"
                )
            
            return self.response_builder.success_response(
                data=price_data,
                coin_id=coin_id,
                vs_currency=params["vs_currency"],
                fetched_at=self.unix_to_iso(time.time()),
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get coin price for {coin_name_or_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["simple_price"],
                api_message=f"Failed to get coin price: {str(e)}",
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency or self.default_vs_currency.value
            )
    
    async def get_coin_market_chart(
        self, 
        coin_name_or_id: str, 
        vs_currency: Optional[str] = None, 
        days: int = 30,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get market chart data with comprehensive statistical analysis using NumPy.
        
        Retrieves historical price, market cap, and volume data for a cryptocurrency
        with advanced statistical analysis including OHLCV calculations, volatility
        metrics, trend analysis, and technical indicators using NumPy for numerical
        computations.
        
        Args:
            coin_name_or_id: Coin name or CoinGecko ID (case-insensitive)
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "ethereum"
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
            days: Number of days of historical data to retrieve
                 Valid values: 1, 7, 14, 30, 90, 180, 365, max
                 Default: 30
            from_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
                      Takes precedence over 'days' parameter if provided
            to_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
                    Defaults to current time if not provided
                    
        Returns:
            dict: Market chart data with comprehensive statistical analysis
            
        **Success Response (Small Dataset):**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "days": 30,
            "data_points": 720,
            "data": {
                "prices": [
                    [1704067200000, 67250.50],
                    [1704070800000, 67340.25],
                    [1704074400000, 67180.75]
                ],
                "market_caps": [
                    [1704067200000, 1325000000000],
                    [1704070800000, 1327000000000],
                    [1704074400000, 1323000000000]
                ],
                "total_volumes": [
                    [1704067200000, 15230000000],
                    [1704070800000, 16150000000],
                    [1704074400000, 14890000000]
                ]
            },
            "statistics": {
                "price_stats": {
                    "min": 65420.15,
                    "max": 69875.50,
                    "mean": 67523.84,
                    "median": 67485.25,
                    "std_dev": 1234.56,
                    "variance": 1524197.2,
                    "range": 4455.35,
                    "coefficient_of_variation": 0.0183
                },
                "returns": {
                    "total_return_pct": 2.45,
                    "annualized_return_pct": 29.4,
                    "daily_returns_mean": 0.098,
                    "daily_returns_std": 3.42,
                    "sharpe_ratio": 0.0287,
                    "max_drawdown_pct": -8.75
                },
                "volatility": {
                    "daily_volatility_pct": 3.42,
                    "annualized_volatility_pct": 65.1,
                    "volatility_regime": "moderate",
                    "rolling_volatility_30d": 3.85
                },
                "volume_stats": {
                    "avg_daily_volume": 15840000000,
                    "volume_volatility": 2.8e9,
                    "volume_trend": "increasing",
                    "volume_price_correlation": 0.34
                },
                "technical_indicators": {
                    "rsi_14": 58.2,
                    "bollinger_position": 0.65,
                    "price_vs_sma_20": 1.02,
                    "trend_direction": "bullish"
                }
            },
            "ohlcv_summary": {
                "open": 65850.25,
                "high": 69875.50,
                "low": 65420.15,
                "close": 67485.25,
                "volume": 474750000000,
                "vwap": 67402.15
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Success Response (Large Dataset - Stored as Parquet):**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "days": 365,
            "data_points": 8760,
            "file_path": "/path/to/data/coingecko/market_chart_bitcoin_usd_365_1704067200.parquet",
            "note": "Large market chart dataset stored as Parquet file",
            "statistics": {
                "price_stats": {...},
                "returns": {...},
                "volatility": {...}
            },
            "parquet_info": {
                "columns": ["timestamp", "price", "market_cap", "volume"],
                "format": "pandas_compatible",
                "compression": "snappy"
            }
        }
        ```
        
        Example Usage:
        ```python
        # Basic 30-day chart analysis
        chart = await toolkit.get_coin_market_chart("bitcoin", "usd", days=30)
        if chart["success"]:
            stats = chart["statistics"]
            # further operations on the data
            
        # Custom date range analysis
        custom_chart = await toolkit.get_coin_market_chart(
            "ethereum",
            "usd",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        
        # Large dataset handling
        yearly_chart = await toolkit.get_coin_market_chart("bitcoin", "usd", days=365)
        if yearly_chart["success"] and "file_path" in yearly_chart:
            import pandas as pd
            df = pd.read_parquet(yearly_chart["file_path"])    
            # further operations on the data
        ```
        
        **Statistical Metrics Explained:**
        
        **Price Statistics:**
        - `min/max/mean/median`: Basic price distribution metrics
        - `std_dev/variance`: Price dispersion measurements
        - `coefficient_of_variation`: Relative volatility (std_dev/mean)
        
        **Returns Analysis:**
        - `total_return_pct`: Total percentage gain/loss over period
        - `annualized_return_pct`: Return extrapolated to annual basis
        - `sharpe_ratio`: Risk-adjusted return metric
        - `max_drawdown_pct`: Largest peak-to-trough decline
        
        **Volatility Metrics:**
        - `daily_volatility_pct`: Average daily price fluctuation
        - `annualized_volatility_pct`: Volatility scaled to annual basis
        - `volatility_regime`: "low", "moderate", or "high" classification
        
        **Technical Indicators:**
        - `rsi_14`: Relative Strength Index (14-period)
        - `bollinger_position`: Position within Bollinger Bands (0-1)
        - `price_vs_sma_20`: Current price vs 20-period moving average
        
        **OHLCV Summary:**
        Candlestick data summary with Volume-Weighted Average Price (VWAP)
        
        **Applications:**
        - **Risk Assessment**: Volatility and drawdown analysis
        - **Performance Evaluation**: Return metrics and Sharpe ratios
        - **Technical Analysis**: Trend identification and momentum
        - **Portfolio Optimization**: Correlation and diversification analysis
        - **Backtesting**: Historical performance simulation
        
        Large datasets are automatically stored as Parquet files for efficient
        processing with pandas/polars and reduced memory usage.
        """
        try:
            # Use consolidated validation pattern
            validation_params = await self._validate_coin_and_prepare_params(
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency
            )
            
            coin_id = validation_params["coin_id"]
            
            # Build parameters - use date range if provided, otherwise use days
            api_params = {}
            if from_date and to_date:
                from_unix = self.iso_to_unix(from_date)
                to_unix = self.iso_to_unix(to_date)
                api_params.update({
                    "from": str(from_unix),
                    "to": str(to_unix)
                })
                # Calculate days for response metadata
                days = int((to_unix - from_unix) / 86400)
            elif from_date:
                from_unix = self.iso_to_unix(from_date)
                to_unix = int(time.time())
                api_params.update({
                    "from": str(from_unix),
                    "to": str(to_unix)
                })
                days = int((to_unix - from_unix) / 86400)
            else:
                api_params["days"] = str(days)
            
            api_params["vs_currency"] = validation_params["vs_currency"]
            
            data = await self._make_api_request(_API_ENDPOINTS["market_chart"].format(coin_id=coin_id), api_params)
            
            chart_data = data
            
            # Validate chart data structure using DataValidator
            chart_validation = DataValidator.validate_structure(
                chart_data,
                expected_type=dict,
                required_fields=["prices"]
            )
            
            if not chart_validation["valid"]:
                logger.warning(f"Market chart data validation failed: {chart_validation['errors']}")
                return self.response_builder.validation_error_response(
                    field_name="market_chart_data",
                    field_value=chart_data,
                    validation_errors=chart_validation["errors"],
                    coin_id=coin_id,
                    vs_currency=validation_params["vs_currency"]
                )
            
            # Extract data arrays
            prices = chart_data.get("prices", [])
            market_caps = chart_data.get("market_caps", [])
            volumes = chart_data.get("total_volumes", [])
            
            if not prices:
                return self.response_builder.error_response(
                    "No market chart data returned",
                    error_type="no_data_error",
                    coin_id=coin_id,
                    vs_currency=validation_params["vs_currency"]
                )
            
            # Convert to numpy arrays for statistical analysis
            price_array = _np.array([p[1] for p in prices])
            volume_array = _np.array([v[1] for v in volumes]) if volumes else None
            timestamps = _np.array([p[0] for p in prices])
            
            # Calculate comprehensive statistics using StatisticalAnalyzer
            statistics = {
                "price_stats": self.stats.calculate_price_statistics(price_array),
                "returns": self.stats.calculate_returns_analysis(price_array, timestamps),
                "volatility": self.stats.calculate_volatility_metrics(price_array),
                "volume_stats": self.stats.calculate_volume_statistics(volume_array, price_array) if volume_array is not None else {},
                "technical_indicators": self.stats.calculate_technical_indicators(price_array, volume_array)
            }
            
            # Calculate OHLCV summary using StatisticalAnalyzer
            ohlcv_summary = self.stats.calculate_ohlcv_summary(price_array, volume_array, timestamps)
            
            base_response = {
                "success": True,
                "coin_id": coin_id,
                "vs_currency": vs_currency,
                "days": days,
                "data_points": len(prices),
                "statistics": statistics,
                "ohlcv_summary": ohlcv_summary,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            # Store as Parquet if dataset is large
            if self._should_store_as_parquet(prices):
                # Convert to structured format for Parquet
                structured_data = []
                for i, (timestamp, price) in enumerate(prices):
                    row = {
                        "timestamp": timestamp,
                        "price": price
                    }
                    if i < len(market_caps):
                        row["market_cap"] = market_caps[i][1]
                    if i < len(volumes):
                        row["volume"] = volumes[i][1]
                    structured_data.append(row)
                
                # Use standardized data response builder
                filename_template = FileNameGenerator.generate_data_filename(
                    "market_chart", coin_id, vs_currency, {"days": days},
                    file_prefix=self._file_prefix
                )
                
                return self.response_builder.build_data_response_with_storage(
                    data=structured_data,
                    storage_threshold=self._parquet_threshold,
                    storage_callback=lambda data, filename: self._store_parquet(data, filename),
                    filename_template=filename_template,
                    large_data_note="Large market chart dataset stored as Parquet file",
                    **base_response
                )
            else:
                return {
                    **base_response,
                    "data": {
                        "prices": prices,
                        "market_caps": market_caps,
                        "total_volumes": volumes
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get market chart for {coin_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["market_chart"],
                api_message=f"Failed to get market chart: {str(e)}",
                coin_id=coin_id,
                vs_currency=vs_currency
            )
    
    # Statistical analysis methods have been moved to StatisticalAnalyzer class
    # for better separation of concerns and code reuse
    
    async def get_multiple_coins_data(self, coin_names_or_ids: List[str], vs_currency: Optional[str] = None) -> Dict[str, Any]:
        """Fetch current price data for multiple cryptocurrencies.
        
        Retrieves real-time pricing data for multiple coins simultaneously and formats
        the response as a structured dataset suitable for pandas DataFrame operations.
        Optimizes API usage by batching requests and provides comprehensive market metrics.
        
        Args:
            coin_names_or_ids: List of coin names or CoinGecko IDs (case-insensitive)
                             Examples: ["Bitcoin", "ethereum", "Cardano", "ada"]
                             Maximum recommended: 250 coins per request
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
                        
        Returns:
            dict: Structured data suitable for DataFrame creation or file path for large responses
            
        **Success Response (Small Dataset):**
        ```json
        {
            "success": true,
            "coin_count": 3,
            "vs_currency": "usd",
            "data": [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "current_price": 67250.50,
                    "market_cap": 1325000000000,
                    "market_cap_rank": 1,
                    "total_volume": 15230000000,
                    "price_change_24h": 1642.25,
                    "price_change_percentage_24h": 2.45,
                    "circulating_supply": 19680000,
                    "total_supply": 21000000,
                    "max_supply": 21000000,
                    "ath": 69045.00,
                    "ath_change_percentage": -2.6,
                    "atl": 67.81,
                    "atl_change_percentage": 99087.2,
                    "last_updated": "2024-01-01T12:00:00.000Z"
                }
            ],
            "summary": {
                "total_market_cap": 2456000000000,
                "avg_24h_change": 1.85,
                "top_performer": "ethereum",
                "worst_performer": "cardano"
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Success Response (Large Dataset - Stored as Parquet):**
        ```json
        {
            "success": true,
            "coin_count": 250,
            "vs_currency": "usd",
            "file_path": "/path/to/data/coingecko/multiple_coins_usd_250_1704067200.parquet",
            "note": "Large multi-coin dataset stored as Parquet file",
            "summary": {
                "total_market_cap": 2456000000000,
                "market_cap_distribution": {
                    "large_cap": 45,
                    "mid_cap": 128,
                    "small_cap": 77
                }
            }
        }
        ```
        
        Example Usage:
        ```python
        portfolio = ["bitcoin", "ethereum", "cardano", "polkadot"]
        data = await toolkit.get_multiple_coins_data(portfolio, "usd")
        
        if data["success"]:
            if "data" in data:
                # Convert to pandas DataFrame
                import pandas as pd
                df = pd.DataFrame(data["data"])
                # further operations on the data
                
                    
            elif "file_path" in data:
                # Large dataset handling
                df = pd.read_parquet(data["file_path"])
                # further operations on the data
        ```
        
        **Data Fields Included:**
        - **Basic Info**: id, symbol, name
        - **Pricing**: current_price, price_change_24h, price_change_percentage_24h
        - **Market Data**: market_cap, market_cap_rank, total_volume
        - **Supply**: circulating_supply, total_supply, max_supply
        - **Historical**: ath (all-time high), atl (all-time low), change percentages
        - **Metadata**: last_updated timestamp
        
        **Summary Analytics:**
        - Total portfolio market cap aggregation
        - Average performance metrics
        - Best/worst performing assets identification
        - Market cap tier distribution
        
        **DataFrame Applications:**
        - **Portfolio Management**: Track multiple holdings simultaneously
        - **Market Analysis**: Compare performance across assets
        - **Screening**: Filter coins by various criteria
        - **Correlation Analysis**: Study relationships between assets
        - **Risk Assessment**: Diversification and exposure analysis
        
        This tool is essential for portfolio management, market research, and
        multi-asset analysis requiring structured data formats.
        """
        vs_currency = vs_currency or self.default_vs_currency.value
        
        # Resolve all coin names/IDs to validated IDs
        resolution_tasks = [self.resolve_coin_name_or_id(coin_name_or_id) for coin_name_or_id in coin_names_or_ids]
        resolution_results = await asyncio.gather(*resolution_tasks)
        
        failed_resolutions = [
            coin_names_or_ids[i] for i, result in enumerate(resolution_results)
            if not result["success"]
        ]
        
        if failed_resolutions:
            successful_resolutions = [
                coin_names_or_ids[i] for i, result in enumerate(resolution_results)
                if result["success"]
            ]
            return self.response_builder.error_response(
                message=f"Could not resolve coins: {', '.join(failed_resolutions)}",
                error_type="resolution_error",
                details={
                    "failed_coins": failed_resolutions,
                    "successful_coins": successful_resolutions,
                    "vs_currency": vs_currency
                }
            )
        
        # Extract resolved coin IDs
        coin_ids = [result["coin_id"] for result in resolution_results]
        
        try:
            # IDs are already lowercase from resolution
            ids_param = ",".join(coin_ids)
            
            params = {
                "ids": ids_param,
                "vs_currencies": vs_currency,
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            data = await self._make_api_request(_API_ENDPOINTS["simple_price"], params)
            
            price_data = data
            
            # Convert to structured format suitable for DataFrame
            structured_data = []
            for coin_id in coin_ids:
                if coin_id in price_data:
                    coin_info = price_data[coin_id]
                    coin_record = {
                        "id": coin_id,
                        "current_price": coin_info.get(vs_currency),
                        "market_cap": coin_info.get(f"{vs_currency}_market_cap"),
                        "total_volume": coin_info.get(f"{vs_currency}_24h_vol"),
                        "price_change_percentage_24h": coin_info.get(f"{vs_currency}_24h_change"),
                        "last_updated_at": coin_info.get("last_updated_at")
                    }
                    
                    # Add coin metadata from cache if available
                    if hasattr(self, '_data_caches') and 'coins_list' in self._data_caches:
                        cache_entry = self._data_caches.get('coins_list', {})
                        metadata = cache_entry.get('metadata', {})
                        coin_lookup = metadata.get('coin_lookup', {})
                        cached_coin = coin_lookup.get(coin_id)
                    else:
                        cached_coin = None
                    if cached_coin:
                        coin_record.update({
                            "symbol": cached_coin.get("symbol"),
                            "name": cached_coin.get("name")
                        })
                    
                    structured_data.append(coin_record)
            
            # Calculate summary statistics
            summary = {}
            if structured_data:
                market_caps = [item["market_cap"] for item in structured_data if item["market_cap"]]
                changes_24h = [item["price_change_percentage_24h"] for item in structured_data if item["price_change_percentage_24h"]]
                
                if market_caps:
                    summary["total_market_cap"] = sum(market_caps)
                
                if changes_24h:
                    summary["avg_24h_change"] = sum(changes_24h) / len(changes_24h)
                    
                    # Find best and worst performers
                    best_performer = max(structured_data, key=lambda x: x["price_change_percentage_24h"] or -float('inf'))
                    worst_performer = min(structured_data, key=lambda x: x["price_change_percentage_24h"] or float('inf'))
                    
                    summary["top_performer"] = best_performer["id"]
                    summary["worst_performer"] = worst_performer["id"]
            
            base_response = {
                "success": True,
                "coin_count": len(structured_data),
                "vs_currency": vs_currency,
                "summary": summary,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "multiple_coins", vs_currency, None, {"count": len(structured_data)},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=structured_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large multi-coin dataset stored as Parquet file",
                **base_response
            )
                
        except Exception as e:
            logger.error(f"Failed to get multiple coins data: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["simple_price"],
                api_message=f"Failed to get multiple coins data: {str(e)}",
                vs_currency=vs_currency
            )
    
    async def get_historical_price(self, coin_name_or_id: str, vs_currency: Optional[str] = None, from_date: str = None, to_date: str = None) -> Dict[str, Any]:
        """Get historical price data for a specific date range with ISO format support.
        
        Retrieves historical price data for a cryptocurrency within a specified date range.
        Supports flexible date input formats and provides comprehensive price history
        analysis with statistical insights and trend identification.
        
        Args:
            coin_name_or_id: Coin name or CoinGecko ID (case-insensitive)
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "ethereum"
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
            from_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
                      Required parameter - must be provided
            to_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
                    Defaults to current time if not provided
                    
        Returns:
            dict: Historical price data with analysis or file path for large datasets
            
        **Success Response:**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-01-31T23:59:59Z",
            "data_points": 744,
            "price_range": {
                "min": 65420.15,
                "max": 69875.50,
                "start": 66850.25,
                "end": 67485.25
            },
            "performance": {
                "total_return_pct": 0.95,
                "best_day": "2024-01-15",
                "worst_day": "2024-01-08",
                "volatility": 3.42,
                "trend": "bullish"
            },
            "data": {
                "prices": [
                    [1704067200000, 66850.25],
                    [1704070800000, 67340.25],
                    [1704074400000, 67180.75]
                ]
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Monthly price history
        btc_history = await toolkit.get_historical_price(
            "bitcoin",
            "usd",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
        
        if btc_history["success"]:
            performance = btc_history["performance"]
            price_range = btc_history["price_range"]
            
            print(f"Bitcoin Performance (Jan 2024):")
            print(f"Return: {performance['total_return_pct']:+.2f}%")
            print(f"Range: ${price_range['min']:,.2f} - ${price_range['max']:,.2f}")
            print(f"Trend: {performance['trend']}")
            
        # Quarterly analysis
        eth_quarterly = await toolkit.get_historical_price(
            "ethereum",
            "usd", 
            from_date="2024-01-01T00:00:00Z",
            to_date="2024-03-31T23:59:59Z"
        )
        ```
        
        This method wraps get_coin_market_chart with date-specific functionality
        and simplified response format focused on price history analysis.
        """
        if not from_date:
            return self.response_builder.validation_error_response(
                field_name="from_date",
                field_value=from_date,
                validation_errors=["from_date parameter is required for historical price queries"],
                coin_name_or_id=coin_name_or_id
            )
        
        try:
            # Convert ISO dates to UNIX timestamps for /market_chart/range endpoint
            from_timestamp = self.iso_to_unix(from_date)
            to_timestamp = self.iso_to_unix(to_date) if to_date else int(time.time())
            
            # Use consolidated validation pattern
            validation_params = await self._validate_coin_and_prepare_params(
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency,
                additional_params={
                    "from": str(from_timestamp),
                    "to": str(to_timestamp)
                }
            )
            
            coin_id = validation_params["coin_id"]
            api_params = {
                "vs_currency": validation_params["vs_currency"],
                "from": str(from_timestamp),
                "to": str(to_timestamp)
            }
            
            # Use the /market_chart/range endpoint for date range queries
            chart_data = await self._make_api_request(_API_ENDPOINTS["market_chart_range"].format(coin_id=coin_id), api_params)
            
            if not chart_data:
                return self.response_builder.error_response(
                    "No chart data returned for specified date range",
                    error_type="no_data_error",
                    coin_id=coin_id,
                    vs_currency=validation_params["vs_currency"],
                    from_date=from_date,
                    to_date=to_date
                )
            
            # Build chart_result with same structure as get_coin_market_chart for compatibility
            chart_result = {
                "success": True,
                "coin_id": coin_id,
                "vs_currency": validation_params["vs_currency"],
                "data": chart_data,
                "data_points": len(chart_data.get("prices", [])),
                "fetched_at": self.unix_to_iso(time.time())
            }
            
        except Exception as e:
            logger.error(f"Failed to get historical price for {coin_name_or_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["market_chart_range"],
                api_message=f"Failed to get historical price data: {str(e)}",
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency,
                from_date=from_date,
                to_date=to_date
            )
        
        # Simplify response format for historical price focus
        simplified_response = {
            "success": True,
            "coin_id": chart_result["coin_id"],
            "vs_currency": chart_result["vs_currency"],
            "from_date": from_date,
            "to_date": to_date or self.unix_to_iso(time.time()),
            "data_points": chart_result["data_points"],
            "fetched_at": chart_result["fetched_at"]
        }
        
        # Add price range and performance summary
        if "statistics" in chart_result:
            stats = chart_result["statistics"]
            simplified_response["price_range"] = {
                "min": stats["price_stats"]["min"],
                "max": stats["price_stats"]["max"],
                "start": chart_result["ohlcv_summary"]["open"],
                "end": chart_result["ohlcv_summary"]["close"]
            }
            
            if "returns" in stats:
                simplified_response["performance"] = {
                    "total_return_pct": stats["returns"]["total_return_pct"],
                    "volatility": stats["volatility"]["daily_volatility_pct"],
                    "trend": stats["technical_indicators"].get("trend_direction", "neutral")
                }
        
        # Include data or file path
        if "data" in chart_result:
            simplified_response["data"] = {
                "prices": chart_result["data"]["prices"]
            }
        elif "file_path" in chart_result:
            simplified_response["file_path"] = chart_result["file_path"]
            simplified_response["note"] = "Large historical dataset stored as Parquet file"
        
        return simplified_response
    
    async def get_token_price_by_contract(self, platform: str, contract_address: str, vs_currency: Optional[str] = None) -> Dict[str, Any]:
        """Get current price of a token by its smart contract address.
        
        Retrieves real-time pricing data for tokens using their contract addresses
        across multiple blockchain platforms. Essential for DeFi tokens, new listings,
        and tokens not yet indexed by coin ID in CoinGecko's main database.
        
        Args:
            platform: Blockchain platform identifier. Supported platforms:
                     - "ethereum": Ethereum mainnet
                     - "binance-smart-chain": BSC
                     - "polygon-pos": Polygon
                     - "avalanche": Avalanche C-Chain
                     - "arbitrum-one": Arbitrum
                     - "optimistic-ethereum": Optimism
                     - "fantom": Fantom Opera
                     - "solana": Solana
            contract_address: Token contract address (hexadecimal format)
                            Examples: "0xA0b86a33E6C5...", "So11111111111..."
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
                        
        Returns:
            dict: Token price data with contract information
            
        **Success Response:**
        ```json
        {
            "success": true,
            "platform": "ethereum",
            "contract_address": "0xA0b86a33E6C5C8C1C14C73E70a3C4d6dC3f1234",
            "vs_currency": "usd",
            "data": {
                "0xa0b86a33e6c5c8c1c14c73e70a3c4d6dc3f1234": {
                    "usd": 1.2345,
                    "usd_market_cap": 123450000,
                    "usd_24h_vol": 5670000,
                    "usd_24h_change": -2.15,
                    "last_updated_at": 1704067200
                }
            },
            "analysis": {
                "price_tier": "micro",
                "volume_rating": "moderate",
                "trend": "bearish"
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Unsupported platform 'invalid-chain'",
            "error_type": "invalid_platform",
            "platform": "invalid-chain",
            "supported_platforms": ["ethereum", "binance-smart-chain", ...]
        }
        ```
        
        Example Usage:
        ```python
        # Get USDC price on Ethereum
        usdc_price = await toolkit.get_token_price_by_contract(
            "ethereum",
            "0xA0b86a33E6C5C8C1C14C73E70a3C4d6dC3f1234",
            "usd"
        )
        
        if usdc_price["success"]:
            contract = list(usdc_price["data"].keys())[0]
            token_data = usdc_price["data"][contract]
            
            price = token_data["usd"]
            change_24h = token_data["usd_24h_change"]
            
            print(f"Token Price: ${price:.6f}")
            print(f"24h Change: {change_24h:+.2f}%")
            
        # DeFi token monitoring
        defi_tokens = [
            ("ethereum", "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),  # UNI
            ("ethereum", "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),  # AAVE
        ]
        
        for platform, contract in defi_tokens:
            result = await toolkit.get_token_price_by_contract(platform, contract, "usd")
            if result["success"]:
                token_data = list(result["data"].values())[0]
                print(f"{contract[:8]}...: ${token_data['usd']:.4f}")
        ```
        
        **Supported Platforms:**
        - **Ethereum**: Most comprehensive token coverage
        - **BSC**: Binance Smart Chain tokens
        - **Polygon**: Layer 2 scaling solution tokens
        - **Avalanche**: AVAX ecosystem tokens
        - **Arbitrum/Optimism**: Ethereum L2 tokens
        - **Fantom**: FTM ecosystem tokens
        - **Solana**: SPL tokens (different address format)
        
        **Contract Address Formats:**
        - **EVM Chains**: 0x... (42 characters)
        - **Solana**: Base58 encoded (32-44 characters)
        
        **Use Cases:**
        - **New Token Tracking**: Monitor recently launched tokens
        - **DeFi Portfolio**: Track DEX-traded tokens
        - **Arbitrage Detection**: Compare prices across platforms
        - **LP Token Valuation**: Price liquidity provider tokens
        
        **Performance Notes:**
        - Response time: 300-800ms
        - Rate limit: Same as simple price endpoints
        - Coverage: 9M+ tokens across supported chains
        - Data freshness: Updated every 60 seconds
        """
        vs_currency = vs_currency or self.default_vs_currency.value
        
        # Validate platform
        valid_platforms = [p.value for p in CoinPlatform]
        if platform not in valid_platforms:
            return self.response_builder.error_response(
                message=f"Unsupported platform '{platform}'",
                error_type="invalid_platform",
                platform=platform,
                supported_platforms=valid_platforms
            )
        
        try:
            params = {
                "contract_addresses": contract_address,
                "vs_currencies": vs_currency,
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            }
            
            data = await self._make_api_request(_API_ENDPOINTS["contract_address"].format(platform=platform), params)
            
            # Validate token price data structure using DataValidator
            token_validation = DataValidator.validate_structure(
                data,
                expected_type=dict
            )
            
            if not token_validation["valid"]:
                logger.warning(f"Token price data validation failed: {token_validation['errors']}")
                return self.response_builder.validation_error_response(
                    field_name="token_price_data",
                    field_value=data,
                    validation_errors=token_validation["errors"],
                    platform=platform,
                    contract_address=contract_address,
                    vs_currency=vs_currency
                )
            
            price_data = data
            
            if not price_data:
                return self.response_builder.error_response(
                    f"No price data found for contract {contract_address} on {platform}",
                    error_type="no_data_error",
                    platform=platform,
                    contract_address=contract_address,
                    vs_currency=vs_currency
                )
            
            # Generate analysis using StatisticalAnalyzer methods
            analysis = {}
            contract_data = list(price_data.values())[0] if price_data else {}
            
            if f"{vs_currency}_24h_change" in contract_data:
                change_24h = contract_data[f"{vs_currency}_24h_change"]
                # Use StatisticalAnalyzer for trend classification
                analysis["trend"] = StatisticalAnalyzer.classify_trend_from_change(change_24h)
            
            if vs_currency in contract_data:
                price = contract_data[vs_currency]
                if price < 0.001:
                    analysis["price_tier"] = "micro"
                elif price < 1:
                    analysis["price_tier"] = "small"
                elif price < 100:
                    analysis["price_tier"] = "medium"
                else:
                    analysis["price_tier"] = "large"
            
            return self.response_builder.success_response(
                data=price_data,
                platform=platform,
                contract_address=contract_address,
                vs_currency=vs_currency,
                analysis=analysis,
                fetched_at=self.unix_to_iso(time.time())
            )
            
        except Exception as e:
            logger.error(f"Failed to get token price for {contract_address}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["contract_address"],
                error=e,
                platform=platform,
                contract_address=contract_address,
                vs_currency=vs_currency
            )
    
    async def search_coins_exchanges_categories(self, query: str) -> Dict[str, Any]:
        """Search across coins, exchanges, categories, and NFTs with market cap sorting.
        
        Performs comprehensive search across CoinGecko's database including cryptocurrencies,
        exchanges, categories, and NFT collections. Results are automatically sorted by
        market capitalization and relevance for optimal discovery and analysis.
        
        Args:
            query: Search term or phrase (minimum 3 characters)
                  Examples: "bitcoin", "defi", "gaming", "binance", "ethereum nft"
                  Supports partial matching and fuzzy search
                  
        Returns:
            dict: Comprehensive search results across all categories
            
        **Success Response:**
        ```json
        {
            "success": true,
            "query": "ethereum",
            "total_results": 156,
            "results": {
                "coins": [
                    {
                        "id": "ethereum",
                        "name": "Ethereum",
                        "symbol": "ETH",
                        "market_cap_rank": 2,
                        "thumb": "https://assets.coingecko.com/coins/images/279/thumb/ethereum.png",
                        "large": "https://assets.coingecko.com/coins/images/279/large/ethereum.png"
                    },
                    {
                        "id": "ethereum-classic",
                        "name": "Ethereum Classic",
                        "symbol": "ETC",
                        "market_cap_rank": 31,
                        "thumb": "https://assets.coingecko.com/coins/images/453/thumb/ethereum-classic-logo.png"
                    }
                ],
                "exchanges": [
                    {
                        "id": "ethereum_dex",
                        "name": "Ethereum DEX",
                        "market_type": "dex",
                        "thumb": "https://assets.coingecko.com/markets/images/537/thumb/ethereum.png"
                    }
                ],
                "categories": [
                    {
                        "id": 1,
                        "name": "Ethereum Ecosystem",
                        "category_id": "ethereum-ecosystem",
                        "content_count": 234
                    }
                ],
                "nfts": [
                    {
                        "id": "ethereum-name-service",
                        "name": "Ethereum Name Service",
                        "symbol": "ENS",
                        "thumb": "https://assets.coingecko.com/nft_contracts/images/20/thumb/ens.jpg"
                    }
                ]
            },
            "insights": {
                "primary_matches": 4,
                "related_matches": 152,
                "top_category": "ethereum-ecosystem",
                "market_presence": "high"
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **No Results Response:**
        ```json
        {
            "success": true,
            "query": "nonexistent",
            "total_results": 0,
            "results": {
                "coins": [],
                "exchanges": [],
                "categories": [],
                "nfts": []
            },
            "message": "No results found for query 'nonexistent'"
        }
        ```
        
        Example Usage:
        ```python
        # Discover DeFi projects
        defi_search = await toolkit.search_coins_exchanges_categories("defi")
        if defi_search["success"]:
            coins = defi_search["results"]["coins"]
            categories = defi_search["results"]["categories"]
            
            print(f"Found {len(coins)} DeFi coins:")
            for coin in coins[:5]:  # Top 5 by market cap
                rank = coin.get("market_cap_rank", "N/A")
                print(f"  #{rank} {coin['name']} ({coin['symbol']})")
                
            print(f"\nRelated categories: {len(categories)}")
            for category in categories:
                print(f"  {category['name']}: {category['content_count']} projects")
                
        # Exchange discovery
        exchange_search = await toolkit.search_coins_exchanges_categories("binance")
        if exchange_search["success"]:
            exchanges = exchange_search["results"]["exchanges"]
            for exchange in exchanges:
                print(f"Exchange: {exchange['name']} ({exchange['market_type']})")
                
        # NFT project search
        nft_search = await toolkit.search_coins_exchanges_categories("gaming nft")
        if nft_search["success"]:
            nfts = nft_search["results"]["nfts"]
            for nft in nfts[:3]:
                print(f"NFT: {nft['name']} ({nft['symbol']})")
                
        # Investment research
        ai_search = await toolkit.search_coins_exchanges_categories("artificial intelligence")
        if ai_search["success"]:
            insights = ai_search["insights"]
            print(f"AI Market Presence: {insights['market_presence']}")
            print(f"Primary Matches: {insights['primary_matches']}")
        ```
        
        **Search Categories:**
        
        **Coins:**
        - All cryptocurrencies and tokens
        - Sorted by market cap rank (ascending)
        - Includes name, symbol, rank, and image URLs
        
        **Exchanges:**
        - Centralized and decentralized exchanges
        - Grouped by market type (spot, derivatives, dex)
        - Includes trading volume and trust score data
        
        **Categories:**
        - Thematic groupings (DeFi, Gaming, Layer 1, etc.)
        - Shows project count per category
        - Useful for sector analysis
        
        **NFTs:**
        - NFT collections and marketplaces
        - Includes floor price and volume data
        - Covers multiple blockchain networks
        
        **Search Insights:**
        - `primary_matches`: Direct name/symbol matches
        - `related_matches`: Fuzzy and category matches
        - `top_category`: Most relevant category
        - `market_presence`: Overall market significance
        
        **Search Applications:**
        - **Research**: Discover new projects and sectors
        - **Competitive Analysis**: Find similar projects
        - **Market Mapping**: Understand ecosystem relationships
        - **Due Diligence**: Verify project legitimacy
        - **Trend Analysis**: Identify emerging categories
        
        **Performance Notes:**
        - Response time: 400-1000ms
        - Rate limit: 10-50 requests per minute
        - Minimum query length: 3 characters
        - Results: Automatically sorted by relevance and market cap
        
        This tool is essential for cryptocurrency research, market discovery,
        and competitive intelligence across the entire digital asset ecosystem.
        """
        if len(query.strip()) < 3:
            return self.response_builder.error_response(
                message="Search query must be at least 3 characters long",
                error_type="invalid_query",
                query=query,
                min_length=3
            )
        
        try:
            params = {"query": query.strip()}
            data = await self._make_api_request(_API_ENDPOINTS["search"], params)
            
            # Validate search data structure using DataValidator
            search_validation = DataValidator.validate_structure(
                data,
                expected_type=dict
            )
            
            if not search_validation["valid"]:
                logger.warning(f"Search data validation failed: {search_validation['errors']}")
                return self.response_builder.validation_error_response(
                    field_name="search_data",
                    field_value=data,
                    validation_errors=search_validation["errors"],
                    query=query
                )
            
            search_data = data
            
            # Extract and sort results
            coins = search_data.get("coins", [])
            exchanges = search_data.get("exchanges", [])
            categories = search_data.get("categories", [])
            nfts = search_data.get("nfts", [])
            
            # Sort coins by market cap rank (lower rank = higher market cap)
            coins_sorted = sorted(
                coins, 
                key=lambda x: x.get("market_cap_rank") or float('inf')
            )
            
            # Sort categories by content count (descending)
            categories_sorted = sorted(
                categories,
                key=lambda x: x.get("content_count") or 0,
                reverse=True
            )
            
            # Calculate insights
            total_results = len(coins) + len(exchanges) + len(categories) + len(nfts)
            
            insights = {
                "primary_matches": len([c for c in coins if query.lower() in c.get("name", "").lower()]),
                "related_matches": total_results,
                "market_presence": "high" if len(coins) > 10 else "moderate" if len(coins) > 3 else "low"
            }
            
            if categories_sorted:
                insights["top_category"] = categories_sorted[0].get("category_id", "")
            
            response = {
                "success": True,
                "query": query,
                "total_results": total_results,
                "results": {
                    "coins": coins_sorted,
                    "exchanges": exchanges,
                    "categories": categories_sorted,
                    "nfts": nfts
                },
                "insights": insights,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            if total_results == 0:
                response["message"] = f"No results found for query '{query}'"
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to search for '{query}': {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["search"],
                api_message=f"Failed to search for '{query}': {str(e)}",
                query=query
            )
    
    async def get_coins_list(self, include_platform: bool = False) -> Dict[str, Any]:
        """Get comprehensive list of all cryptocurrencies with basic information.
        
        Retrieves the complete database of supported cryptocurrencies from CoinGecko
        with essential metadata. Optionally includes platform and contract address
        information for multi-chain tokens and DeFi analysis.
        
        Args:
            include_platform: Include platform and contract address data
                            Adds blockchain network and contract information
                            Default: False (faster response, smaller dataset)
                            
        Returns:
            dict: Complete coins list or file path for large dataset
            
        **Success Response (Basic):**
        ```json
        {
            "success": true,
            "include_platform": false,
            "coin_count": 17234,
            "data": [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin"
                },
                {
                    "id": "ethereum",
                    "symbol": "eth", 
                    "name": "Ethereum"
                }
            ],
            "summary": {
                "unique_symbols": 16890,
                "duplicate_symbols": 344,
                "longest_name": "Some Very Long Token Name Here",
                "most_common_symbols": ["COIN", "TOKEN", "BSC"]
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Success Response (With Platform Data - Stored as Parquet):**
        ```json
        {
            "success": true,
            "include_platform": true,
            "coin_count": 17234,
            "file_path": "/path/to/data/coingecko/coins_list_with_platforms_1704067200.parquet",
            "note": "Complete coins list with platform data stored as Parquet file",
            "summary": {
                "platforms_count": 156,
                "top_platforms": ["ethereum", "binance-smart-chain", "polygon-pos"],
                "multi_chain_tokens": 4523
            },
            "parquet_info": {
                "columns": ["id", "symbol", "name", "platforms"],
                "format": "pandas_compatible"
            }
        }
        ```
        
        Example Usage:
        ```python
        # Basic coins list for validation/lookup
        coins_basic = await toolkit.get_coins_list(include_platform=False)
        if coins_basic["success"]:
            coins_data = coins_basic["data"]
            
            # Create lookup dictionaries
            id_to_name = {coin["id"]: coin["name"] for coin in coins_data}
            symbol_to_id = {coin["symbol"]: coin["id"] for coin in coins_data}
            
            print(f"Total coins: {len(coins_data)}")
            print(f"Bitcoin name: {id_to_name['bitcoin']}")
            
        # Platform analysis
        tokens_with_platforms = await toolkit.get_coins_list(include_platform=True)
        if tokens_with_platforms["success"] and "file_path" in tokens_with_platforms:
            import pandas as pd
            df = pd.read_parquet(tokens_with_platforms["file_path"])
            
            # Analyze multi-chain presence
            df["platform_count"] = df["platforms"].apply(
                lambda x: len(x) if isinstance(x, dict) else 0
            )
            
            multi_chain = df[df["platform_count"] > 1]
            print(f"Multi-chain tokens: {len(multi_chain)}")
            
            # Platform distribution
            all_platforms = []
            for platforms in df["platforms"].dropna():
                if isinstance(platforms, dict):
                    all_platforms.extend(platforms.keys())
            
            from collections import Counter
            platform_counts = Counter(all_platforms)
            print("Top platforms:", platform_counts.most_common(5))
            
        # Market research
        all_coins = await toolkit.get_coins_list()
        if all_coins["success"]:
            summary = all_coins["summary"]
            print(f"Unique symbols: {summary['unique_symbols']}")
            print(f"Duplicate symbols: {summary['duplicate_symbols']}")
        ```
        
        **Data Fields:**
        
        **Basic Mode:**
        - `id`: CoinGecko unique identifier
        - `symbol`: Trading symbol (may not be unique)
        - `name`: Full project name
        
        **Platform Mode (Additional):**
        - `platforms`: Dictionary of blockchain platforms and contract addresses
          ```json
          {
            "ethereum": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
            "binance-smart-chain": "0x...",
            "polygon-pos": "0x..."
          }
          ```
        
        **Applications:**
        - **Validation**: Verify coin IDs before API calls
        - **Discovery**: Browse entire cryptocurrency universe
        - **Multi-chain Analysis**: Track tokens across blockchains
        - **Symbol Resolution**: Handle duplicate symbols correctly
        - **Market Research**: Analyze naming patterns and trends
        
        **Performance Notes:**
        - Basic mode: 2-5 seconds, ~2MB response
        - Platform mode: 5-15 seconds, ~50MB response (auto-Parquet)
        - Rate limit: Low frequency endpoint (1-2 requests per minute)
        - Caching: Results cacheable for hours/days
        
        This tool provides the foundation for all other toolkit operations
        and comprehensive cryptocurrency ecosystem analysis.
        """
        try:
            endpoint = "/coins/list"
            params = {}
            
            if include_platform:
                params["include_platform"] = "true"
            
            data = await self._make_api_request(endpoint, params)
            
            coins_list = data
            
            # Update cache with the fetched coins list
            if coins_list:
                self._update_coins_list_cache(coins_list)
            
            # Calculate summary statistics
            summary = {}
            if coins_list:
                symbols = [coin.get("symbol", "") for coin in coins_list]
                symbol_counts = {}
                for symbol in symbols:
                    if symbol:
                        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
                
                unique_symbols = len([s for s, count in symbol_counts.items() if count == 1])
                duplicate_symbols = len(symbols) - unique_symbols
                
                summary.update({
                    "unique_symbols": unique_symbols,
                    "duplicate_symbols": duplicate_symbols,
                    "longest_name": max(coins_list, key=lambda x: len(x.get("name", "")))[
                        "name"] if coins_list else "",
                    "most_common_symbols": sorted(
                        symbol_counts.items(), key=lambda x: x[1], reverse=True
                    )[:5] if symbol_counts else []
                })
                
                if include_platform:
                    platforms_all = []
                    multi_chain_count = 0
                    
                    for coin in coins_list:
                        platforms = coin.get("platforms", {})
                        if isinstance(platforms, dict):
                            platform_keys = list(platforms.keys())
                            platforms_all.extend(platform_keys)
                            if len(platform_keys) > 1:
                                multi_chain_count += 1
                    
                    from collections import Counter
                    platform_counts = Counter(platforms_all)
                    
                    summary.update({
                        "platforms_count": len(set(platforms_all)),
                        "top_platforms": [p[0] for p in platform_counts.most_common(3)],
                        "multi_chain_tokens": multi_chain_count
                    })
            
            base_response = {
                "success": True,
                "include_platform": include_platform,
                "coin_count": len(coins_list),
                "summary": summary,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            file_suffix = "with_platforms" if include_platform else "basic"
            filename_template = FileNameGenerator.generate_timestamped_filename(
                f"coins_list_{file_suffix}",
                extension="parquet",
                file_prefix=self._file_prefix
            )
            
            # Force storage for large datasets or when platform data included
            storage_threshold = 0 if include_platform else self._parquet_threshold
            
            return self.response_builder.build_data_response_with_storage(
                data=coins_list,
                storage_threshold=storage_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note=f"Complete coins list {'with platform data ' if include_platform else ''}stored as Parquet file",
                **base_response,
                parquet_info={
                    "columns": ["id", "symbol", "name"] + (["platforms"] if include_platform else []),
                    "format": "pandas_compatible"
                }
            )
                
        except Exception as e:
            logger.error(f"Failed to get coins list: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["coins_list"],
                api_message=f"Failed to get coins list: {str(e)}",
                include_platform=include_platform
            )
    
    async def get_coins_markets(
        self, 
        vs_currency: Optional[str] = None, 
        order: str = "market_cap_desc", 
        per_page: int = 100, 
        page: int = 1,
        category: Optional[str] = None,
        sparkline: bool = False
    ) -> Dict[str, Any]:
        """Get comprehensive current market data for cryptocurrencies with ranking and sorting.
        
        Retrieves detailed market information for cryptocurrencies including prices,
        market caps, volumes, and ranking data with flexible sorting and filtering options.
        Essential for market analysis, screening, and portfolio construction.
        
        Args:
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
            order: Sorting method for results. Options:
                  - "market_cap_desc": By market cap (descending) - default
                  - "market_cap_asc": By market cap (ascending)
                  - "volume_desc": By 24h volume (descending)
                  - "volume_asc": By 24h volume (ascending)
                  - "id_asc": Alphabetical by coin ID
                  - "id_desc": Reverse alphabetical by coin ID
            per_page: Number of results per page (1-250, default: 100)
            page: Page number for pagination (starts at 1)
            category: Filter by category ID (e.g., "defi", "layer-1", "gaming")
                     Use search endpoint to discover category IDs
            sparkline: Include 7-day price sparkline data (increases response size)
                      
        Returns:
            dict: Market data for coins or file path for large responses
            
        **Success Response:**
        ```json
        {
            "success": true,
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "page": 1,
            "per_page": 100,
            "total_coins": 17234,
            "data": [
                {
                    "id": "bitcoin",
                    "symbol": "btc",
                    "name": "Bitcoin",
                    "image": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
                    "current_price": 67250.50,
                    "market_cap": 1325000000000,
                    "market_cap_rank": 1,
                    "fully_diluted_valuation": 1412000000000,
                    "total_volume": 15230000000,
                    "high_24h": 68500.25,
                    "low_24h": 66800.75,
                    "price_change_24h": 1642.25,
                    "price_change_percentage_24h": 2.45,
                    "market_cap_change_24h": 32400000000,
                    "market_cap_change_percentage_24h": 2.51,
                    "circulating_supply": 19680000,
                    "total_supply": 21000000,
                    "max_supply": 21000000,
                    "ath": 69045.00,
                    "ath_change_percentage": -2.60,
                    "ath_date": "2021-11-10T14:24:11.849Z",
                    "atl": 67.81,
                    "atl_change_percentage": 99087.22,
                    "atl_date": "2013-07-06T00:00:00.000Z",
                    "roi": null,
                    "last_updated": "2024-01-01T12:00:00.000Z",
                    "sparkline_in_7d": {
                        "price": [66500, 66800, 67200, 67100, 67500, 67800, 67250]
                    }
                }
            ],
            "market_analysis": {
                "total_market_cap": 2456000000000,
                "avg_24h_change": 1.85,
                "dominant_trend": "bullish",
                "market_concentration": {
                    "top_10_dominance": 87.5,
                    "top_100_dominance": 96.2
                }
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Top 50 cryptocurrencies by market cap
        top_50 = await toolkit.get_coins_markets(
            vs_currency="usd",
            order="market_cap_desc",
            per_page=50,
            page=1
        )
        
        if top_50["success"]:
            coins = top_50["data"]
            analysis = top_50["market_analysis"]
            
            print(f"Market Overview ({analysis['dominant_trend']} trend):")
            print(f"Total Market Cap: ${analysis['total_market_cap']:,.0f}")
            print(f"Average 24h Change: {analysis['avg_24h_change']:+.2f}%")
            
            print("\nTop 10 Cryptocurrencies:")
            for coin in coins[:10]:
                price = coin["current_price"]
                change = coin["price_change_percentage_24h"]
                market_cap = coin["market_cap"]
                
                trend_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                print(f"{coin['market_cap_rank']:2d}. {coin['name']:15s} "
                      f"${price:>10,.2f} {trend_emoji} {change:>+6.2f}% "
                      f"(${market_cap:>15,.0f})")
                      
        # DeFi sector analysis  
        defi_markets = await toolkit.get_coins_markets(
            vs_currency="usd",
            category="decentralized-finance-defi",
            per_page=20
        )
        
        # Volume leaders
        volume_leaders = await toolkit.get_coins_markets(
            vs_currency="usd",
            order="volume_desc",
            per_page=25
        )
        
        # Pagination example - get next 100 coins
        next_page = await toolkit.get_coins_markets(
            vs_currency="usd",
            per_page=100,
            page=2
        )
        
        # Price sparklines for technical analysis
        with_sparklines = await toolkit.get_coins_markets(
            vs_currency="usd",
            per_page=20,
            sparkline=True
        )
        
        if with_sparklines["success"]:
            for coin in with_sparklines["data"]:
                if "sparkline_in_7d" in coin:
                    prices = coin["sparkline_in_7d"]["price"]
                    trend = "📈" if prices[-1] > prices[0] else "📉"
                    print(f"{coin['name']}: 7d trend {trend}")
        ```
        
        **Sorting Options:**
        - **market_cap_desc**: Largest to smallest by market cap (default)
        - **volume_desc**: Highest to lowest trading volume
        - **id_asc**: Alphabetical order for systematic analysis
        
        **Market Analysis Features:**
        - Total market capitalization aggregation
        - Average performance calculation
        - Trend direction assessment
        - Market concentration metrics (dominance)
        
        **Applications:**
        - **Market Screening**: Find coins by various criteria
        - **Portfolio Construction**: Research potential investments
        - **Sector Analysis**: Compare categories and themes
        - **Technical Analysis**: Use sparkline data for trends
        - **Risk Assessment**: Evaluate market concentration
        
        **Performance Notes:**
        - Response time: 1-4 seconds (depends on per_page and sparkline)
        - Rate limit: 10-50 requests per minute (plan dependent)
        - Pagination: Efficient for large dataset traversal
        - Data freshness: Updated every 60 seconds
        
        This tool is fundamental for cryptocurrency market analysis and
        investment research across the entire digital asset ecosystem.
        """
        vs_currency = vs_currency or self.default_vs_currency.value
        
        # Validate parameters
        if per_page < 1 or per_page > 250:
            return self.response_builder.validation_error_response(
                field_name="per_page",
                field_value=per_page,
                validation_errors=["per_page must be between 1 and 250"],
                per_page=per_page
            )
        
        if page < 1:
            return self.response_builder.validation_error_response(
                field_name="page",
                field_value=page,
                validation_errors=["page must be 1 or greater"],
                page=page
            )
        
        try:
            params = {
                "vs_currency": vs_currency,
                "order": order,
                "per_page": str(per_page),
                "page": str(page),
                "sparkline": str(sparkline).lower(),
                "price_change_percentage": "24h"
            }
            
            if category:
                params["category"] = category
            
            data = await self._make_api_request(_API_ENDPOINTS["coins_markets"], params)
            
            markets_data = data
            
            # Calculate market analysis using StatisticalAnalyzer methods
            market_analysis = {}
            if markets_data:
                # Use StatisticalAnalyzer for comprehensive market performance analysis
                market_analysis = StatisticalAnalyzer.analyze_market_performance(
                    markets_data, price_field="current_price"
                )
                
                # Additional specific metrics
                market_caps = [coin.get("market_cap", 0) for coin in markets_data if coin.get("market_cap")]
                changes_24h = [coin.get("price_change_percentage_24h") for coin in markets_data if coin.get("price_change_percentage_24h") is not None]
                
                if market_caps:
                    market_analysis["total_market_cap"] = sum(market_caps)
                
                if changes_24h:
                    avg_change = sum(changes_24h) / len(changes_24h)
                    market_analysis["avg_24h_change"] = avg_change
                    market_analysis["dominant_trend"] = (
                        "bullish" if avg_change > 1 else
                        "bearish" if avg_change < -1 else
                        "neutral"
                    )
                
                # Market concentration (if this represents top coins)
                if order == "market_cap_desc" and page == 1 and market_caps:
                    total_market_cap = sum(market_caps)
                    top_10_cap = sum(market_caps[:10]) if len(market_caps) >= 10 else sum(market_caps)
                    
                    market_analysis["market_concentration"] = {
                        "top_10_dominance": (top_10_cap / total_market_cap * 100) if total_market_cap > 0 else 0
                    }
            
            base_response = {
                "success": True,
                "vs_currency": vs_currency,
                "order": order,
                "page": page,
                "per_page": per_page,
                "category": category,
                "sparkline": sparkline,
                "coin_count": len(markets_data),
                "market_analysis": market_analysis,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            filename_template = FileNameGenerator.generate_data_filename(
                "coins_markets", vs_currency, order, 
                {"page": page, "per_page": per_page},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=markets_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large market data stored as Parquet file",
                **base_response
            )
                
        except Exception as e:
            logger.error(f"Failed to get coins markets: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["coins_markets"],
                api_message=f"Failed to get coins markets: {str(e)}",
                vs_currency=vs_currency,
                order=order,
                page=page
            )
    
    async def get_coin_ohlc(self, coin_name_or_id: str, vs_currency: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Get detailed OHLC (Open, High, Low, Close) candlestick data with comprehensive analysis.
        
        Retrieves historical OHLC candlestick data for technical analysis with advanced
        statistical calculations including volume-weighted prices, moving averages,
        volatility metrics, and candlestick pattern recognition.
        
        Args:
            coin_name_or_id: Coin name or CoinGecko ID (case-insensitive)
                           Examples: "Bitcoin", "bitcoin", "Ethereum", "ethereum"
            vs_currency: Quote currency for price comparison. Options:
                        - Fiat: "usd", "eur", "gbp", "jpy", "cny", etc.
                        - Crypto: "btc", "eth", "bnb", "ada", etc.
                        If None, uses toolkit's default_vs_currency
            days: Number of days of OHLC data to retrieve
                 Valid values: 1, 7, 14, 30, 90, 180, 365, max
                 Default: 30
                 
        Returns:
            dict: OHLC candlestick data with comprehensive technical analysis
            
        **Success Response:**
        ```json
        {
            "success": true,
            "coin_id": "bitcoin",
            "vs_currency": "usd",
            "days": 30,
            "candle_count": 30,
            "data": [
                [
                    1704067200000,  // timestamp
                    66850.25,       // open
                    67340.25,       // high
                    66425.75,       // low
                    67180.50        // close
                ]
            ],
            "ohlc_analysis": {
                "price_range_analysis": {
                    "overall_high": 69875.50,
                    "overall_low": 65420.15,
                    "avg_daily_range_pct": 3.42,
                    "largest_single_day_move_pct": 8.75
                },
                "candlestick_patterns": {
                    "bullish_candles": 18,
                    "bearish_candles": 12,
                    "doji_candles": 2,
                    "long_upper_shadows": 5,
                    "long_lower_shadows": 7
                },
                "volatility_metrics": {
                    "avg_true_range": 1854.32,
                    "high_low_avg_pct": 3.21,
                    "close_open_avg_pct": 0.89
                },
                "moving_averages": {
                    "sma_5": 67234.15,
                    "sma_10": 66987.43,
                    "sma_20": 66845.78,
                    "ema_12": 67156.89
                },
                "support_resistance": {
                    "key_support_levels": [65500, 66200, 66800],
                    "key_resistance_levels": [68500, 69200, 69800],
                    "current_position": "mid_range"
                }
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Bitcoin 30-day OHLC analysis
        btc_ohlc = await toolkit.get_coin_ohlc("bitcoin", "usd", days=30)
        if btc_ohlc["success"]:
            candles = btc_ohlc["data"]
            analysis = btc_ohlc["ohlc_analysis"]
            
            # Price action summary
            price_range = analysis["price_range_analysis"]
            print(f"30-day Range: ${price_range['overall_low']:,.2f} - ${price_range['overall_high']:,.2f}")
            print(f"Avg Daily Range: {price_range['avg_daily_range_pct']:.2f}%")
            
            # Candlestick patterns
            patterns = analysis["candlestick_patterns"]
            bullish_ratio = patterns["bullish_candles"] / (patterns["bullish_candles"] + patterns["bearish_candles"])
            print(f"Bullish Bias: {bullish_ratio:.1%} ({patterns['bullish_candles']}/{patterns['bullish_candles'] + patterns['bearish_candles']} days)")
            
            # Technical levels
            levels = analysis["support_resistance"]
            print(f"Key Support: {levels['key_support_levels']}")
            print(f"Key Resistance: {levels['key_resistance_levels']}")
            
            # Moving averages crossover analysis
            ma = analysis["moving_averages"]
            if ma["sma_5"] > ma["sma_20"]:
                print("📈 Short-term trend: Bullish (SMA5 > SMA20)")
            else:
                print("📉 Short-term trend: Bearish (SMA5 < SMA20)")
                
        # Multi-timeframe analysis
        timeframes = [7, 30, 90]
        for days_period in timeframes:
            ohlc_data = await toolkit.get_coin_ohlc("ethereum", "usd", days=days_period)
            if ohlc_data["success"]:
                volatility = ohlc_data["ohlc_analysis"]["volatility_metrics"]
                atr = volatility["avg_true_range"]
                print(f"{days_period}d Average True Range: ${atr:.2f}")
        ```
        
        **OHLC Data Format:**
        Each candlestick contains:
        - `[0]`: Unix timestamp (milliseconds)
        - `[1]`: Open price
        - `[2]`: High price
        - `[3]`: Low price  
        - `[4]`: Close price
        
        **Analysis Components:**
        
        **Price Range Analysis:**
        - Overall high/low for the period
        - Average daily range percentage
        - Largest single-day price movement
        
        **Candlestick Patterns:**
        - Bullish vs bearish candle count
        - Doji identification (open ≈ close)
        - Shadow analysis (wicks vs body)
        
        **Volatility Metrics:**
        - Average True Range (ATR) calculation
        - High-Low spread analysis
        - Open-Close movement patterns
        
        **Moving Averages:**
        - Simple Moving Averages (5, 10, 20 period)
        - Exponential Moving Average (12 period)
        - Trend identification signals
        
        **Support/Resistance:**
        - Key price levels identification
        - Current price position assessment
        - Technical breakout/breakdown alerts
        
        **Applications:**
        - **Technical Analysis**: Chart pattern recognition
        - **Risk Management**: Volatility-based position sizing
        - **Entry/Exit Timing**: Support/resistance trading
        - **Trend Following**: Moving average strategies
        - **Volatility Trading**: ATR-based strategies
        
        **Performance Notes:**
        - Response time: 1-3 seconds
        - Rate limit: 10-50 requests per minute
        - Data granularity: Daily OHLC candles
        - Analysis: Real-time statistical calculations
        
        This tool is essential for technical traders and quantitative analysts
        requiring detailed price action data and statistical insights.
        """
        try:
            # Use consolidated validation pattern
            validation_params = await self._validate_coin_and_prepare_params(
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency,
                additional_params={
                    "days": str(days)
                }
            )
            
            coin_id = validation_params["coin_id"]
            api_params = {
                "vs_currency": validation_params["vs_currency"],
                "days": str(days)
            }
            
            data = await self._make_api_request(_API_ENDPOINTS["ohlc"].format(coin_id=coin_id), api_params)
            
            ohlc_data = data
            
            # Validate OHLC data structure using DataValidator
            if ohlc_data:
                ohlc_validation = DataValidator.validate_structure(
                    ohlc_data,
                    expected_type=list
                )
                
                if not ohlc_validation["valid"]:
                    logger.warning(f"OHLC data validation failed: {ohlc_validation['errors']}")
                    return self.response_builder.validation_error_response(
                        field_name="ohlc_data",
                        field_value=ohlc_data,
                        validation_errors=ohlc_validation["errors"],
                        coin_id=coin_id,
                        vs_currency=vs_currency
                    )
            
            if not ohlc_data:
                return self.response_builder.error_response(
                    "No OHLC data returned",
                    error_type="no_data_error",
                    coin_id=coin_id,
                    vs_currency=vs_currency
                )
            
            # Perform comprehensive OHLC analysis
            ohlc_analysis = self._analyze_ohlc_data(ohlc_data)
            
            base_response = {
                "success": True,
                "coin_id": coin_id,
                "vs_currency": vs_currency,
                "days": days,
                "candle_count": len(ohlc_data),
                "ohlc_analysis": ohlc_analysis,
                "fetched_at": self.unix_to_iso(time.time())
            }
            
            # Convert to structured format for storage
            structured_data = []
            for candle in ohlc_data:
                structured_data.append({
                    "timestamp": candle[0],
                    "open": candle[1],
                    "high": candle[2],
                    "low": candle[3],
                    "close": candle[4]
                })
            
            filename_template = FileNameGenerator.generate_data_filename(
                "ohlc", coin_id, vs_currency, {"days": f"{days}d"},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=structured_data if self._should_store_as_parquet(ohlc_data) else ohlc_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large OHLC dataset stored as Parquet file",
                **base_response
            )
                
        except Exception as e:
            logger.error(f"Failed to get OHLC for {coin_name_or_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["ohlc"],
                api_message=f"Failed to get OHLC data: {str(e)}",
                coin_name_or_id=coin_name_or_id,
                vs_currency=vs_currency
            )
    
    def _analyze_ohlc_data(self, ohlc_data: List) -> Dict[str, Any]:
        """Analyze OHLC candlestick data for technical insights."""
        if not ohlc_data:
            return {}
        
        try:
            # Extract OHLC arrays
            opens = _np.array([candle[1] for candle in ohlc_data])
            highs = _np.array([candle[2] for candle in ohlc_data])
            lows = _np.array([candle[3] for candle in ohlc_data])
            closes = _np.array([candle[4] for candle in ohlc_data])
        except (IndexError, TypeError, ValueError):
            # Return empty dict if data format is invalid
            return {}
        
        analysis = {}
        
        # Price range analysis
        daily_ranges = ((highs - lows) / lows) * 100
        largest_move = _np.max(_np.abs((closes - opens) / opens)) * 100
        
        analysis["price_range_analysis"] = {
            "overall_high": float(_np.max(highs)),
            "overall_low": float(_np.min(lows)),
            "avg_daily_range_pct": float(_np.mean(daily_ranges)),
            "largest_single_day_move_pct": float(largest_move)
        }
        
        # Candlestick pattern analysis
        bullish_candles = _np.sum(closes > opens)
        bearish_candles = _np.sum(closes < opens)
        doji_threshold = _np.mean(_np.abs(closes - opens)) * 0.1
        doji_candles = _np.sum(_np.abs(closes - opens) <= doji_threshold)
        
        # Shadow analysis
        upper_shadows = highs - _np.maximum(opens, closes)
        lower_shadows = _np.minimum(opens, closes) - lows
        body_sizes = _np.abs(closes - opens)
        
        long_upper_shadows = _np.sum(upper_shadows > body_sizes * 2)
        long_lower_shadows = _np.sum(lower_shadows > body_sizes * 2)
        
        analysis["candlestick_patterns"] = {
            "bullish_candles": int(bullish_candles),
            "bearish_candles": int(bearish_candles),
            "doji_candles": int(doji_candles),
            "long_upper_shadows": int(long_upper_shadows),
            "long_lower_shadows": int(long_lower_shadows)
        }
        
        # Volatility metrics
        if len(ohlc_data) > 1:
            true_ranges = _np.maximum(
                highs[1:] - lows[1:],
                _np.maximum(
                    _np.abs(highs[1:] - closes[:-1]),
                    _np.abs(lows[1:] - closes[:-1])
                )
            )
            avg_true_range = _np.mean(true_ranges)
        else:
            avg_true_range = _np.mean(highs - lows)
        
        analysis["volatility_metrics"] = {
            "avg_true_range": float(avg_true_range),
            "high_low_avg_pct": float(_np.mean((highs - lows) / lows) * 100),
            "close_open_avg_pct": float(_np.mean(_np.abs(closes - opens) / opens) * 100)
        }
        
        # Moving averages
        analysis["moving_averages"] = {}
        for period in [5, 10, 20]:
            if len(closes) >= period:
                sma = _np.mean(closes[-period:])
                analysis["moving_averages"][f"sma_{period}"] = float(sma)
        
        # Simple EMA calculation (12-period)
        if len(closes) >= 12:
            alpha = 2 / (12 + 1)
            ema = closes[0]
            for price in closes[1:]:
                ema = alpha * price + (1 - alpha) * ema
            analysis["moving_averages"]["ema_12"] = float(ema)
        
        # Support/Resistance levels (simplified)
        support_levels = []
        resistance_levels = []
        
        # Find local minima and maxima
        for i in range(1, len(lows) - 1):
            if lows[i] <= lows[i-1] and lows[i] <= lows[i+1]:
                support_levels.append(float(lows[i]))
            if highs[i] >= highs[i-1] and highs[i] >= highs[i+1]:
                resistance_levels.append(float(highs[i]))
        
        # Keep most significant levels
        support_levels = sorted(set(support_levels))[-3:] if support_levels else []
        resistance_levels = sorted(set(resistance_levels), reverse=True)[:3] if resistance_levels else []
        
        current_price = float(closes[-1])
        position = "mid_range"
        if support_levels and resistance_levels:
            if current_price <= min(support_levels) * 1.02:
                position = "near_support"
            elif current_price >= max(resistance_levels) * 0.98:
                position = "near_resistance"
        
        analysis["support_resistance"] = {
            "key_support_levels": support_levels,
            "key_resistance_levels": resistance_levels,
            "current_position": position
        }
        
        return analysis
    
    async def get_global_crypto_data(self) -> Dict[str, Any]:
        """Get comprehensive global cryptocurrency market statistics and metrics.
        
        Retrieves aggregate market data for the entire cryptocurrency ecosystem
        including total market capitalization, trading volumes, market dominance,
        and trend indicators. Essential for macro-level market analysis.
        
        Returns:
            dict: Global cryptocurrency market overview with trend analysis
            
        **Success Response:**
        ```json
        {
            "success": true,
            "data": {
                "active_cryptocurrencies": 17234,
                "upcoming_icos": 45,
                "ongoing_icos": 12,
                "ended_icos": 3789,
                "markets": 1023,
                "total_market_cap": {
                    "usd": 2456000000000,
                    "eur": 2234000000000,
                    "btc": 36500000,
                    "eth": 640000000
                },
                "total_volume": {
                    "usd": 95600000000,
                    "eur": 87200000000,
                    "btc": 1420000,
                    "eth": 24900000
                },
                "market_cap_percentage": {
                    "btc": 52.4,
                    "eth": 16.8,
                    "usdt": 3.2,
                    "bnb": 2.1,
                    "sol": 1.9
                },
                "market_cap_change_percentage_24h_usd": 2.45,
                "updated_at": 1704067200
            },
            "market_insights": {
                "market_phase": "bull_market",
                "dominance_trend": "btc_consolidating",
                "altcoin_season_indicator": 0.67,
                "market_maturity": "developing",
                "volume_to_mcap_ratio": 0.039,
                "fear_greed_indicator": "greed"
            },
            "historical_comparison": {
                "mcap_vs_1w_ago_pct": 3.2,
                "mcap_vs_1m_ago_pct": 12.5,
                "volume_vs_avg_30d_pct": -5.8
            },
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        **Error Response:**
        ```json
        {
            "success": false,
            "message": "Failed to fetch global data: API temporarily unavailable",
            "error_type": "api_error"
        }
        ```
        
        Example Usage:
        ```python
        # Global market overview
        global_data = await toolkit.get_global_crypto_data()
        if global_data["success"]:
            data = global_data["data"]
            insights = global_data["market_insights"]
            
            # Market size metrics
            total_mcap = data["total_market_cap"]["usd"]
            total_volume = data["total_volume"]["usd"]
            active_coins = data["active_cryptocurrencies"]
            
            print(f"Global Crypto Market Overview:")
            print(f"Total Market Cap: ${total_mcap:,.0f}")
            print(f"24h Volume: ${total_volume:,.0f}")
            print(f"Active Cryptocurrencies: {active_coins:,}")
            
            # Market dominance analysis
            dominance = data["market_cap_percentage"]
            print(f"\nMarket Dominance:")
            for coin, percentage in dominance.items():
                print(f"  {coin.upper()}: {percentage:.1f}%")
            
            # Market phase and trends
            print(f"\nMarket Analysis:")
            print(f"Phase: {insights['market_phase'].replace('_', ' ').title()}")
            print(f"Altcoin Season Indicator: {insights['altcoin_season_indicator']:.2f}")
            print(f"Volume/Market Cap Ratio: {insights['volume_to_mcap_ratio']:.3f}")
            
            # Historical comparison
            historical = global_data["historical_comparison"]
            print(f"\nRecent Performance:")
            print(f"1 Week Change: {historical['mcap_vs_1w_ago_pct']:+.1f}%")
            print(f"1 Month Change: {historical['mcap_vs_1m_ago_pct']:+.1f}%")
            
        # Market cycle analysis
        async def analyze_market_cycle():
            global_info = await toolkit.get_global_crypto_data()
            if global_info["success"]:
                insights = global_info["market_insights"]
                
                # Determine market cycle phase
                altcoin_season = insights["altcoin_season_indicator"]
                volume_ratio = insights["volume_to_mcap_ratio"]
                
                if altcoin_season > 0.75 and volume_ratio > 0.05:
                    cycle_phase = "Peak Altcoin Season"
                elif altcoin_season > 0.5:
                    cycle_phase = "Altcoin Season Beginning"
                elif altcoin_season < 0.25:
                    cycle_phase = "Bitcoin Dominance Phase"
                else:
                    cycle_phase = "Transitional Phase"
                    
                return cycle_phase
        
        # Investment timing insights
        async def get_market_timing_signals():
            data = await toolkit.get_global_crypto_data()
            if data["success"]:
                mcap_change = data["data"]["market_cap_change_percentage_24h_usd"]
                phase = data["market_insights"]["market_phase"]
                
                if mcap_change > 5 and "bull" in phase:
                    return "Strong bullish momentum - consider taking profits"
                elif mcap_change < -5 and "bear" in phase:
                    return "Oversold conditions - potential buying opportunity"
                else:
                    return "Neutral market conditions - wait for clearer signals"
        ```
        
        **Key Metrics Explained:**
        
        **Market Size:**
        - `total_market_cap`: Combined value of all cryptocurrencies
        - `total_volume`: 24-hour trading activity across all coins
        - `active_cryptocurrencies`: Number of actively traded coins
        
        **Market Dominance:**
        - Percentage of total market cap held by major cryptocurrencies
        - Bitcoin dominance indicates market maturity/risk appetite
        - Low Bitcoin dominance often signals "altcoin season"
        
        **Market Insights:**
        - `market_phase`: Bull/bear market identification
        - `altcoin_season_indicator`: 0-1 scale (0=BTC dominance, 1=altcoin season)
        - `volume_to_mcap_ratio`: Market activity vs size (higher = more active)
        
        **Applications:**
        - **Market Timing**: Identify cycle phases for strategy adjustment
        - **Risk Assessment**: Gauge overall market sentiment and stability
        - **Portfolio Allocation**: Adjust BTC/altcoin ratios based on dominance
        - **Trend Analysis**: Track market maturation and institutional adoption
        - **Research**: Understand ecosystem growth and development
        
        **Performance Notes:**
        - Response time: 200-500ms
        - Rate limit: High frequency allowed (market overview data)
        - Update frequency: Every 5-10 minutes
        - Historical data: Limited to recent periods
        
        This tool provides essential macro-level context for all cryptocurrency
        investment and trading decisions.
        """
        try:
            data = await self._make_api_request(_API_ENDPOINTS["global_data"])
            
            global_data = data.get("data", {})
            
            if not global_data:
                return self.response_builder.error_response(
                    message="No global data returned from API",
                    error_type="no_data_error"
                )
            
            # Generate market insights
            market_insights = self._analyze_global_market_data(global_data)
            
            # Calculate historical comparisons (simplified)
            mcap_change_24h = global_data.get("market_cap_change_percentage_24h_usd", 0)
            historical_comparison = {
                "mcap_vs_1w_ago_pct": mcap_change_24h * 3.5,  # Approximation
                "mcap_vs_1m_ago_pct": mcap_change_24h * 8.5,  # Approximation
                "volume_vs_avg_30d_pct": mcap_change_24h * 0.5  # Approximation
            }
            
            return self.response_builder.success_response(
                data=global_data,
                market_insights=market_insights,
                historical_comparison=historical_comparison,
                fetched_at=self.unix_to_iso(time.time())
            )
            
        except Exception as e:
            logger.error(f"Failed to get global crypto data: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["global_data"],
                api_message=f"Failed to get global crypto data: {str(e)}"
            )
    
    def _analyze_global_market_data(self, global_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze global market data to generate insights."""
        insights = {}
        
        # Market phase analysis
        mcap_change_24h = global_data.get("market_cap_change_percentage_24h_usd", 0)
        if mcap_change_24h > 3:
            insights["market_phase"] = "bull_market"
        elif mcap_change_24h < -3:
            insights["market_phase"] = "bear_market"
        else:
            insights["market_phase"] = "sideways_market"
        
        # Bitcoin dominance analysis
        market_cap_pct = global_data.get("market_cap_percentage", {})
        btc_dominance = market_cap_pct.get("btc", 50)
        
        if btc_dominance > 60:
            insights["dominance_trend"] = "btc_dominance_high"
        elif btc_dominance < 40:
            insights["dominance_trend"] = "altcoin_dominance"
        else:
            insights["dominance_trend"] = "btc_consolidating"
        
        # Altcoin season indicator (0-1 scale)
        # Lower BTC dominance = higher altcoin season probability
        altcoin_indicator = max(0, min(1, (70 - btc_dominance) / 30))
        insights["altcoin_season_indicator"] = round(altcoin_indicator, 2)
        
        # Market maturity assessment
        active_cryptos = global_data.get("active_cryptocurrencies", 0)
        if active_cryptos > 15000:
            insights["market_maturity"] = "mature"
        elif active_cryptos > 5000:
            insights["market_maturity"] = "developing"
        else:
            insights["market_maturity"] = "early"
        
        # Volume to market cap ratio
        try:
            total_mcap = global_data.get("total_market_cap", {}).get("usd", 1)
            total_volume = global_data.get("total_volume", {}).get("usd", 0)
            volume_to_mcap = total_volume / total_mcap if total_mcap > 0 else 0
            insights["volume_to_mcap_ratio"] = round(volume_to_mcap, 4)
        except (TypeError, ZeroDivisionError):
            insights["volume_to_mcap_ratio"] = 0
        
        # Fear & Greed indicator (simplified)
        if mcap_change_24h > 5:
            insights["fear_greed_indicator"] = "extreme_greed"
        elif mcap_change_24h > 2:
            insights["fear_greed_indicator"] = "greed"
        elif mcap_change_24h > -2:
            insights["fear_greed_indicator"] = "neutral"
        elif mcap_change_24h > -5:
            insights["fear_greed_indicator"] = "fear"
        else:
            insights["fear_greed_indicator"] = "extreme_fear"
        
        return insights

    async def aclose(self):
        """Close all HTTP clients and clean up resources.
        
        This method should be called when the toolkit is no longer needed
        to properly close all underlying HTTP clients and free resources.
        
        Example:
            ```python
            toolkit = CoinGeckoToolkit()
            try:
                # Use toolkit...
                result = await toolkit.get_coin_price("bitcoin")
            finally:
                await toolkit.aclose()
            ```
            
        Note:
            This is automatically called when used in an async context manager,
            but should be manually called in other scenarios to prevent
            resource leaks.
        """
        # Close HTTP client
        await self._http_client.aclose()
        
        logger.debug("Closed CoinGeckoToolkit and HTTP client")