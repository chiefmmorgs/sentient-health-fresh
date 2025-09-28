from __future__ import annotations

"""Arkham Intelligence Blockchain Analytics Toolkit
=================================================

A comprehensive Agno-compatible toolkit that provides access to Arkham Intelligence's 
blockchain analytics APIs for on-chain intelligence, token analysis, and wallet tracking 
with intelligent data management and LLM-optimized responses.

## Supported Data Types

**Token Analytics**
- Top tokens by various metrics (volume, market cap, holders)
- Token holder analysis and distribution
- Token flow tracking (inflows/outflows)
- Supported blockchain networks and chains

**Transfer Analysis** 
- Transfer data with comprehensive filtering options
- Real-time and historical transaction tracking
- Cross-chain transfer analysis
- Entity-based transfer patterns

**Wallet Intelligence**
- Token balance tracking for specific addresses
- Portfolio analysis across multiple chains
- Entity attribution and labeling
- Address activity monitoring

## Key Features

✅ **Multi-Chain Support**: Ethereum, Bitcoin, BNB Chain, Avalanche, Polygon, Tron
✅ **Smart Data Management**: Large responses automatically stored as Parquet files  
✅ **Entity Intelligence**: Real-world identity mapping via ULTRA AI engine
✅ **LLM-Optimized**: Standardized response formats with clear success/failure indicators
✅ **Async Performance**: Full async/await support with proper resource management
✅ **Framework Integration**: Seamless integration with agent YAML configuration

## Configuration Examples

### Basic Configuration
```yaml
toolkits:
  - name: "ArkhamToolkit"
    params:
      api_key: "${ARKHAM_API_KEY}"
      default_chain: "ethereum"
      data_dir: "./data/arkham"
      parquet_threshold: 1000
    available_tools:
      - "get_top_tokens"
      - "get_token_holders"
      - "get_token_balances"
```

### Advanced Configuration  
```yaml
toolkits:
  - name: "ArkhamToolkit"
    params:
      api_key: "${ARKHAM_API_KEY}"
      default_chain: "ethereum"
      supported_chains: ["ethereum", "bitcoin", "bsc", "avalanche", "polygon"]
      include_entity_data: true
      cache_ttl_seconds: 1800
    available_tools:
      - "get_top_tokens"
      - "get_token_holders" 
      - "get_token_top_flow"
      - "get_supported_chains"
      - "get_transfers"
      - "get_token_balances"
```

## Environment Variables

- `ARKHAM_API_KEY`: Required API key for Arkham Intelligence access
- `ARKHAM_BASE_URL`: Base URL for API endpoints (default: https://api.arkhamintelligence.com)
- `ARKHAM_BIG_DATA_THRESHOLD`: Global threshold for parquet storage (default: 1000)

## Response Format Standards

All tools return consistent JSON structures:

**Success Response:**
```json
{
  "success": true,
  "data": {...},           // Small responses
  "file_path": "...",      // Large responses stored as Parquet
  "chain": "ethereum",
  "fetched_at": "2024-01-01T12:00:00Z"
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Human-readable error description", 
  "error_type": "validation_error|api_error|...",
  "chain": "ethereum"
}
```
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Literal
from enum import Enum

import pandas as _pd
import numpy as _np
from agno.tools import Toolkit
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit, BaseAPIToolkit
from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import (
    StatisticalAnalyzer, DataValidator, FileNameGenerator
)

__all__ = ["ArkhamToolkit", "SupportedChain"]

# Supported blockchain networks
class SupportedChain(str, Enum):
    """Supported blockchain networks for Arkham Intelligence API."""
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    BNB_CHAIN = "bsc"
    AVALANCHE = "avalanche" 
    POLYGON = "polygon"
    TRON = "tron"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"

DEFAULT_BASE_URL = "https://api.arkm.com"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "arkham"
BIG_DATA_THRESHOLD = int(os.getenv("ARKHAM_BIG_DATA_THRESHOLD", "1000"))

# API endpoint mappings - Official Arkham API v1.0.0 (pricing_id endpoints only)
_API_ENDPOINTS = {
    "intelligence": "/intelligence/address/{address}/all",
    "top_tokens": "/token/top",
    "token_holders": "/token/holders/{pricing_id}",
    "token_flow": "/token/top_flow/{pricing_id}",
    "supported_chains": "/chains",
    "transfers": "/transfers",
    "balances": "/balances/address/{address}"
}


class ArkhamAPIError(Exception):
    """Raised when the Arkham Intelligence API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ArkhamToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """Arkham Intelligence Blockchain Analytics Toolkit
    
    A comprehensive toolkit providing access to Arkham Intelligence's blockchain analytics
    platform for on-chain intelligence, token analysis, and wallet tracking. Designed for
    crypto investigators, DeFi analysts, and automated monitoring systems.
    
    **Supported Analytics:**
    - Token holder distribution and top holder analysis
    - Token flow tracking (inflows, outflows, net flows)
    - Cross-chain transfer monitoring and filtering
    - Wallet balance tracking across multiple networks
    - Entity attribution via ULTRA AI engine
    - Real-time blockchain intelligence alerts
    
    **Key Capabilities:**
    - Multi-chain support (Ethereum, Bitcoin, BNB Chain, etc.)
    - Advanced filtering for transfers by amount, time, entities
    - Portfolio analysis with entity mapping
    - Large dataset management via Parquet storage
    - Statistical analysis of token distributions and flows
    - Entity-based transaction pattern analysis
    
    **Data Management:**
    Large responses (>threshold) are automatically stored as Parquet files and the
    file path is returned instead of raw data, optimizing memory usage and enabling
    efficient downstream processing with pandas/polars.
    """

    # Toolkit metadata for enhanced display
    _toolkit_category = "blockchain"
    _toolkit_type = "analytics" 
    _toolkit_icon = "🔍"

    def __init__(
        self,
        api_key: str | None = None,
        default_chain: SupportedChain | str = SupportedChain.ETHEREUM,
        base_url: str = DEFAULT_BASE_URL,
        supported_chains: Optional[Sequence[str]] = None,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        parquet_threshold: int = BIG_DATA_THRESHOLD,
        include_entity_data: bool = True,
        cache_ttl_seconds: int = 1800,
        name: str = "arkham_toolkit",
        **kwargs: Any,
    ):
        """Initialize the Arkham Intelligence Analytics Toolkit.
        
        Args:
            api_key: Arkham Intelligence API key. If None, reads from ARKHAM_API_KEY 
                    environment variable. Required for all endpoints.
            default_chain: Default blockchain network for queries.
                          Options: "ethereum", "bitcoin", "bsc", "avalanche", etc.
            base_url: Base URL for Arkham Intelligence API endpoints.
                     Default: https://api.arkhamintelligence.com
            supported_chains: List of blockchain networks to support. If None,
                            all supported chains are allowed.
            data_dir: Directory path where Parquet files will be stored for large
                     responses. Defaults to tools/data/arkham/
            parquet_threshold: Size threshold in KB for Parquet storage.
                             Responses with JSON payload > threshold KB will be
                             saved to disk and file path returned instead of data.
                             Recommended: 10-50 KB for on-chain data.
            include_entity_data: Include entity attribution data when available
            cache_ttl_seconds: Cache time-to-live for API responses in seconds
            name: Name identifier for this toolkit instance
            **kwargs: Additional arguments passed to Toolkit
            
        Raises:
            ValueError: If default_chain is not supported or API key is missing
            
        Example:
            ```python
            # Basic blockchain analytics toolkit
            toolkit = ArkhamToolkit(
                api_key="your_arkham_api_key",
                default_chain="ethereum"
            )
            
            # Get top tokens by market cap
            top_tokens = await toolkit.get_top_tokens(limit=50)
            
            # Analyze token holder distribution
            holders = await toolkit.get_token_holders("0x...", limit=100)
            
            # Track wallet balances
            balances = await toolkit.get_token_balances("0x...")
            ```
        """
        # Use base class validation for configuration
        self._validate_configuration_enum(default_chain, SupportedChain, "default_chain")
        
        # Convert string to enum if needed
        if isinstance(default_chain, str):
            found_enum = None
            for member in SupportedChain:
                if member.value == default_chain.lower():
                    found_enum = member
                    break
            
            if found_enum is None:
                raise ValueError(f"Invalid default_chain: {default_chain}")
            self.default_chain = found_enum
        else:
            self.default_chain = default_chain
            
        # API key is required for Arkham Intelligence
        self._api_key = api_key or os.getenv("ARKHAM_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Arkham API key is required. Set ARKHAM_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.base_url = base_url
        self.include_entity_data = include_entity_data
        
        # Chain management
        if supported_chains:
            self._supported_chains = {
                chain.lower() for chain in supported_chains 
                if chain.lower() in [c.value for c in SupportedChain]
            }
        else:
            self._supported_chains = {c.value for c in SupportedChain}
        
        # Initialize standard configuration (includes cache system and HTTP client)
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=cache_ttl_seconds
        )
        
        # Define available tools for this toolkit (pricing_id based endpoints)
        available_tools = [
            self.get_top_tokens,
            self.get_token_holders,  # Uses pricing_id
            self.get_token_top_flow,  # Uses pricing_id
            self.get_supported_chains,
            self.get_transfers,
            self.get_token_balances,  # Uses address
        ]
        
        # Initialize Toolkit
        super().__init__(name=name, tools=available_tools, **kwargs)
        
        # Initialize BaseDataToolkit helpers  
        self._init_data_helpers(
            data_dir=data_dir,
            parquet_threshold=parquet_threshold,
            file_prefix="arkham_",
            toolkit_name="arkham",
        )
        
        # Initialize statistical analyzer
        self.stats = StatisticalAnalyzer()
        
        logger.debug(
            f"Initialized ArkhamToolkit with default chain '{self.default_chain.value}' "
            f"and {len(self._supported_chains)} supported chains"
        )

    def _build_arkham_auth_headers(self, endpoint_name: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Build authentication headers for Arkham Intelligence endpoints.
        
        According to the official API docs, all requests must include the API-Key header.
        """
        # Parameters kept for interface compatibility with BaseAPIToolkit
        _ = endpoint_name, config  # Acknowledge parameters
        return {
            "API-Key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _setup_endpoints(self):
        """Setup HTTP endpoints for Arkham Intelligence API."""
        # Setup standard endpoint (20 req/sec)
        await self._http_client.add_endpoint(
            name="arkham",
            base_url=self.base_url,
            headers=self._build_arkham_auth_headers("arkham", {}),
            timeout=30.0,
            rate_limit=0.05,  # 20 req/sec = 0.05 second minimum between requests
        )
        
        # Setup heavy endpoint (1 req/sec rate limit)
        await self._http_client.add_endpoint(
            name="arkham_heavy",
            base_url=self.base_url,
            headers=self._build_arkham_auth_headers("arkham_heavy", {}),
            timeout=30.0,
            rate_limit=1.0,  # 1 req/sec = 1 second minimum between requests
        )

    async def _make_api_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        method: str = "GET",
        use_heavy_endpoint: bool = False
    ) -> Dict[str, Any]:
        """Make API request to Arkham Intelligence endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters or request body
            method: HTTP method (GET, POST, etc.)
            use_heavy_endpoint: Whether to use heavy endpoint (1 req/sec rate limit)
            
        Returns:
            dict: Raw JSON response from API
        """
        # Ensure endpoints are setup
        if "arkham" not in self._http_client.get_endpoints():
            await self._setup_endpoints()
        
        # Choose endpoint based on rate limiting requirements
        endpoint_name = "arkham_heavy" if use_heavy_endpoint else "arkham"
        
        # Use HTTP client directly
        if method.upper() == "GET":
            return await self._http_client.get(endpoint_name, endpoint, params=params)
        elif method.upper() == "POST":
            return await self._http_client.post(endpoint_name, endpoint, json=params)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def _validate_chain(self, chain: str) -> str:
        """Validate and normalize chain parameter.
        
        Args:
            chain: Chain identifier to validate
            
        Returns:
            str: Normalized chain identifier
            
        Raises:
            ValueError: If chain is not supported
        """
        chain_lower = chain.lower()
        if chain_lower not in self._supported_chains:
            supported_list = list(self._supported_chains)
            raise ValueError(f"Unsupported chain '{chain}'. Supported: {supported_list}")
        return chain_lower

    def _validate_address(self, address: str) -> str:
        """Validate blockchain address format using DataValidator.
        
        Args:
            address: Address to validate
            
        Returns:
            str: Normalized address
            
        Raises:
            ValueError: If address format is invalid
        """
        if not address or not isinstance(address, str):
            raise ValueError("Address must be a non-empty string")
        
        address = address.strip()
        if not address:
            raise ValueError("Address cannot be empty")
        
        # Use base validation first
        validation_result = DataValidator.validate_structure(
            address, 
            expected_type=str
        )
        
        if not validation_result["valid"]:
            raise ValueError(f"Address validation failed: {validation_result['errors']}")
        
        # Blockchain-specific validation
        if address.startswith("0x") and len(address) == 42:
            # Ethereum-style address - validate hex format
            try:
                int(address[2:], 16)  # Validate it's valid hex
                return address.lower()
            except ValueError:
                raise ValueError(f"Invalid Ethereum address format: {address}")
        elif len(address) >= 26 and len(address) <= 35:
            # Bitcoin-style address - basic length validation
            return address
        else:
            # For other formats, return as-is but log warning
            logger.warning(f"Address format not recognized, proceeding: {address}")
            return address

    # =========================================================================
    # Token-Related Tools
    # =========================================================================
    
    async def get_top_tokens(
        self,
        timeframe: str = "24h",
        order_by_agg: str = "volume", 
        order_by_desc: bool = True,
        order_by_percent: bool = False,
        from_index: int = 0,
        size: int = 10,
        chains: Optional[str] = None,
        min_volume: Optional[float] = None,
        max_volume: Optional[float] = None,
        min_market_cap: Optional[float] = None,
        max_market_cap: Optional[float] = None,
        num_reference_periods: str = "auto",
        token_ids: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get top tokens by various metrics with optional filtering.
        
        Retrieves the highest-ranking tokens based on specified criteria such as
        volume, market cap, inflows, outflows, and other metrics. Essential for market
        analysis, token discovery, and trend identification.
        
        Args:
            timeframe: Time interval for token data. Options: "1h", "6h", "12h", "24h", "7d"
            order_by_agg: Aggregation field to order tokens by. Options:
                         "volume", "inflow", "outflow", "volumeDex", "volumeCex", 
                         "inflowDex", "inflowCex", "outflowDex", "outflowCex", 
                         "netflowDex", "netflowCex", "netflow", "price"
            order_by_desc: Sort descending (True) or ascending (False)
            order_by_percent: Whether to order results by percentage change
            from_index: Starting index for pagination (default: 0)
            size: Number of results to return (default: 10)
            chains: Comma-separated list of chains (e.g., "ethereum,bsc")
            min_volume: Minimum trading volume filter
            max_volume: Maximum trading volume filter
            min_market_cap: Minimum market capitalization filter
            max_market_cap: Maximum market capitalization filter
                        
        Returns:
            dict: Top tokens data or file path for large responses
            
        **Success Response (Small Dataset):**
        ```json
        {
            "success": true,
            "data": [
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
            ],
            "limit": 50,
            "sort_by": "market_cap",
            "chain": "ethereum",
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Get top 100 tokens by market cap
        top_tokens = await toolkit.get_top_tokens(limit=100, sort_by="market_cap")
        
        # Get most traded tokens in last 24h
        volume_leaders = await toolkit.get_top_tokens(
            limit=25, 
            sort_by="volume", 
            time_period="24h"
        )
        
        # Analyze token distribution
        if top_tokens["success"]:
            if "data" in top_tokens:
                for token in top_tokens["data"][:10]:
                    print(f"{token['symbol']}: ${token['market_cap']:,.0f}")
        ```
        """
        try:
            # Validate parameters according to actual API
            valid_timeframes = ["1h", "6h", "12h", "24h", "7d"]
            if timeframe not in valid_timeframes:
                raise ValueError(f"Invalid timeframe. Options: {valid_timeframes}")
                
            valid_order_by = [
                "volume", "inflow", "outflow", "volumeDex", "volumeCex", "inflowDex", 
                "inflowCex", "outflowDex", "outflowCex", "netflowDex", "netflowCex", 
                "netflow", "netflowVolumeRatio", "netflowVolumeRatioDex", 
                "netflowVolumeRatioCex", "price"
            ]
            if order_by_agg not in valid_order_by:
                raise ValueError(f"Invalid order_by_agg. Options: {valid_order_by}")
            
            if size <= 0:
                raise ValueError("Size must be greater than 0")
            if from_index < 0:
                raise ValueError("from_index must be non-negative")
            
            # Prepare API request parameters according to actual API spec
            api_params = {
                "timeframe": timeframe,
                "orderByAgg": order_by_agg,
                "orderByDesc": "true" if order_by_desc else "false",  # API expects string
                "orderByPercent": "true" if order_by_percent else "false",  # API expects string
                "from": from_index,
                "size": size,
                "numReferencePeriods": num_reference_periods
            }
            
            # Add optional parameters
            if chains:
                api_params["chains"] = chains
            if min_volume is not None:
                api_params["minVolume"] = min_volume
            if max_volume is not None:
                api_params["maxVolume"] = max_volume
            if min_market_cap is not None:
                api_params["minMarketCap"] = min_market_cap
            if max_market_cap is not None:
                api_params["maxMarketCap"] = max_market_cap
            if token_ids:
                api_params["tokenIds"] = token_ids
            
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["top_tokens"], api_params)
            
            # Validate response structure using DataValidator
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=(list, dict)
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            # Handle response format according to API spec
            if isinstance(data, dict) and "tokens" in data:
                tokens_list = data["tokens"]
                # CRITICAL FIX: Handle case where tokens_list could be None
                if tokens_list is None:
                    tokens_list = []
                total_count = data.get("total", len(tokens_list))
            elif isinstance(data, list):
                tokens_list = data or []  # Handle case where data could be None
                total_count = len(tokens_list)
            else:
                tokens_list = []
                total_count = 0
            
            base_response = {
                "success": True,
                "timeframe": timeframe,
                "order_by_agg": order_by_agg,
                "order_by_desc": order_by_desc,
                "from_index": from_index,
                "size": size,
                "count": len(tokens_list),
                "total": total_count,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Add analysis for token data using actual API response structure
            analysis = {}
            if tokens_list:
                try:
                    # Extract data based on actual API response structure from docs
                    # API response: {tokens: [{token: {id, symbol, marketCap}, current: {price, *Volume}, previous: {...}}]}
                    market_caps = []
                    current_prices = []
                    volumes = []
                    
                    for token in tokens_list:
                        try:
                            # API returns nested structure with token info and current/previous data
                            token_info = token.get("token", {})
                            current_data = token.get("current", {})
                            
                            # Extract market cap from token info
                            if token_info.get("marketCap") is not None:
                                market_caps.append(float(token_info["marketCap"]))
                            
                            # Extract current price
                            if current_data.get("price") is not None:
                                current_prices.append(float(current_data["price"]))
                            
                            # Calculate total volume from available volume fields
                            volume_fields = ["inflowDexVolume", "outflowDexVolume", "inflowCexVolume", "outflowCexVolume"]
                            total_volume = sum(float(current_data.get(field, 0)) for field in volume_fields if current_data.get(field) is not None)
                            
                            if total_volume > 0:
                                volumes.append(total_volume)
                                
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse token data: {e}")
                            continue
                    
                    # Use StatisticalAnalyzer for proper statistical calculations
                    if market_caps:
                        mcap_array = _np.array(market_caps)
                        mcap_stats = self.stats.calculate_distribution_stats(mcap_array)
                        total_market_cap = sum(market_caps)
                        
                        analysis.update({
                            "total_market_cap": total_market_cap,
                            "market_cap_distribution": mcap_stats,
                            "market_concentration_gini": mcap_stats.get("gini_coefficient", 0),
                            "top_token_dominance_pct": (max(market_caps) / total_market_cap * 100) if total_market_cap > 0 else 0
                        })
                    
                    if volumes:
                        volume_array = _np.array(volumes)
                        volume_stats = self.stats.calculate_distribution_stats(volume_array)
                        
                        analysis.update({
                            "total_volume": sum(volumes),
                            "volume_distribution": volume_stats
                        })
                    
                    if current_prices:
                        price_array = _np.array(current_prices)
                        price_stats = self.stats.calculate_price_statistics(price_array)
                        
                        analysis.update({
                            "price_statistics": price_stats
                        })
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate token analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "top_tokens", timeframe, order_by_agg, {"size": size, "from": from_index},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=tokens_list,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large token dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get top tokens: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["top_tokens"],
                api_message=f"Failed to get top tokens: {str(e)}",
                timeframe=timeframe,
                order_by_agg=order_by_agg,
                size=size
            )

    async def get_token_holders(
        self,
        pricing_id: str,
        group_by_entity: bool = False
    ) -> Dict[str, Any]:
        """Get token holder distribution for a specific token by CoinGecko pricing ID.
        
        Retrieves the addresses holding the specified token, along with their
        balance amounts and percentages. Essential for analyzing token distribution,
        whale activity, and ownership concentration.
        
        Args:
            pricing_id: CoinGecko pricing ID for the token (e.g., "bitcoin", "ethereum", "usd-coin")
            group_by_entity: If true, group results by entity (default: False)
                  
        Returns:
            dict: Token holders data or file path for large responses
            
        **Success Response:**
        ```json
        {
            "success": true,
            "data": [
                {
                    "address": "0x...",
                    "balance": "1000000.5",
                    "balance_usd": 2000000.0,
                    "percentage": 5.25,
                    "entity_name": "Binance Hot Wallet",
                    "entity_type": "exchange",
                    "rank": 1
                }
            ],
            "token_address": "0x...",
            "total_holders": 45678,
            "total_supply": "21000000.0",
            "analysis": {
                "top_10_concentration": 65.5,
                "whale_holders": 12,
                "distribution_score": "concentrated"
            }
        }
        ```
        
        Example Usage:
        ```python
        # Analyze USDC holder distribution
        usdc_holders = await toolkit.get_token_holders(
            "0xa0b86a33e6441b7e946a8ed1a30e1a49c5f6b92b",
            limit=500
        )
        
        # Focus on large holders only  
        whale_holders = await toolkit.get_token_holders(
            "0x...",
            limit=50,
            min_balance=1000000  # 1M tokens minimum
        )
        ```
        """
        try:
            # Validate parameters
            if not pricing_id or not isinstance(pricing_id, str):
                raise ValueError("pricing_id must be a non-empty string")
            
            pricing_id = pricing_id.strip().lower()
            if not pricing_id:
                raise ValueError("pricing_id cannot be empty")
            
            # Prepare API request parameters according to actual API spec
            api_params = {}
            
            if group_by_entity:
                api_params["groupByEntity"] = group_by_entity
            
            # Make API request using centralized endpoint mapping
            endpoint = _API_ENDPOINTS["token_holders"].format(pricing_id=pricing_id)
            data = await self._make_api_request(endpoint, api_params)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(data, expected_type=(list, dict))
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            # Handle response format - API returns holder data nested by chain
            if isinstance(data, list):
                holders_list = data
                token_info = {}
            elif isinstance(data, dict):
                # Handle actual API response structure based on debug logs
                holders_list = []
                token_info = {}
                
                # Check for the actual response structure: addressTopHolders/entityTopHolders
                if "addressTopHolders" in data or "entityTopHolders" in data:
                    # Extract holders from addressTopHolders and entityTopHolders
                    if "addressTopHolders" in data:
                        address_holders = data["addressTopHolders"]
                        if isinstance(address_holders, list):
                            holders_list.extend(address_holders)
                        elif isinstance(address_holders, dict):
                            # If nested by chain, flatten
                            for chain_holders in address_holders.values():
                                if isinstance(chain_holders, list):
                                    holders_list.extend(chain_holders)
                    
                    if "entityTopHolders" in data:
                        entity_holders = data["entityTopHolders"]
                        if isinstance(entity_holders, list):
                            holders_list.extend(entity_holders)
                        elif isinstance(entity_holders, dict):
                            # If nested by chain, flatten
                            for chain_holders in entity_holders.values():
                                if isinstance(chain_holders, list):
                                    holders_list.extend(chain_holders)
                    
                    # Store token info and other metadata
                    token_info = {k: v for k, v in data.items() if k not in ["addressTopHolders", "entityTopHolders"]}
                
                # Fallback: check for "holders" key (documentation format)
                elif "holders" in data:
                    holders_dict = data["holders"]
                    if isinstance(holders_dict, dict):
                        # Flatten all holders from all chains into a single list
                        for chain, chain_holders in holders_dict.items():
                            if isinstance(chain_holders, list):
                                holders_list.extend(chain_holders)
                    else:
                        # Direct list format
                        holders_list = holders_dict if isinstance(holders_dict, list) else []
                    token_info = {k: v for k, v in data.items() if k != "holders"}
                
                # Final fallback: single holder object or other format
                else:
                    holders_list = [data] if data else []
                    token_info = {}
            else:
                holders_list = []
                token_info = {}
            
            # Debug logging for response structure understanding
            logger.debug(f"Parsed holders list length: {len(holders_list) if holders_list else 0}")
            if holders_list and len(holders_list) > 0:
                first_holder = holders_list[0]
                logger.debug(f"First holder structure: {type(first_holder).__name__} with keys: {list(first_holder.keys()) if isinstance(first_holder, dict) else 'not a dict'}")
            
            base_response = {
                "success": True,
                "pricing_id": pricing_id,
                "group_by_entity": group_by_entity,
                "count": len(holders_list),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time()),
                **token_info
            }
            
            # Calculate holder distribution analysis using DataValidator
            analysis = {}
            if holders_list:
                try:
                    # Validate holder data structure first - based on actual API response from Firecrawl docs
                    # Arkham API returns holders with fields: address, balance, usd, pctOfCap
                    holder_validation = DataValidator.validate_structure(
                        holders_list,
                        required_fields=["balance"],  # Only balance is guaranteed, percentage fields vary
                        expected_type=list
                    )
                    
                    if holder_validation["valid"]:
                        balances = []
                        percentages = []
                        
                        for holder in holders_list:
                            try:
                                # Extract balance - based on Arkham API docs: balance, balanceExact, amount, usd
                                balance_fields = ["balance", "balanceExact", "amount", "usd"]
                                for field in balance_fields:
                                    if field in holder and holder[field] is not None:
                                        balances.append(float(holder[field]))
                                        break
                                
                                # Extract percentage - based on Arkham API docs: pctOfCap, percentage, or percent
                                percentage_fields = ["pctOfCap", "percentage", "percent"]
                                for pct_field in percentage_fields:
                                    if pct_field in holder and holder[pct_field] is not None:
                                        percentages.append(float(holder[pct_field]))
                                        break
                                    
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Failed to parse holder data: {e}")
                                continue
                        
                        if percentages:
                            # Validate percentage array
                            pct_array_validation = DataValidator.validate_numeric_data(percentages)
                            if pct_array_validation["valid"]:
                                # Calculate concentration metrics using StatisticalAnalyzer
                                top_10_pct = sum(percentages[:10]) if len(percentages) >= 10 else sum(percentages)
                                whale_count = sum(1 for p in percentages if p >= 1.0)  # Holders with 1%+ of supply
                                
                                # Use StatisticalAnalyzer for distribution analysis
                                balance_distribution = {}
                                percentage_distribution = {}
                                
                                if balances:
                                    balance_array = _np.array(balances)
                                    balance_distribution = self.stats.calculate_distribution_stats(balance_array)
                                
                                if percentages:
                                    percentage_array = _np.array(percentages)
                                    percentage_distribution = self.stats.calculate_distribution_stats(percentage_array)
                                
                                analysis = {
                                    "top_10_concentration": top_10_pct,
                                    "whale_holders": whale_count,
                                    "distribution_score": (
                                        "highly_concentrated" if top_10_pct > 80 else
                                        "concentrated" if top_10_pct > 50 else
                                        "moderate" if top_10_pct > 25 else
                                        "distributed"
                                    ),
                                    "balance_distribution": balance_distribution,
                                    "percentage_distribution": percentage_distribution,
                                    "holder_data_validation": holder_validation,
                                    "percentage_validation": pct_array_validation
                                }
                    else:
                        logger.warning(f"Holder data structure validation failed: {holder_validation['errors']}")
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate holder analysis: {e}")
            
            filename_template = FileNameGenerator.generate_data_filename(
                "token_holders", pricing_id, "pricing_id", {"group_by_entity": group_by_entity},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=holders_list,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large holder dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get token holders for {pricing_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["token_holders"],
                api_message=f"Failed to get token holders: {str(e)}",
                pricing_id=pricing_id
            )

    async def get_token_top_flow(
        self,
        pricing_id: str,
        time_last: str = "24h",
        chains: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get top token flows (inflows and outflows) for a specific token by pricing ID.
        
        Retrieves the largest token movements (inflows, outflows, net flows) for
        analysis of whale activity, exchange flows, and major token transfers.
        
        Args:
            pricing_id: CoinGecko pricing ID for the token (e.g., "bitcoin", "ethereum")
            time_last: Duration string for time window (e.g., "24h", "7d")
            chains: Optional comma-separated list of chains to filter results
                  
        Returns:
            dict: Token flow data or file path for large responses
        """
        try:
            # Validate parameters
            if not pricing_id or not isinstance(pricing_id, str):
                raise ValueError("pricing_id must be a non-empty string")
            
            pricing_id = pricing_id.strip().lower()
            if not pricing_id:
                raise ValueError("pricing_id cannot be empty")
            
            if not time_last or not isinstance(time_last, str):
                raise ValueError("time_last must be a non-empty string")
            
            # Prepare API request according to actual API spec
            api_params = {
                "timeLast": time_last,
                "id": pricing_id
            }
            
            if chains:
                api_params["chains"] = chains
            
            endpoint = _API_ENDPOINTS["token_flow"].format(pricing_id=pricing_id)
            # Use heavy endpoint since /token/top_flow/{id} has 1 req/sec rate limit
            data = await self._make_api_request(endpoint, api_params, use_heavy_endpoint=True)
            
            # Handle response format - API returns array of TopFlowItem objects
            # Based on API docs: [{address: {}, inUSD: float, outUSD: float, inValue: float, outValue: float, time: string}]
            if isinstance(data, list):
                flows_list = data
            elif isinstance(data, dict):
                # Handle wrapped response or single flow item
                if "flows" in data:
                    flows_list = data["flows"]
                elif "data" in data:
                    flows_list = data["data"] if isinstance(data["data"], list) else [data["data"]]
                else:
                    flows_list = [data] if data else []
            else:
                flows_list = []
            
            base_response = {
                "success": True,
                "pricing_id": pricing_id,
                "time_last": time_last,
                "chains": chains,
                "count": len(flows_list),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Essential flow analysis for LLM interpretation
            analysis = {}
            if flows_list:
                try:
                    # Extract flow data from TopFlowItem objects
                    # API fields: inUSD, outUSD, inValue, outValue per flow item
                    in_usd_values = []
                    out_usd_values = []
                    
                    for flow in flows_list:
                        try:
                            if flow.get("inUSD") is not None:
                                in_usd_values.append(float(flow["inUSD"]))
                            if flow.get("outUSD") is not None:
                                out_usd_values.append(float(flow["outUSD"]))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse flow data: {e}")
                            continue
                    
                    total_in = sum(in_usd_values)
                    total_out = sum(out_usd_values)
                    net_flow = total_in - total_out
                    
                    analysis = {
                        "flow_summary": {
                            "total_inflow_usd": round(total_in, 2),
                            "total_outflow_usd": round(total_out, 2),
                            "net_flow_usd": round(net_flow, 2),
                            "flow_direction": "net_inflow" if net_flow > 0 else "net_outflow" if net_flow < 0 else "balanced",
                            "flow_intensity": round(abs(net_flow) / max(total_in, total_out) * 100, 1) if max(total_in, total_out) > 0 else 0
                        },
                        "flow_distribution": {
                            "address_count": len(flows_list),
                            "largest_inflow_usd": round(max(in_usd_values), 2) if in_usd_values else 0,
                            "largest_outflow_usd": round(max(out_usd_values), 2) if out_usd_values else 0
                        }
                    }
                    
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate flow analysis: {e}")
            
            filename_template = FileNameGenerator.generate_data_filename(
                "token_flows", pricing_id, "pricing_id", 
                {"time_last": time_last, "chains": chains or "all"},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=flows_list,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large flow dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get token flows for {pricing_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["token_flow"],
                api_message=f"Failed to get token flows: {str(e)}",
                pricing_id=pricing_id
            )

    async def get_supported_chains(self) -> Dict[str, Any]:
        """Get the list of supported blockchain networks.
        
        Retrieves all blockchain networks supported by the Arkham Intelligence API
        for token analysis, transfer tracking, and wallet monitoring.
        
        Returns:
            dict: Supported chains data
            
        **Success Response:**
        ```json
        {
            "success": true,
            "data": [
                {
                    "chain_id": "ethereum",
                    "name": "Ethereum",
                    "native_token": "ETH",
                    "block_explorer": "https://etherscan.io",
                    "supported_features": ["tokens", "transfers", "entities"]
                }
            ],
            "count": 8,
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        """
        try:
            # Check cache first
            cache_key = "supported_chains"
            cached_chains = self._get_cached_data(cache_key)
            
            if cached_chains is not None:
                return self.response_builder.success_response(
                    data=cached_chains,
                    count=len(cached_chains),
                    fetched_at=BaseAPIToolkit.unix_to_iso(time.time()),
                    source="cache"
                )
            
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["supported_chains"])
            
            # Handle response format
            if isinstance(data, dict) and "chains" in data:
                chains_list = data["chains"]
            elif isinstance(data, list):
                chains_list = data
            else:
                chains_list = []
            
            # Cache the results
            self._cache_data(cache_key, chains_list, {"fetched_at": time.time()})
            
            return self.response_builder.success_response(
                data=chains_list,
                count=len(chains_list),
                fetched_at=BaseAPIToolkit.unix_to_iso(time.time())
            )
            
        except Exception as e:
            logger.error(f"Failed to get supported chains: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["supported_chains"],
                api_message=f"Failed to get supported chains: {str(e)}"
            )

    # =========================================================================
    # Transfer-Related Tools
    # =========================================================================
    
    async def get_transfers(
        self,
        base: Optional[str] = None,
        chains: Optional[str] = None,
        flow: Optional[str] = None,
        from_addresses: Optional[str] = None,
        to_addresses: Optional[str] = None,
        tokens: Optional[str] = None,
        counterparties: Optional[str] = None,
        time_last: Optional[str] = None,
        time_gte: Optional[str] = None,
        time_lte: Optional[str] = None,
        value_gte: Optional[float] = None,
        value_lte: Optional[float] = None,
        usd_gte: Optional[float] = None,
        usd_lte: Optional[float] = None,
        sort_key: Optional[str] = None,
        sort_dir: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get transfers based on various filtering criteria.
        
        Retrieves blockchain transfers with comprehensive filtering options for
        analyzing transaction patterns, whale movements, and token flows.
        
        Note: This endpoint has a rate limit of 1 request per second.
        
        Args:
            base: Filter by specific entity or address (e.g., "0x123abc" or "binance")
            chains: Comma-separated list of chains (e.g., "ethereum,bsc")
            flow: Transfer direction - "in", "out", "self", or "all"
            from_addresses: Comma-separated list of addresses/entities for 'from' side
            to_addresses: Comma-separated list of addresses/entities for 'to' side
            tokens: Comma-separated list of token addresses or IDs
            counterparties: Comma-separated list of counterparty addresses/entities
            time_last: Recent duration filter (e.g., "24h", "7d")
            time_gte: Filter from timestamp in milliseconds
            time_lte: Filter to timestamp in milliseconds
            value_gte: Minimum raw token value (on-chain units)
            value_lte: Maximum raw token value (on-chain units)
            usd_gte: Minimum historical USD value
            usd_lte: Maximum historical USD value
            sort_key: Sort field - "time", "value", or "usd"
            sort_dir: Sort direction - "asc" or "desc"
            limit: Maximum results to return (default: 50)
            offset: Pagination offset (default: 0)
                  
        Returns:
            dict: Transfer data or file path for large responses
        """
        try:
            # Validate parameters according to actual API spec
            if limit <= 0:
                raise ValueError("Limit must be greater than 0")
            if offset < 0:
                raise ValueError("Offset must be non-negative")
                
            # Validate flow direction if provided
            if flow and flow not in ["in", "out", "self", "all"]:
                raise ValueError("flow must be one of: in, out, self, all")
            
            # Validate sort parameters
            if sort_key and sort_key not in ["time", "value", "usd"]:
                raise ValueError("sort_key must be one of: time, value, usd")
            if sort_dir and sort_dir not in ["asc", "desc"]:
                raise ValueError("sort_dir must be one of: asc, desc")
            
            # Validate value ranges
            if value_gte is not None and value_lte is not None and value_gte > value_lte:
                raise ValueError("value_gte cannot be greater than value_lte")
            if usd_gte is not None and usd_lte is not None and usd_gte > usd_lte:
                raise ValueError("usd_gte cannot be greater than usd_lte")
            
            # Prepare API request parameters according to actual API spec
            api_params = {
                "limit": limit,
                "offset": offset
            }
            
            # Add optional filters - use correct API parameter names
            if base:
                api_params["base"] = base
            if chains:
                api_params["chains"] = chains
            if flow:
                api_params["flow"] = flow
            if from_addresses:
                api_params["from"] = from_addresses  # ✅ Correct: API expects "from"
            if to_addresses:
                api_params["to"] = to_addresses  # ✅ Correct: API expects "to"
            if tokens:
                api_params["tokens"] = tokens
            if counterparties:
                api_params["counterparties"] = counterparties
            if time_last:
                api_params["timeLast"] = time_last  # ✅ Correct: API expects "timeLast"
            if time_gte:
                api_params["timeGte"] = time_gte  # ✅ Correct: API expects "timeGte"
            if time_lte:
                api_params["timeLte"] = time_lte  # ✅ Correct: API expects "timeLte"
            if value_gte is not None:
                api_params["valueGte"] = value_gte  # ✅ Correct: API expects "valueGte"
            if value_lte is not None:
                api_params["valueLte"] = value_lte  # ✅ Correct: API expects "valueLte"
            if usd_gte is not None:
                api_params["usdGte"] = usd_gte  # ✅ Correct: API expects "usdGte"
            if usd_lte is not None:
                api_params["usdLte"] = usd_lte  # ✅ Correct: API expects "usdLte"
            if sort_key:
                api_params["sortKey"] = sort_key  # ✅ Correct: API expects "sortKey"
            if sort_dir:
                api_params["sortDir"] = sort_dir  # ✅ Correct: API expects "sortDir"
            
            # Make API request - use heavy endpoint since /transfers has 1 req/sec rate limit  
            data = await self._make_api_request(_API_ENDPOINTS["transfers"], api_params, use_heavy_endpoint=True)
            
            # Handle response format according to API spec
            if isinstance(data, dict) and "transfers" in data:
                transfers_list = data["transfers"]
                # CRITICAL FIX: Handle case where transfers_list could be None
                if transfers_list is None:
                    transfers_list = []
                total_count = data.get("count", len(transfers_list))
                transfer_summary = {k: v for k, v in data.items() if k not in ["transfers", "count"]}
            elif isinstance(data, list):
                transfers_list = data or []  # Handle case where data could be None
                total_count = len(transfers_list)
                transfer_summary = {}
            else:
                transfers_list = []
                total_count = 0
                transfer_summary = {}
            
            base_response = {
                "success": True,
                "limit": limit,
                "offset": offset,
                "count": len(transfers_list),
                "total_count": total_count,
                "filters": {k: v for k, v in api_params.items() if k not in ["limit", "offset"]},
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time()),
                **transfer_summary
            }
            
            # Calculate transfer analysis based on actual API response structure
            analysis = {}
            if transfers_list:
                try:
                    # Extract USD values from transfer data - API uses "historicalUSD" field
                    usd_values = []
                    
                    for transfer in transfers_list:
                        try:
                            # API response uses "historicalUSD" field according to docs
                            if "historicalUSD" in transfer and transfer["historicalUSD"] is not None:
                                usd_values.append(float(transfer["historicalUSD"]))
                        except (ValueError, TypeError):
                            continue
                    
                    # Extract unique addresses and tokens
                    # Extract token addresses - handle different field names
                    unique_tokens = set()
                    for t in transfers_list:
                        token_addr = t.get("tokenAddress") or t.get("token_address") or t.get("token")
                        if token_addr:
                            unique_tokens.add(token_addr)
                    unique_senders = set()
                    unique_receivers = set()
                    
                    for t in transfers_list:
                        try:
                            # Handle nested address objects or direct address fields
                            from_addr = None
                            to_addr = None
                            
                            if isinstance(t.get("fromAddress"), dict):
                                from_addr = t["fromAddress"].get("address")
                            elif isinstance(t.get("fromAddress"), str):
                                from_addr = t["fromAddress"]
                            elif t.get("from"):
                                from_addr = t["from"]
                                
                            if isinstance(t.get("toAddress"), dict):
                                to_addr = t["toAddress"].get("address")
                            elif isinstance(t.get("toAddress"), str):
                                to_addr = t["toAddress"]
                            elif t.get("to"):
                                to_addr = t["to"]
                                
                            if from_addr:
                                unique_senders.add(from_addr)
                            if to_addr:
                                unique_receivers.add(to_addr)
                                
                        except (KeyError, TypeError) as e:
                            logger.warning(f"Failed to extract address from transfer: {e}")
                            continue
                    
                    if usd_values:
                        # Use StatisticalAnalyzer for comprehensive transfer value analysis
                        usd_array = _np.array(usd_values)
                        usd_distribution = self.stats.calculate_distribution_stats(usd_array)
                        
                        analysis = {
                            "total_usd_value": sum(usd_values),
                            "usd_value_distribution": usd_distribution,
                            "unique_tokens": len(unique_tokens),
                            "unique_senders": len(unique_senders),
                            "unique_receivers": len(unique_receivers),
                            "total_transfers": len(transfers_list),
                            "transfer_concentration": {
                                "largest_transfer_dominance": (max(usd_values) / sum(usd_values) * 100) if sum(usd_values) > 0 else 0,
                                "top_1_percent_threshold": usd_distribution.get("p99", 0),
                                "whale_transfers": sum(1 for v in usd_values if v >= usd_distribution.get("p95", 0))
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate transfer analysis: {e}")
            
            filename_template = FileNameGenerator.generate_data_filename(
                "transfers", "filtered", "query", 
                {"limit": limit, "offset": offset, "filters": len([k for k, v in api_params.items() if v and k not in ["limit", "offset"]])},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=transfers_list,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large transfer dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get transfers: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["transfers"],
                api_message=f"Failed to get transfers: {str(e)}",
                limit=limit,
                offset=offset
            )

    # =========================================================================
    # Wallet-Specific Tools
    # =========================================================================
    
    async def get_token_balances(
        self,
        address: str,
        chains: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get token balances for a specific wallet address.
        
        Retrieves all token holdings for a given address, including balance amounts,
        USD values, and token metadata. Essential for portfolio analysis and
        wealth tracking.
        
        Args:
            address: Wallet address to analyze
            chains: Comma-separated chain list to filter results (optional)
                  
        Returns:
            dict: Token balance data or file path for large responses
        """
        try:
            # Validate parameters
            address = self._validate_address(address)
            
            # Prepare API request parameters according to actual API spec
            api_params = {}
            
            if chains:
                api_params["chains"] = chains
            
            # Make API request
            endpoint = _API_ENDPOINTS["balances"].format(address=address)
            data = await self._make_api_request(endpoint, api_params)
            
            # Handle response format according to API spec
            # API returns {totalBalance: {}, balances: {chainName: [BalanceDetail]}}
            # BalanceDetail: {name, symbol, id, ethereumAddress, balance, balanceExact, usd, price, etc.}
            balances_list = []
            portfolio_summary = {}
            
            if isinstance(data, dict):
                total_balance = data.get("totalBalance", {})
                balances_by_chain = data.get("balances", {})
                portfolio_summary = {"totalBalance": total_balance}
                
                # Flatten balances from all chains into a single list for analysis
                for chain_name, chain_balances in balances_by_chain.items():
                    if isinstance(chain_balances, list):
                        for balance in chain_balances:
                            try:
                                # Add chain info and validate required fields
                                balance_copy = balance.copy()
                                balance_copy["chain"] = chain_name
                                balances_list.append(balance_copy)
                            except (AttributeError, TypeError) as e:
                                logger.warning(f"Failed to process balance item: {e}")
                                continue
            elif isinstance(data, list):
                # Direct list of balance items
                balances_list = data
            else:
                logger.warning(f"Unexpected balance response format: {type(data)}")
            
            base_response = {
                "success": True,
                "address": address,
                "chains": chains,
                "count": len(balances_list),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time()),
                **portfolio_summary
            }
            
            # Calculate portfolio analysis based on actual API response structure
            analysis = {}
            if balances_list:
                try:
                    # Extract USD values - API uses 'usd' field in BalanceDetail
                    usd_values = []
                    for balance in balances_list:
                        try:
                            if balance.get("usd") is not None:
                                usd_values.append(float(balance["usd"]))
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to parse USD value: {e}")
                            continue
                    
                    # Count chains and tokens from BalanceDetail objects
                    unique_chains = set()
                    unique_tokens = set()
                    
                    for balance in balances_list:
                        try:
                            if balance.get("chain"):
                                unique_chains.add(balance["chain"])
                            
                            # Token identifier could be symbol, name, or id
                            token_id = balance.get("symbol") or balance.get("name") or balance.get("id")
                            if token_id:
                                unique_tokens.add(token_id)
                        except (AttributeError, TypeError):
                            continue
                    
                    if usd_values:
                        # Essential portfolio insights for LLM
                        usd_array = _np.array(usd_values)
                        total_value = sum(usd_values)
                        largest_holding = max(usd_values)
                        gini = self.stats.calculate_gini_coefficient(usd_array)
                        
                        analysis = {
                            "portfolio_summary": {
                                "total_value_usd": round(total_value, 2),
                                "token_count": len(usd_values),
                                "diversification": {
                                    "gini_coefficient": round(gini, 3),
                                    "largest_holding_share_pct": round((largest_holding / total_value * 100), 1) if total_value > 0 else 0,
                                    "concentration_level": "high" if gini > 0.7 else "moderate" if gini > 0.4 else "low",
                                    "significant_holdings": sum(1 for v in usd_values if v > 1000)  # Holdings > $1k
                                }
                            },
                            "cross_chain_activity": {
                                "chains_used": len(unique_chains),
                                "unique_tokens": len(unique_tokens)
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate portfolio analysis: {e}")
            
            filename_template = FileNameGenerator.generate_data_filename(
                "token_balances", address, "address", {"chains": chains or "all"},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=balances_list,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large balance dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get token balances for {address}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["balances"],
                api_message=f"Failed to get token balances: {str(e)}",
                address=address
            )

    async def aclose(self):
        """Close all HTTP clients and clean up resources."""
        await self._http_client.aclose()
        logger.debug("Closed ArkhamToolkit and all clients")