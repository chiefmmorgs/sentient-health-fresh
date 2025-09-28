from __future__ import annotations

"""DefiLlama DeFi Analytics Toolkit
===================================

A comprehensive Agno-compatible toolkit that provides access to DefiLlama's DeFi analytics APIs
for protocol analytics, yield farming data, fees/revenue tracking, and ecosystem metrics
with intelligent data management and LLM-optimized responses.

## Supported Data Types

**TVL & Protocol Analytics**
- Protocol TVL data across all chains
- Historical TVL trends and breakdowns
- Protocol metadata and categorization
- Cross-chain TVL comparisons

**Fees & Revenue Analysis**
- Daily fees and revenue by protocol
- Chain-specific fee analysis
- Revenue distribution and trends
- Protocol profitability metrics

**Yield Farming Data** (Pro API)
- APY rates across protocols
- Yield pool compositions
- Staking rewards and farming opportunities
- Risk-adjusted yield metrics

**User Activity Metrics** (Pro API)
- Active user counts by protocol
- Transaction volumes and gas usage
- User growth and retention metrics
- Cross-protocol user behavior

## Key Features

✅ **Multi-Tier API Support**: Free endpoints + Pro API features with authentication
✅ **Smart Data Management**: Large responses automatically stored as Parquet files  
✅ **Financial Analytics**: Comprehensive statistical analysis of DeFi metrics
✅ **LLM-Optimized**: Standardized response formats with clear success/failure indicators
✅ **Async Performance**: Full async/await support with proper resource management
✅ **Framework Integration**: Seamless integration with agent YAML configuration

## Configuration Examples

### Basic Configuration (Free API)
```yaml
toolkits:
  - name: "DefiLlamaToolkit"
    params:
      data_dir: "./data/defillama"
      parquet_threshold: 1000
      default_chain: "ethereum"
    available_tools:
      - "get_protocol_fees"
      - "get_chain_fees"
      - "get_protocols"
      - "get_protocol_tvl"
```

### Pro Configuration
```yaml
toolkits:
  - name: "DefiLlamaToolkit"
    params:
      api_key: "${DEFILLAMA_API_KEY}"
      data_dir: "./data/defillama"
      parquet_threshold: 1000
      enable_pro_features: true
      cache_ttl_seconds: 1800
    available_tools:
      - "get_protocol_fees"
      - "get_chain_fees"
      - "get_yield_pools"
      - "get_yield_chart" 
      - "get_yield_pools_borrow"
      - "get_yield_perps"
      - "get_historical_liquidity"
      - "get_active_users"
      - "get_chain_assets"
```

## Environment Variables

- `DEFILLAMA_API_KEY`: Pro API key for premium endpoints (optional)
- `DEFILLAMA_BIG_DATA_THRESHOLD`: Global threshold for parquet storage (default: 1000)

## Response Format Standards

All tools return consistent JSON structures:

**Success Response:**
```json
{
  "success": true,
  "data": {...},           // Small responses
  "file_path": "...",      // Large responses stored as Parquet
  "chain": "ethereum",
  "protocol": "aave",
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

__all__ = ["DefiLlamaToolkit", "SupportedChain", "DataType"]

# Supported blockchain networks
class SupportedChain(str, Enum):
    """Supported blockchain networks for DefiLlama API."""
    ETHEREUM = "ethereum"
    ARBITRUM = "arbitrum"
    POLYGON = "polygon"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BSC = "bsc"
    FANTOM = "fantom"
    SOLANA = "solana"
    TRON = "tron"
    BASE = "base"

# Data types for API endpoints
class DataType(str, Enum):
    """Data types for fee/revenue endpoints."""
    DAILY_FEES = "dailyFees"
    DAILY_REVENUE = "dailyRevenue"
    DAILY_HOLDERS_REVENUE = "dailyHoldersRevenue"

# API Configuration
DEFAULT_BASE_URL = "https://api.llama.fi"
DEFAULT_PRO_BASE_URL = "https://pro-api.llama.fi"
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "defillama"
BIG_DATA_THRESHOLD = int(os.getenv("DEFILLAMA_BIG_DATA_THRESHOLD", "1000"))

# API endpoint mappings
_API_ENDPOINTS = {
    # Free endpoints
    "protocols": "/protocols",
    "protocol_detail": "/protocol/{protocol}",
    "protocol_tvl": "/tvl/{protocol}",
    "chains": "/v2/chains",
    "historical_chain_tvl": "/v2/historicalChainTvl/{chain}",
    "fees_overview": "/overview/fees",
    "fees_chain": "/overview/fees/{chain}",
    "fees_protocol": "/summary/fees/{protocol}",
    
    # Pro endpoints (require API key)
    "chain_assets": "/api/chainAssets",
    "active_users": "/api/activeUsers",
    "user_data": "/api/userData/{type}/{protocolId}",
    "token_protocols": "/api/tokenProtocols/{symbol}",
    "protocol_inflows": "/api/inflows/{protocol}/{timestamp}",
    
    # Yield endpoints (Pro API)
    "yield_pools": "/yields/pools",
    "yield_chart": "/yields/chart/{pool_id}",
    "yield_pools_borrow": "/yields/poolsBorrow", 
    "yield_perps": "/yields/perps",
    "historical_liquidity": "/api/historicalLiquidity/{token}",
}


class DefiLlamaAPIError(Exception):
    """Raised when the DefiLlama API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class DefiLlamaToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """DefiLlama DeFi Analytics Toolkit
    
    A comprehensive toolkit providing access to DefiLlama's DeFi analytics platform
    for protocol analytics, yield farming, fees/revenue tracking, and ecosystem metrics.
    Designed for DeFi analysts, protocol researchers, and automated monitoring systems.
    
    **Supported Analytics:**
    - Protocol TVL tracking and historical trends
    - Daily fees and revenue analysis across protocols
    - Yield farming pools and APY data (Pro)
    - User activity metrics and growth tracking (Pro)
    - Cross-chain asset distribution analysis (Pro)
    - Protocol profitability and sustainability metrics
    
    **Key Capabilities:**
    - Multi-tier API support (free + Pro endpoints)
    - Advanced financial metrics and statistical analysis
    - Cross-protocol and cross-chain comparisons
    - Large dataset management via Parquet storage
    - Real-time DeFi ecosystem monitoring
    - LLM-optimized insights and trend analysis
    
    **Data Management:**
    Large responses (>threshold) are automatically stored as Parquet files and the
    file path is returned instead of raw data, optimizing memory usage and enabling
    efficient downstream processing with pandas/polars.
    """

    # Toolkit metadata for enhanced display
    _toolkit_category = "defi"
    _toolkit_type = "analytics" 
    _toolkit_icon = "🦙"

    def __init__(
        self,
        api_key: str | None = None,
        enable_pro_features: bool = None,
        default_chain: SupportedChain | str = SupportedChain.ETHEREUM,
        base_url: str = DEFAULT_BASE_URL,
        pro_base_url: str = DEFAULT_PRO_BASE_URL,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        parquet_threshold: int = BIG_DATA_THRESHOLD,
        cache_ttl_seconds: int = 1800,
        name: str = "defillama_toolkit",
        **kwargs: Any,
    ):
        """Initialize the DefiLlama Analytics Toolkit.
        
        Args:
            api_key: DefiLlama Pro API key. If None, reads from DEFILLAMA_API_KEY 
                    environment variable. Required for Pro endpoints.
            enable_pro_features: Enable Pro API features. If None, auto-detected based 
                               on API key availability.
            default_chain: Default blockchain network for chain-specific queries.
                          Options: "ethereum", "arbitrum", "polygon", etc.
            base_url: Base URL for free DefiLlama API endpoints.
                     Default: https://api.llama.fi
            pro_base_url: Base URL for Pro DefiLlama API endpoints.
                         Default: https://pro-api.llama.fi
            data_dir: Directory path where Parquet files will be stored for large
                     responses. Defaults to tools/data/defillama/
            parquet_threshold: Size threshold in KB for Parquet storage.
                             Responses with JSON payload > threshold KB will be
                             saved to disk and file path returned instead of data.
                             Recommended: 10-50 KB for DeFi data (complex objects).
            cache_ttl_seconds: Cache time-to-live for API responses in seconds
            name: Name identifier for this toolkit instance
            **kwargs: Additional arguments passed to Toolkit
            
        Raises:
            ValueError: If default_chain is not supported
            
        Example:
            ```python
            # Basic DeFi analytics toolkit (free tier)
            toolkit = DefiLlamaToolkit(
                default_chain="ethereum"
            )
            
            # Get protocol fees data
            fees = await toolkit.get_protocol_fees("aave")
            
            # Analyze chain-wide fee trends
            eth_fees = await toolkit.get_chain_fees("ethereum")
            
            # Pro tier with advanced features
            pro_toolkit = DefiLlamaToolkit(
                api_key="your_pro_api_key",
                enable_pro_features=True
            )
            
            # Get yield farming opportunities
            yields = await pro_toolkit.get_yield_pools()
            
            # Track user activity metrics
            users = await pro_toolkit.get_active_users()
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
            
        # API key and Pro features configuration
        self._api_key = api_key or os.getenv("DEFILLAMA_API_KEY")
        
        # Auto-detect Pro features if not explicitly set
        if enable_pro_features is None:
            self.enable_pro_features = bool(self._api_key)
        else:
            self.enable_pro_features = enable_pro_features
            
        # Validate Pro features requirements
        if self.enable_pro_features and not self._api_key:
            logger.warning(
                "Pro features enabled but no API key provided. "
                "Set DEFILLAMA_API_KEY environment variable or pass api_key parameter."
            )
            self.enable_pro_features = False
        
        self.base_url = base_url
        self.pro_base_url = pro_base_url
        
        # Initialize standard configuration (includes cache system and HTTP client)
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=cache_ttl_seconds
        )
        
        # Define available tools based on Pro features
        available_tools = [
            self.get_protocols,
            self.get_protocol_tvl,
            self.get_protocol_detail,
            self.get_chains,
            self.get_chain_historical_tvl,
            self.get_protocol_fees,
            self.get_chain_fees,
        ]
        
        # Add Pro tools if enabled
        if self.enable_pro_features:
            available_tools.extend([
                self.get_chain_assets,
                self.get_yield_pools,
                self.get_yield_chart,
                self.get_yield_pools_borrow,
                self.get_yield_perps,
                self.get_historical_liquidity,
                self.get_active_users,
            ])
        
        # Initialize Toolkit
        super().__init__(name=name, tools=available_tools, **kwargs)
        
        # Initialize BaseDataToolkit helpers  
        self._init_data_helpers(
            data_dir=data_dir,
            parquet_threshold=parquet_threshold,
            file_prefix="defillama_",
            toolkit_name="defillama",
        )
        
        # Initialize statistical analyzer
        self.stats = StatisticalAnalyzer()
        
        logger.info(
            f"Initialized DefiLlamaToolkit with default chain '{self.default_chain.value}', "
            f"Pro features: {self.enable_pro_features}"
        )

    def _build_defillama_auth_headers(self, endpoint_name: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Build authentication headers for DefiLlama endpoints."""
        # Parameters kept for interface compatibility with BaseAPIToolkit
        _ = endpoint_name, config  # Acknowledge parameters
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SentientResearchAgent-DefiLlamaToolkit/1.0"
        }

    async def _setup_endpoints(self):
        """Setup HTTP endpoints for DefiLlama API."""
        # Setup free API endpoint
        await self._http_client.add_endpoint(
            name="defillama_free",
            base_url=self.base_url,
            headers=self._build_defillama_auth_headers("defillama_free", {}),
            timeout=30.0,
            rate_limit=0.2,  # Conservative rate limiting
        )
        
        # Setup Pro API endpoint if enabled
        if self.enable_pro_features:
            await self._http_client.add_endpoint(
                name="defillama_pro",
                base_url=self.pro_base_url,
                headers=self._build_defillama_auth_headers("defillama_pro", {}),
                timeout=30.0,
                rate_limit=0.1,  # More conservative for Pro API
            )

    async def _make_api_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        use_pro_api: bool = False,
        method: str = "GET"
    ) -> Dict[str, Any]:
        """Make API request to DefiLlama endpoint.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters or request body
            use_pro_api: Whether to use Pro API endpoint
            method: HTTP method (GET, POST, etc.)
            
        Returns:
            dict: Raw JSON response from API
        """
        # Ensure endpoints are setup
        if "defillama_free" not in self._http_client.get_endpoints():
            await self._setup_endpoints()
        
        # Choose endpoint based on Pro API usage
        if use_pro_api and self.enable_pro_features:
            endpoint_name = "defillama_pro"
            # For Pro API, inject API key into URL path
            endpoint = f"/{self._api_key}{endpoint}"
        else:
            endpoint_name = "defillama_free"
            
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
        supported_chains = {c.value for c in SupportedChain}
        
        if chain_lower not in supported_chains:
            supported_list = list(supported_chains)
            raise ValueError(f"Unsupported chain '{chain}'. Supported: {supported_list}")
        return chain_lower

    def _validate_protocol(self, protocol: str) -> str:
        """Validate and normalize protocol parameter.
        
        Args:
            protocol: Protocol identifier to validate
            
        Returns:
            str: Normalized protocol identifier
            
        Raises:
            ValueError: If protocol format is invalid
        """
        if not protocol or not isinstance(protocol, str):
            raise ValueError("Protocol must be a non-empty string")
        
        protocol = protocol.strip().lower()
        if not protocol:
            raise ValueError("Protocol cannot be empty")
        
        # Basic format validation - protocols are typically lowercase with hyphens
        if any(char in protocol for char in [' ', '/', '\\', '?', '#']):
            raise ValueError(f"Invalid protocol format: {protocol}")
        
        return protocol

    # =========================================================================
    # TVL & Protocol Tools
    # =========================================================================
    
    async def get_protocols(self) -> Dict[str, Any]:
        """Get all protocols with current TVL data.
        
        Retrieves comprehensive list of all DeFi protocols tracked by DefiLlama,
        including current TVL, category classification, supported chains, and
        recent performance metrics.
        
        Returns:
            dict: Protocols data or file path for large responses
            
        **Success Response:**
        ```json
        {
            "success": true,
            "data": [
                {
                    "id": "2269",
                    "name": "Aave",
                    "symbol": "AAVE",
                    "category": "Lending",
                    "chains": ["Ethereum", "Polygon"],
                    "tvl": 5200000000,
                    "chainTvls": {
                        "Ethereum": 3200000000,
                        "Polygon": 2000000000
                    },
                    "change_1d": 2.1,
                    "change_7d": -5.3,
                    "mcap": 1500000000
                }
            ],
            "count": 1247,
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Get all protocols overview
        protocols = await toolkit.get_protocols()
        if protocols["success"]:
            if "data" in protocols:
                # Analyze top protocols by TVL
                for protocol in protocols["data"][:10]:
                    print(f"{protocol['name']}: ${protocol['tvl']:,.0f}")
                    
        # Filter by category
        lending_protocols = [p for p in protocols["data"] 
                           if p.get("category") == "Lending"]
        ```
        """
        try:
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["protocols"])
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=list
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            base_response = {
                "success": True,
                "count": len(data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Add analysis for protocol data
            analysis = {}
            if data:
                try:
                    # Extract TVL values for statistical analysis
                    tvl_values = []
                    categories = {}
                    chains_usage = {}
                    
                    for protocol in data:
                        try:
                            if protocol.get("tvl") is not None:
                                tvl_values.append(float(protocol["tvl"]))
                                
                            # Count by category
                            category = protocol.get("category", "Unknown")
                            categories[category] = categories.get(category, 0) + 1
                            
                            # Count chain usage
                            protocol_chains = protocol.get("chains", [])
                            if isinstance(protocol_chains, list):
                                for chain in protocol_chains:
                                    chains_usage[chain] = chains_usage.get(chain, 0) + 1
                                    
                        except (ValueError, TypeError):
                            continue
                    
                    if tvl_values:
                        # Use StatisticalAnalyzer for TVL distribution analysis
                        tvl_array = _np.array(tvl_values)
                        tvl_distribution = self.stats.calculate_distribution_stats(tvl_array)
                        total_tvl = sum(tvl_values)
                        
                        # Calculate market concentration
                        top_10_tvl = sum(sorted(tvl_values, reverse=True)[:10])
                        concentration_ratio = (top_10_tvl / total_tvl * 100) if total_tvl > 0 else 0
                        
                        analysis = {
                            "ecosystem_overview": {
                                "total_protocols": len(data),
                                "total_tvl": total_tvl,
                                "market_concentration_top10_pct": round(concentration_ratio, 1),
                                "tvl_distribution": tvl_distribution
                            },
                            "category_breakdown": dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]),
                            "chain_adoption": dict(sorted(chains_usage.items(), key=lambda x: x[1], reverse=True)[:10]),
                            "market_insights": {
                                "dominant_category": max(categories.items(), key=lambda x: x[1])[0] if categories else None,
                                "most_adopted_chain": max(chains_usage.items(), key=lambda x: x[1])[0] if chains_usage else None,
                                "concentration_level": "high" if concentration_ratio > 50 else "moderate" if concentration_ratio > 30 else "distributed"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate protocol analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "protocols", "all", "overview", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large protocols dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get protocols: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["protocols"],
                api_message=f"Failed to get protocols: {str(e)}"
            )

    async def get_protocol_tvl(self, protocol: str) -> Dict[str, Any]:
        """Get current TVL for a specific protocol.
        
        Simplified endpoint that returns only the current Total Value Locked
        for the specified protocol as a single number.
        
        Args:
            protocol: Protocol identifier (e.g., "aave", "uniswap", "compound")
                     
        Returns:
            dict: Current TVL data
            
        **Success Response:**
        ```json
        {
            "success": true,
            "protocol": "aave",
            "tvl": 4962012809.795062,
            "tvl_formatted": "$4.96B",
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Get current Aave TVL
        aave_tvl = await toolkit.get_protocol_tvl("aave")
        if aave_tvl["success"]:
            print(f"Aave TVL: {aave_tvl['tvl_formatted']}")
            
        # Compare multiple protocols
        protocols = ["aave", "compound", "uniswap"]
        for protocol in protocols:
            result = await toolkit.get_protocol_tvl(protocol)
            if result["success"]:
                print(f"{protocol.upper()}: ${result['tvl']:,.0f}")
        ```
        """
        try:
            # Validate and normalize protocol
            protocol = self._validate_protocol(protocol)
            
            # Make API request
            endpoint = _API_ENDPOINTS["protocol_tvl"].format(protocol=protocol)
            tvl_value = await self._make_api_request(endpoint)
            
            # Validate response - should be a number
            if not isinstance(tvl_value, (int, float)):
                raise ValueError(f"Expected numeric TVL value, got {type(tvl_value)}")
            
            # Format TVL for human readability
            if tvl_value >= 1e9:
                tvl_formatted = f"${tvl_value/1e9:.2f}B"
            elif tvl_value >= 1e6:
                tvl_formatted = f"${tvl_value/1e6:.2f}M"
            elif tvl_value >= 1e3:
                tvl_formatted = f"${tvl_value/1e3:.2f}K"
            else:
                tvl_formatted = f"${tvl_value:.2f}"
            
            return self.response_builder.success_response(
                protocol=protocol,
                tvl=float(tvl_value),
                tvl_formatted=tvl_formatted,
                fetched_at=BaseAPIToolkit.unix_to_iso(time.time())
            )
            
        except Exception as e:
            logger.error(f"Failed to get TVL for protocol {protocol}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["protocol_tvl"],
                api_message=f"Failed to get protocol TVL: {str(e)}",
                protocol=protocol
            )

    # =========================================================================
    # Fees & Revenue Tools (Priority endpoints mentioned by user)
    # =========================================================================
    
    async def get_protocol_fees(
        self, 
        protocol: str, 
        data_type: Optional[DataType] = DataType.DAILY_FEES
    ) -> Dict[str, Any]:
        """Get daily fees and revenue data for a specific protocol.
        
        Retrieves comprehensive fee and revenue metrics for the specified protocol,
        including historical trends, breakdown by chains, and profitability analysis.
        
        Args:
            protocol: Protocol identifier (e.g., "aave", "uniswap", "compound")
            data_type: Type of data to retrieve. Options:
                      - "dailyFees": Daily protocol fees
                      - "dailyRevenue": Daily protocol revenue
                      - "dailyHoldersRevenue": Daily revenue to token holders
                     
        Returns:
            dict: Protocol fees data or file path for large responses
            
        **Success Response:**
        ```json
        {
            "success": true,
            "data": {
                "id": "parent#hyperliquid",
                "name": "Hyperliquid",
                "total24h": 4890250,
                "total7d": 26184696,
                "totalAllTime": 499292857,
                "change_1d": 7.47,
                "chains": ["Hyperliquid L1"],
                "totalDataChart": [
                    [1734912000, 1472923]
                ]
            },
            "protocol": "hyperliquid",
            "data_type": "dailyFees",
            "fetched_at": "2024-01-01T12:00:00Z"
        }
        ```
        
        Example Usage:
        ```python
        # Get Uniswap daily fees
        uni_fees = await toolkit.get_protocol_fees("uniswap", "dailyFees")
        if uni_fees["success"]:
            fees_data = uni_fees["data"]
            print(f"Uniswap 24h fees: ${fees_data['total24h']:,.0f}")
            
        # Compare fees vs revenue for a protocol
        fees = await toolkit.get_protocol_fees("aave", "dailyFees")
        revenue = await toolkit.get_protocol_fees("aave", "dailyRevenue")
        ```
        """
        try:
            # Validate and normalize protocol
            protocol = self._validate_protocol(protocol)
            
            # Prepare API request parameters
            api_params = {}
            if data_type and data_type != DataType.DAILY_FEES:
                api_params["dataType"] = data_type.value
            
            # Make API request
            endpoint = _API_ENDPOINTS["fees_protocol"].format(protocol=protocol)
            data = await self._make_api_request(endpoint, api_params)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            base_response = {
                "success": True,
                "protocol": protocol,
                "data_type": data_type.value if data_type else DataType.DAILY_FEES.value,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate fee analytics
            analysis = {}
            if data:
                try:
                    # Extract key metrics
                    total_24h = data.get("total24h", 0)
                    total_7d = data.get("total7d", 0)
                    total_all_time = data.get("totalAllTime", 0)
                    change_1d = data.get("change_1d", 0)
                    
                    # Historical data analysis if available
                    historical_data = data.get("totalDataChart", [])
                    if historical_data and len(historical_data) > 1:
                        # Extract values from chart data
                        timestamps = [item[0] for item in historical_data]
                        values = [item[1] for item in historical_data]
                        
                        if len(values) >= 2:
                            values_array = _np.array(values)
                            
                            # Use StatisticalAnalyzer for trend analysis
                            trend_analysis = self.stats.analyze_price_trends(values_array, window=min(30, len(values)))
                            
                            # Calculate growth metrics
                            if len(values) >= 30:
                                monthly_growth = ((values[-1] / values[-30]) - 1) * 100 if values[-30] > 0 else 0
                            else:
                                monthly_growth = 0
                                
                            analysis = {
                                "financial_metrics": {
                                    "daily_fees_24h": total_24h,
                                    "weekly_fees": total_7d,
                                    "all_time_fees": total_all_time,
                                    "daily_change_pct": change_1d,
                                    "weekly_run_rate": total_7d * 52.14,  # Annualized
                                    "fee_sustainability_score": "high" if total_24h > 100000 else "medium" if total_24h > 10000 else "low"
                                },
                                "trend_analysis": {
                                    "trend_direction": trend_analysis.get("trend_direction", "sideways"),
                                    "momentum_pct": trend_analysis.get("momentum_pct", 0),
                                    "monthly_growth_pct": monthly_growth,
                                    "volatility_regime": self.stats.classify_volatility_from_change(abs(change_1d))
                                },
                                "revenue_insights": {
                                    "avg_daily_revenue": total_7d / 7 if total_7d > 0 else 0,
                                    "revenue_consistency": "stable" if abs(change_1d) < 10 else "volatile",
                                    "growth_stage": "mature" if total_all_time > 1000000 else "emerging"
                                }
                            }
                            
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate fee analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "protocol_fees", protocol, "protocol", {"data_type": data_type.value if data_type else "dailyFees"},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet([data], filename),  # Wrap single object
                filename_template=filename_template,
                large_data_note="Large protocol fees dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get protocol fees for {protocol}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["fees_protocol"],
                api_message=f"Failed to get protocol fees: {str(e)}",
                protocol=protocol
            )

    async def get_chain_fees(
        self, 
        chain: str, 
        data_type: Optional[DataType] = DataType.DAILY_FEES
    ) -> Dict[str, Any]:
        """Get overview of daily fees for a specific blockchain.
        
        Retrieves aggregated fee data for all protocols on the specified chain,
        providing insights into network activity, fee trends, and ecosystem health.
        
        Args:
            chain: Chain identifier (e.g., "ethereum", "arbitrum", "polygon")
            data_type: Type of data to retrieve. Options:
                      - "dailyFees": Daily chain fees
                      - "dailyRevenue": Daily chain revenue
                      - "dailyHoldersRevenue": Daily revenue to token holders
                     
        Returns:
            dict: Chain fees data or file path for large responses
        """
        try:
            # Validate and normalize chain
            chain = self._validate_chain(chain)
            
            # Prepare API request parameters
            api_params = {}
            if data_type and data_type != DataType.DAILY_FEES:
                api_params["dataType"] = data_type.value
            
            # Make API request
            endpoint = _API_ENDPOINTS["fees_chain"].format(chain=chain)
            data = await self._make_api_request(endpoint, api_params)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            base_response = {
                "success": True,
                "chain": chain,
                "data_type": data_type.value if data_type else DataType.DAILY_FEES.value,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate chain-level analytics
            analysis = {}
            if data:
                try:
                    # Extract chain metrics
                    total_fees_24h = data.get("totalFees24h", 0)
                    protocols = data.get("protocols", [])
                    
                    if protocols:
                        # Analyze protocol distribution
                        protocol_fees = [(p.get("name", "Unknown"), p.get("fees24h", 0)) for p in protocols]
                        protocol_fees.sort(key=lambda x: x[1], reverse=True)
                        
                        # Calculate concentration metrics
                        total_protocol_fees = sum(fee for _, fee in protocol_fees)
                        if total_protocol_fees > 0:
                            top_5_fees = sum(fee for _, fee in protocol_fees[:5])
                            concentration_pct = (top_5_fees / total_protocol_fees * 100)
                        else:
                            concentration_pct = 0
                        
                        analysis = {
                            "chain_overview": {
                                "total_fees_24h": total_fees_24h,
                                "active_protocols": len(protocols),
                                "top_5_concentration_pct": round(concentration_pct, 1),
                                "ecosystem_health": "thriving" if len(protocols) >= 10 else "developing" if len(protocols) >= 5 else "nascent"
                            },
                            "top_protocols": [
                                {"name": name, "fees_24h": fee, "market_share_pct": round((fee / total_protocol_fees * 100), 1) if total_protocol_fees > 0 else 0}
                                for name, fee in protocol_fees[:10]
                            ],
                            "market_insights": {
                                "dominant_protocol": protocol_fees[0][0] if protocol_fees else None,
                                "market_leader_share_pct": round((protocol_fees[0][1] / total_protocol_fees * 100), 1) if protocol_fees and total_protocol_fees > 0 else 0,
                                "competition_level": "high" if concentration_pct < 30 else "moderate" if concentration_pct < 60 else "concentrated"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate chain analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "chain_fees", chain, "chain", {"data_type": data_type.value if data_type else "dailyFees"},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet([data], filename),
                filename_template=filename_template,
                large_data_note="Large chain fees dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get chain fees for {chain}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["fees_chain"],
                api_message=f"Failed to get chain fees: {str(e)}",
                chain=chain
            )

    # =========================================================================
    # Pro API Tools (require API key)
    # =========================================================================
    
    async def get_yield_pools(self) -> Dict[str, Any]:
        """Get all yield farming pools with current APY data.
        
        Retrieves comprehensive yield farming opportunities across all protocols,
        including APY breakdowns, pool compositions, and risk assessments.
        
        **Pro API Required**
        
        Returns:
            dict: Yield pools data or file path for large responses
        """
        if not self.enable_pro_features:
            return self.response_builder.error_response(
                message="Pro API features required for yield pools data",
                error_type="pro_api_required"
            )
            
        try:
            # Make Pro API request
            data = await self._make_api_request(_API_ENDPOINTS["yield_pools"], use_pro_api=True)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            pools_data = data.get("data", [])
            
            base_response = {
                "success": True,
                "count": len(pools_data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate yield analytics
            analysis = {}
            if pools_data:
                try:
                    # Extract APY values for analysis
                    apy_values = [pool.get("apy", 0) for pool in pools_data if pool.get("apy") is not None]
                    
                    if apy_values:
                        apy_array = _np.array(apy_values)
                        apy_stats = self.stats.calculate_distribution_stats(apy_array)
                        
                        # Categorize pools by APY ranges
                        high_yield = sum(1 for apy in apy_values if apy > 20)
                        medium_yield = sum(1 for apy in apy_values if 5 <= apy <= 20)
                        low_yield = sum(1 for apy in apy_values if apy < 5)
                        
                        # Chain and protocol distribution
                        chains = {}
                        protocols = {}
                        for pool in pools_data:
                            chain = pool.get("chain", "Unknown")
                            chains[chain] = chains.get(chain, 0) + 1
                            
                            protocol = pool.get("project", "Unknown")
                            protocols[protocol] = protocols.get(protocol, 0) + 1
                        
                        analysis = {
                            "yield_landscape": {
                                "total_pools": len(pools_data),
                                "avg_apy": round(float(_np.mean(apy_array)), 2),
                                "median_apy": round(float(_np.median(apy_array)), 2),
                                "max_apy": round(float(_np.max(apy_array)), 2),
                                "apy_distribution": apy_stats
                            },
                            "opportunity_segments": {
                                "high_yield_pools": high_yield,
                                "medium_yield_pools": medium_yield,
                                "stable_yield_pools": low_yield,
                                "risk_reward_ratio": high_yield / len(pools_data) if len(pools_data) > 0 else 0
                            },
                            "ecosystem_diversity": {
                                "active_chains": len(chains),
                                "active_protocols": len(protocols),
                                "top_chains": dict(sorted(chains.items(), key=lambda x: x[1], reverse=True)[:5]),
                                "top_protocols": dict(sorted(protocols.items(), key=lambda x: x[1], reverse=True)[:5])
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate yield analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "yield_pools", "all", "yields", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=pools_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large yield pools dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get yield pools: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["yield_pools"],
                api_message=f"Failed to get yield pools: {str(e)}"
            )

    async def get_active_users(self) -> Dict[str, Any]:
        """Get active user metrics for all protocols.
        
        Retrieves user activity data across all tracked protocols, including
        daily active users, transaction counts, and growth metrics.
        
        **Pro API Required**
        
        Returns:
            dict: Active users data
        """
        if not self.enable_pro_features:
            return self.response_builder.error_response(
                message="Pro API features required for active users data",
                error_type="pro_api_required"
            )
            
        try:
            # Make Pro API request
            data = await self._make_api_request(_API_ENDPOINTS["active_users"], use_pro_api=True)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            base_response = {
                "success": True,
                "protocols_count": len(data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate user activity analytics
            analysis = {}
            if data:
                try:
                    # Extract user metrics
                    user_counts = []
                    protocols_with_users = []
                    
                    for protocol_id, protocol_data in data.items():
                        users_data = protocol_data.get("users", {})
                        if isinstance(users_data, dict) and users_data.get("value"):
                            user_count = users_data.get("value", 0)
                            user_counts.append(user_count)
                            protocols_with_users.append({
                                "protocol": protocol_data.get("name", protocol_id),
                                "users": user_count,
                                "new_users": protocol_data.get("newUsers", {}).get("value", 0),
                                "txs": protocol_data.get("txs", {}).get("value", 0)
                            })
                    
                    if user_counts:
                        user_array = _np.array(user_counts)
                        user_stats = self.stats.calculate_distribution_stats(user_array)
                        
                        # Sort protocols by user count
                        protocols_with_users.sort(key=lambda x: x["users"], reverse=True)
                        
                        # Calculate ecosystem health metrics
                        total_users = sum(user_counts)
                        top_10_users = sum(p["users"] for p in protocols_with_users[:10])
                        user_concentration = (top_10_users / total_users * 100) if total_users > 0 else 0
                        
                        analysis = {
                            "ecosystem_activity": {
                                "total_active_users": total_users,
                                "active_protocols": len(protocols_with_users),
                                "avg_users_per_protocol": round(float(_np.mean(user_array)), 0),
                                "user_distribution": user_stats,
                                "top_10_concentration_pct": round(user_concentration, 1)
                            },
                            "top_protocols": protocols_with_users[:10],
                            "market_insights": {
                                "most_active_protocol": protocols_with_users[0]["protocol"] if protocols_with_users else None,
                                "user_growth_leaders": sorted(protocols_with_users, key=lambda x: x.get("new_users", 0), reverse=True)[:5],
                                "ecosystem_maturity": "mature" if len(protocols_with_users) >= 50 else "growing" if len(protocols_with_users) >= 20 else "emerging"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate user activity analysis: {e}")
            
            return self.response_builder.success_response(
                data=data,
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get active users: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["active_users"],
                api_message=f"Failed to get active users: {str(e)}"
            )

    async def get_chain_assets(self) -> Dict[str, Any]:
        """Get asset breakdown across all blockchain networks.
        
        Retrieves comprehensive asset distribution data showing how value is
        distributed across different chains and asset types.
        
        **Pro API Required**
        
        Returns:
            dict: Chain assets data
        """
        if not self.enable_pro_features:
            return self.response_builder.error_response(
                message="Pro API features required for chain assets data",
                error_type="pro_api_required"
            )
            
        try:
            # Make Pro API request
            data = await self._make_api_request(_API_ENDPOINTS["chain_assets"], use_pro_api=True)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            timestamp = data.get("timestamp", int(time.time()))
            
            base_response = {
                "success": True,
                "timestamp": timestamp,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate asset distribution analytics
            analysis = {}
            if data:
                try:
                    # Extract chain data (excluding timestamp)
                    chain_data = {k: v for k, v in data.items() if k != "timestamp"}
                    
                    if chain_data:
                        # Analyze asset types across chains
                        total_values = []
                        canonical_values = []
                        native_values = []
                        third_party_values = []
                        
                        for assets in chain_data.values():
                            if isinstance(assets, dict):
                                canonical = float(assets.get("canonical", {}).get("total", 0))
                                native = float(assets.get("native", {}).get("total", 0))
                                third_party = float(assets.get("thirdParty", {}).get("total", 0))
                                total = float(assets.get("total", {}).get("total", 0))
                                
                                canonical_values.append(canonical)
                                native_values.append(native)
                                third_party_values.append(third_party)
                                total_values.append(total)
                        
                        if total_values:
                            ecosystem_total = sum(total_values)
                            
                            analysis = {
                                "asset_distribution": {
                                    "total_ecosystem_value": ecosystem_total,
                                    "active_chains": len(chain_data),
                                    "canonical_assets_total": sum(canonical_values),
                                    "native_assets_total": sum(native_values),
                                    "third_party_assets_total": sum(third_party_values)
                                },
                                "composition_breakdown": {
                                    "canonical_percentage": round((sum(canonical_values) / ecosystem_total * 100), 1) if ecosystem_total > 0 else 0,
                                    "native_percentage": round((sum(native_values) / ecosystem_total * 100), 1) if ecosystem_total > 0 else 0,
                                    "third_party_percentage": round((sum(third_party_values) / ecosystem_total * 100), 1) if ecosystem_total > 0 else 0
                                },
                                "chain_rankings": sorted(
                                    [(chain, float(assets.get("total", {}).get("total", 0))) for chain, assets in chain_data.items() if isinstance(assets, dict)],
                                    key=lambda x: x[1], reverse=True
                                )[:10]
                            }
                            
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate asset analysis: {e}")
            
            return self.response_builder.success_response(
                data=data,
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get chain assets: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["chain_assets"],
                api_message=f"Failed to get chain assets: {str(e)}"
            )

    async def get_protocol_detail(self, protocol: str) -> Dict[str, Any]:
        """Get detailed protocol information including historical TVL.
        
        Retrieves comprehensive protocol data including metadata, historical TVL
        across all chains, token breakdowns, and detailed analytics.
        
        Args:
            protocol: Protocol identifier (e.g., "aave", "uniswap")
                     
        Returns:
            dict: Detailed protocol data or file path for large responses
        """
        try:
            # Validate and normalize protocol
            protocol = self._validate_protocol(protocol)
            
            # Make API request
            endpoint = _API_ENDPOINTS["protocol_detail"].format(protocol=protocol)
            data = await self._make_api_request(endpoint)
            
            # Validate response structure
            validation_result = DataValidator.validate_structure(
                data, 
                expected_type=dict
            )
            
            if not validation_result["valid"]:
                raise ValueError(f"API response validation failed: {validation_result['errors']}")
            
            base_response = {
                "success": True,
                "protocol": protocol,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate analytics for protocol
            analysis = {}
            if data:
                try:
                    # Extract current TVL from historical data array
                    tvl_data = data.get("tvl", [])
                    current_tvl = 0
                    
                    # Get the most recent TVL value from the array
                    if isinstance(tvl_data, list) and tvl_data:
                        # Get the latest entry (last in array)
                        latest_entry = tvl_data[-1]
                        if isinstance(latest_entry, dict) and "totalLiquidityUSD" in latest_entry:
                            current_tvl = latest_entry["totalLiquidityUSD"]
                    elif isinstance(tvl_data, (int, float)):
                        # Handle case where API might return direct number
                        current_tvl = tvl_data
                    
                    chain_tvls = data.get("currentChainTvls", {})
                    
                    if chain_tvls:
                        chain_distribution = {}
                        total_chain_tvl = sum(chain_tvls.values())
                        
                        for chain, tvl in chain_tvls.items():
                            percentage = (tvl / total_chain_tvl * 100) if total_chain_tvl > 0 else 0
                            chain_distribution[chain] = {
                                "tvl": tvl,
                                "percentage": round(percentage, 1)
                            }
                        
                        # Find dominant chain
                        dominant_chain = max(chain_distribution.items(), key=lambda x: x[1]["tvl"])[0] if chain_distribution else None
                        
                        analysis = {
                            "protocol_summary": {
                                "current_tvl": current_tvl,
                                "chain_count": len(chain_tvls),
                                "dominant_chain": dominant_chain,
                                "chain_diversification": "high" if len(chain_tvls) >= 5 else "moderate" if len(chain_tvls) >= 3 else "low"
                            },
                            "chain_distribution": chain_distribution,
                            "market_position": {
                                "category": data.get("category", "Unknown"),
                                "multi_chain": len(chain_tvls) > 1,
                                "tvl_tier": "large" if current_tvl >= 1e9 else "medium" if current_tvl >= 1e8 else "small"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate protocol analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "protocol_detail", protocol, "protocol", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet([data], filename),  # Wrap single object in array
                filename_template=filename_template,
                large_data_note="Large protocol dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get protocol detail for {protocol}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["protocol_detail"],
                api_message=f"Failed to get protocol detail: {str(e)}",
                protocol=protocol
            )

    async def get_chains(self) -> Dict[str, Any]:
        """Get current TVL for all blockchain networks.
        
        Retrieves TVL data for all supported blockchain networks, providing
        a comprehensive overview of value distribution across the DeFi ecosystem.
        
        Returns:
            dict: Chains TVL data
        """
        try:
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["chains"])
            
            # Validate response
            if not isinstance(data, list):
                raise ValueError(f"Expected list response, got {type(data)}")
            
            # Calculate total TVL and analytics
            total_tvl = sum(chain.get("tvl", 0) for chain in data)
            
            # Sort by TVL descending
            data_sorted = sorted(data, key=lambda x: x.get("tvl", 0), reverse=True)
            
            # Calculate chain dominance
            analysis = {}
            if data_sorted:
                top_5_tvl = sum(chain.get("tvl", 0) for chain in data_sorted[:5])
                eth_tvl = next((chain.get("tvl", 0) for chain in data_sorted if chain.get("name") == "Ethereum"), 0)
                
                analysis = {
                    "ecosystem_overview": {
                        "total_chains": len(data),
                        "total_tvl": total_tvl,
                        "top_5_dominance_pct": round((top_5_tvl / total_tvl * 100), 1) if total_tvl > 0 else 0,
                        "ethereum_dominance_pct": round((eth_tvl / total_tvl * 100), 1) if total_tvl > 0 else 0
                    },
                    "top_chains": [
                        {
                            "name": chain.get("name"),
                            "tvl": chain.get("tvl", 0),
                            "percentage": round((chain.get("tvl", 0) / total_tvl * 100), 1) if total_tvl > 0 else 0
                        }
                        for chain in data_sorted[:5]
                    ]
                }
            
            return self.response_builder.success_response(
                data=data_sorted,
                count=len(data),
                total_tvl=total_tvl,
                fetched_at=BaseAPIToolkit.unix_to_iso(time.time()),
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get chains: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["chains"],
                api_message=f"Failed to get chains: {str(e)}"
            )

    async def get_yield_chart(self, pool_id: str) -> Dict[str, Any]:
        """Get historical yield chart data for a specific pool.
        
        Retrieves historical APY/APR data for the specified yield pool, showing
        yield trends over time for informed farming decisions.
        
        Args:
            pool_id: Unique identifier for the yield pool
                   
        Returns:
            dict: Historical yield chart data or error response
        """
        try:
            # Validate pool_id
            if not pool_id or not isinstance(pool_id, str):
                return self.response_builder.error_response(
                    error_type="validation_error",
                    message="Pool ID must be a non-empty string",
                    pool_id=pool_id
                )
                
            # Check if Pro API is available
            if not self.enable_pro_features:
                return self.response_builder.error_response(
                    error_type="pro_api_required",
                    message="Pro API features required for yield chart data",
                    required_feature="yield_chart"
                )
            
            # Make API request
            endpoint = _API_ENDPOINTS["yield_chart"].format(pool_id=pool_id)
            data = await self._make_api_request(endpoint, use_pro_api=True)
            
            # Validate response
            if not isinstance(data, (list, dict)):
                raise ValueError(f"Expected list or dict response, got {type(data)}")
            
            base_response = {
                "success": True,
                "pool_id": pool_id,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Handle different response formats
            chart_data = data
            if isinstance(data, dict):
                if "data" in data:
                    chart_data = data["data"]
                elif "chart" in data:
                    chart_data = data["chart"]
            
            base_response["count"] = len(chart_data) if isinstance(chart_data, list) else 1
            
            # Calculate yield trend analysis if we have time series data
            analysis = {}
            if isinstance(chart_data, list) and len(chart_data) >= 2:
                try:
                    # Extract yield values (APY) from chart data
                    yield_values = []
                    
                    for item in chart_data:
                        if isinstance(item, dict):
                            apy = item.get("apy", item.get("apyBase", item.get("yield", 0)))
                            if apy is not None:
                                yield_values.append(float(apy))
                    
                    if len(yield_values) >= 2:
                        yield_array = _np.array(yield_values)
                        
                        # Calculate trends using StatisticalAnalyzer
                        trend_analysis = self.stats.analyze_price_trends(yield_array, window=min(7, len(yield_values)//2))
                        
                        # Current vs historical yield metrics
                        current_apy = yield_values[-1] if yield_values else 0
                        max_apy = max(yield_values)
                        min_apy = min(yield_values)
                        avg_apy = sum(yield_values) / len(yield_values)
                        
                        # Volatility and stability metrics
                        yield_std = _np.std(yield_array)
                        stability_score = max(0, 100 - (yield_std / avg_apy * 100)) if avg_apy > 0 else 0
                        
                        analysis = {
                            "yield_analysis": {
                                "current_apy": round(current_apy, 2),
                                "average_apy": round(avg_apy, 2),
                                "max_apy": round(max_apy, 2),
                                "min_apy": round(min_apy, 2),
                                "yield_volatility": round(yield_std, 2),
                                "stability_score": round(stability_score, 1),
                                "trend_direction": trend_analysis.get("trend_direction", "sideways"),
                                "data_points": len(yield_values)
                            },
                            "risk_metrics": {
                                "yield_range": round(max_apy - min_apy, 2),
                                "coefficient_of_variation": round((yield_std / avg_apy * 100), 1) if avg_apy > 0 else 0,
                                "risk_category": "low" if yield_std < 2 else "medium" if yield_std < 5 else "high"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate yield chart analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "yield_chart", pool_id, "pool", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=chart_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data if isinstance(data, list) else [data], filename),
                filename_template=filename_template,
                large_data_note="Large yield chart dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get yield chart for pool {pool_id}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["yield_chart"],
                api_message=f"Failed to get yield chart: {str(e)}",
                pool_id=pool_id
            )

    async def get_yield_pools_borrow(self) -> Dict[str, Any]:
        """Get borrow costs APY of assets from lending markets.
        
        Retrieves borrowing cost data across lending protocols, showing
        current APY rates for borrowing various assets.
        
        Returns:
            dict: Borrow costs data across lending markets
        """
        try:
            # Check if Pro API is available
            if not self.enable_pro_features:
                return self.response_builder.error_response(
                    error_type="pro_api_required",
                    message="Pro API features required for borrow yields data",
                    required_feature="yield_pools_borrow"
                )
            
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["yield_pools_borrow"], use_pro_api=True)
            
            # Validate response
            if not isinstance(data, (list, dict)):
                raise ValueError(f"Expected list or dict response, got {type(data)}")
            
            # Handle different response formats
            borrow_data = data
            if isinstance(data, dict):
                if "data" in data:
                    borrow_data = data["data"]
                elif "pools" in data:
                    borrow_data = data["pools"]
            
            if not isinstance(borrow_data, list):
                borrow_data = [borrow_data] if borrow_data else []
            
            base_response = {
                "success": True,
                "count": len(borrow_data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate borrow market analysis
            analysis = {}
            if borrow_data:
                try:
                    # Extract borrow rates
                    borrow_rates = []
                    protocols = set()
                    chains = set()
                    assets = set()
                    
                    for pool in borrow_data:
                        if isinstance(pool, dict):
                            # Extract borrow APY
                            borrow_apy = pool.get("apyBaseBorrow", pool.get("apyBorrow", pool.get("borrowApy", 0)))
                            if borrow_apy and isinstance(borrow_apy, (int, float)):
                                borrow_rates.append(float(borrow_apy))
                            
                            # Collect metadata
                            if "project" in pool:
                                protocols.add(pool["project"])
                            if "chain" in pool:
                                chains.add(pool["chain"])
                            if "symbol" in pool:
                                assets.add(pool["symbol"])
                    
                    if borrow_rates:
                        borrow_array = _np.array(borrow_rates)
                        
                        # Calculate statistical metrics
                        stats_summary = self.stats.calculate_distribution_stats(borrow_array)
                        
                        # Categorize rates
                        low_cost = sum(1 for rate in borrow_rates if rate < 5)
                        medium_cost = sum(1 for rate in borrow_rates if 5 <= rate < 15)
                        high_cost = sum(1 for rate in borrow_rates if rate >= 15)
                        
                        analysis = {
                            "market_overview": {
                                "total_borrow_pools": len(borrow_data),
                                "protocols_count": len(protocols),
                                "chains_count": len(chains),
                                "assets_count": len(assets),
                                "avg_borrow_apy": round(stats_summary["mean"], 2),
                                "median_borrow_apy": round(stats_summary["median"], 2),
                                "min_borrow_apy": round(min(borrow_rates), 2),
                                "max_borrow_apy": round(max(borrow_rates), 2)
                            },
                            "rate_distribution": {
                                "low_cost_pools": low_cost,
                                "medium_cost_pools": medium_cost,
                                "high_cost_pools": high_cost,
                                "cost_spread": round(max(borrow_rates) - min(borrow_rates), 2)
                            },
                            "top_protocols": list(protocols)[:10],
                            "supported_chains": list(chains),
                            "available_assets": list(assets)[:20]  # Limit to avoid huge response
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate borrow yields analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "yield_pools_borrow", "all", "borrow", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=borrow_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large borrow yields dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get borrow yields: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["yield_pools_borrow"],
                api_message=f"Failed to get borrow yields: {str(e)}"
            )

    async def get_yield_perps(self) -> Dict[str, Any]:
        """Get funding rates and open interest of perps across exchanges.
        
        Retrieves perpetual futures data including funding rates and open interest
        across decentralized perpetual trading platforms.
        
        Returns:
            dict: Perpetuals funding rates and open interest data
        """
        try:
            # Check if Pro API is available
            if not self.enable_pro_features:
                return self.response_builder.error_response(
                    error_type="pro_api_required",
                    message="Pro API features required for perpetuals data",
                    required_feature="yield_perps"
                )
            
            # Make API request
            data = await self._make_api_request(_API_ENDPOINTS["yield_perps"], use_pro_api=True)
            
            # Validate response
            if not isinstance(data, (list, dict)):
                raise ValueError(f"Expected list or dict response, got {type(data)}")
            
            # Handle different response formats
            perps_data = data
            if isinstance(data, dict):
                if "data" in data:
                    perps_data = data["data"]
                elif "perps" in data:
                    perps_data = data["perps"]
            
            if not isinstance(perps_data, list):
                perps_data = [perps_data] if perps_data else []
            
            base_response = {
                "success": True,
                "count": len(perps_data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate perpetuals market analysis
            analysis = {}
            if perps_data:
                try:
                    # Extract funding rates and open interest
                    funding_rates = []
                    open_interest_values = []
                    exchanges = set()
                    assets = set()
                    
                    total_oi = 0
                    
                    for perp in perps_data:
                        if isinstance(perp, dict):
                            # Extract funding rate
                            funding_rate = perp.get("fundingRate", perp.get("rate", 0))
                            if funding_rate and isinstance(funding_rate, (int, float)):
                                funding_rates.append(float(funding_rate))
                            
                            # Extract open interest
                            open_interest = perp.get("openInterest", perp.get("oi", 0))
                            if open_interest and isinstance(open_interest, (int, float)):
                                open_interest_values.append(float(open_interest))
                                total_oi += float(open_interest)
                            
                            # Collect metadata
                            if "exchange" in perp:
                                exchanges.add(perp["exchange"])
                            elif "project" in perp:
                                exchanges.add(perp["project"])
                            if "symbol" in perp:
                                assets.add(perp["symbol"])
                            elif "pair" in perp:
                                assets.add(perp["pair"])
                    
                    # Calculate analysis
                    analysis_data = {
                        "market_overview": {
                            "total_perp_markets": len(perps_data),
                            "total_open_interest": total_oi,
                            "exchanges_count": len(exchanges),
                            "assets_count": len(assets)
                        }
                    }
                    
                    # Funding rate analysis
                    if funding_rates:
                        funding_array = _np.array(funding_rates)
                        funding_stats = self.stats.calculate_distribution_stats(funding_array)
                        
                        # Categorize funding rates (positive = longs pay shorts, negative = shorts pay longs)
                        positive_funding = sum(1 for rate in funding_rates if rate > 0)
                        negative_funding = sum(1 for rate in funding_rates if rate < 0)
                        neutral_funding = sum(1 for rate in funding_rates if rate == 0)
                        
                        analysis_data["funding_analysis"] = {
                            "avg_funding_rate": round(funding_stats["mean"], 4),
                            "median_funding_rate": round(funding_stats["median"], 4),
                            "max_funding_rate": round(max(funding_rates), 4),
                            "min_funding_rate": round(min(funding_rates), 4),
                            "positive_funding_markets": positive_funding,
                            "negative_funding_markets": negative_funding,
                            "neutral_funding_markets": neutral_funding,
                            "market_sentiment": "bullish" if positive_funding > negative_funding else "bearish" if negative_funding > positive_funding else "neutral"
                        }
                    
                    # Open interest analysis
                    if open_interest_values:
                        oi_array = _np.array(open_interest_values)
                        oi_stats = self.stats.calculate_distribution_stats(oi_array)
                        
                        analysis_data["open_interest_analysis"] = {
                            "total_open_interest": round(total_oi, 2),
                            "avg_market_oi": round(oi_stats["mean"], 2),
                            "median_market_oi": round(oi_stats["median"], 2),
                            "largest_market_oi": round(max(open_interest_values), 2),
                            "oi_concentration": round((max(open_interest_values) / total_oi * 100), 1) if total_oi > 0 else 0
                        }
                    
                    analysis_data["exchanges"] = list(exchanges)
                    analysis_data["top_assets"] = list(assets)[:20]  # Limit response size
                    
                    analysis = analysis_data
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate perpetuals analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "yield_perps", "all", "perps", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=perps_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large perpetuals dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get perpetuals data: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["yield_perps"],
                api_message=f"Failed to get perpetuals data: {str(e)}"
            )

    async def get_historical_liquidity(self, token: str) -> Dict[str, Any]:
        """Get historical liquidity data for a specific token.
        
        Retrieves historical liquidity information for tokens,
        providing insights into token liquidity trends and availability over time.
        
        **Pro API Required**
        
        Args:
            token: Token slug identifier (e.g., "usdt", "usdc", "dai", "weth", "wbtc")
                   Simple token identifiers as used by DefiLlama
                   
        Returns:
            dict: Historical liquidity data or error response
            
        **Success Response:**
        ```json
        {
            "success": true,
            "token": "usdt",
            "data": [...],  // Historical liquidity data points
            "analysis": {
                "liquidity_analysis": {
                    "current_liquidity": 1500000000.0,
                    "average_liquidity": 1200000000.0,
                    "trend_direction": "bullish",
                    "data_points": 365
                },
                "market_health": {
                    "liquidity_depth": "deep",
                    "stability_score": 85.2
                }
            }
        }
        ```
        """
        try:
            # Validate token identifier
            if not token or not isinstance(token, str):
                return self.response_builder.error_response(
                    error_type="validation_error",
                    message="Token slug must be a non-empty string",
                    token=token
                )
            
            # Clean and validate token slug format
            token = token.strip().lower()
            if not token or len(token) < 2:
                return self.response_builder.error_response(
                    error_type="validation_error", 
                    message="Token slug must be at least 2 characters long",
                    token=token
                )
                
            # Check if Pro API is available
            if not self.enable_pro_features:
                return self.response_builder.error_response(
                    error_type="pro_api_required",
                    message="Pro API features required for historical liquidity data",
                    required_feature="historical_liquidity"
                )
            
            # Make API request
            endpoint = _API_ENDPOINTS["historical_liquidity"].format(token=token)
            data = await self._make_api_request(endpoint, use_pro_api=True)
            
            # Handle API response
            if isinstance(data, dict) and data.get("message") == "No liquidity info available":
                return self.response_builder.error_response(
                    error_type="no_data",
                    message=f"No historical liquidity data available for token '{token}'. Try common tokens like: usdt, usdc, dai, weth, wbtc",
                    token=token
                )
            
            # Validate response
            if not isinstance(data, (list, dict)):
                raise ValueError(f"Expected list or dict response, got {type(data)}")
            
            base_response = {
                "success": True,
                "token": token,
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Handle different response formats
            liquidity_data = data
            if isinstance(data, dict):
                if "data" in data:
                    liquidity_data = data["data"]
                elif "liquidity" in data:
                    liquidity_data = data["liquidity"]
            
            if isinstance(liquidity_data, list):
                base_response["count"] = len(liquidity_data)
            else:
                base_response["count"] = 1
                liquidity_data = [liquidity_data] if liquidity_data else []
            
            # Calculate liquidity trend analysis if we have time series data
            analysis = {}
            if isinstance(liquidity_data, list) and len(liquidity_data) >= 2:
                try:
                    # Extract liquidity values from data
                    liquidity_values = []
                    timestamps = []
                    
                    for item in liquidity_data:
                        if isinstance(item, dict):
                            # Try different field names that might contain liquidity data
                            liquidity = item.get("liquidity", item.get("totalLiquidity", 
                                                 item.get("liquidityUSD", item.get("value", 0))))
                            timestamp = item.get("timestamp", item.get("date", 0))
                            if liquidity is not None and timestamp:
                                try:
                                    liquidity_values.append(float(liquidity))
                                    timestamps.append(timestamp)
                                except (ValueError, TypeError):
                                    continue
                    
                    if len(liquidity_values) >= 2:
                        liquidity_array = _np.array(liquidity_values)
                        
                        # Calculate trends using StatisticalAnalyzer
                        trend_analysis = self.stats.analyze_price_trends(
                            liquidity_array, 
                            window=min(7, len(liquidity_values)//2)
                        )
                        
                        # Current vs historical liquidity metrics
                        current_liquidity = liquidity_values[-1] if liquidity_values else 0
                        max_liquidity = max(liquidity_values)
                        min_liquidity = min(liquidity_values)
                        avg_liquidity = sum(liquidity_values) / len(liquidity_values)
                        
                        # Liquidity stability metrics
                        liquidity_std = _np.std(liquidity_array)
                        volatility_ratio = (liquidity_std / avg_liquidity * 100) if avg_liquidity > 0 else 0
                        
                        analysis = {
                            "liquidity_analysis": {
                                "current_liquidity": round(current_liquidity, 2),
                                "average_liquidity": round(avg_liquidity, 2),
                                "max_liquidity": round(max_liquidity, 2),
                                "min_liquidity": round(min_liquidity, 2),
                                "liquidity_volatility": round(liquidity_std, 2),
                                "volatility_ratio": round(volatility_ratio, 2),
                                "trend_direction": trend_analysis.get("trend_direction", "sideways"),
                                "data_points": len(liquidity_values)
                            },
                            "market_health": {
                                "liquidity_depth": "deep" if current_liquidity > avg_liquidity * 1.2 else "shallow" if current_liquidity < avg_liquidity * 0.8 else "moderate",
                                "stability_score": max(0, 100 - volatility_ratio),
                                "trend_strength": trend_analysis.get("trend_strength", 0),
                                "market_maturity": "mature" if liquidity_std < avg_liquidity * 0.3 else "volatile"
                            }
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate liquidity analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "historical_liquidity", token, "liquidity", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=liquidity_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large historical liquidity dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get historical liquidity for token {token}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["historical_liquidity"],
                api_message=f"Failed to get historical liquidity: {str(e)}",
                token=token
            )

    async def get_chain_historical_tvl(self, chain: str) -> Dict[str, Any]:
        """Get historical TVL data for a specific blockchain.
        
        Retrieves historical Total Value Locked data for the specified chain,
        excluding liquid staking and double-counted TVL for accurate trends.
        
        Args:
            chain: Chain identifier (e.g., "ethereum", "arbitrum", "polygon")
                   
        Returns:
            dict: Historical TVL data or file path for large responses
        """
        try:
            # Validate and normalize chain
            chain = self._validate_chain(chain)
            
            # Make API request
            endpoint = _API_ENDPOINTS["historical_chain_tvl"].format(chain=chain)
            data = await self._make_api_request(endpoint)
            
            # Validate response
            if not isinstance(data, list):
                raise ValueError(f"Expected list response, got {type(data)}")
            
            base_response = {
                "success": True,
                "chain": chain,
                "count": len(data),
                "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
            }
            
            # Calculate historical trends analysis
            analysis = {}
            if len(data) >= 2:
                try:
                    # Extract TVL values and timestamps
                    tvl_values = [item.get("tvl", 0) for item in data if item.get("tvl") is not None]
                    
                    if len(tvl_values) >= 2:
                        tvl_array = _np.array(tvl_values)
                        
                        # Calculate trends using StatisticalAnalyzer
                        trend_analysis = self.stats.analyze_price_trends(tvl_array, window=30)
                        
                        # Current vs historical metrics
                        current_tvl = tvl_values[-1] if tvl_values else 0
                        max_tvl = max(tvl_values)
                        min_tvl = min(tvl_values)
                        
                        # Growth analysis
                        if len(tvl_values) >= 30:
                            monthly_change = ((tvl_values[-1] / tvl_values[-30]) - 1) * 100 if tvl_values[-30] > 0 else 0
                        else:
                            monthly_change = 0
                        
                        analysis = {
                            "trend_analysis": {
                                "current_tvl": current_tvl,
                                "all_time_high": max_tvl,
                                "all_time_low": min_tvl,
                                "drawdown_from_ath_pct": round(((max_tvl - current_tvl) / max_tvl * 100), 1) if max_tvl > 0 else 0,
                                "monthly_change_pct": round(monthly_change, 1),
                                "trend_direction": trend_analysis.get("trend_direction", "sideways"),
                                "volatility": trend_analysis.get("volatility", 0)
                            },
                            "statistical_summary": self.stats.calculate_price_statistics(tvl_array)
                        }
                        
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to calculate TVL trend analysis: {e}")
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "chain_historical_tvl", chain, "chain", {},
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large historical TVL dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get historical TVL for chain {chain}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["historical_chain_tvl"],
                api_message=f"Failed to get historical chain TVL: {str(e)}",
                chain=chain
            )

    async def aclose(self):
        """Close all HTTP clients and clean up resources."""
        await self._http_client.aclose()
        logger.debug("Closed DefiLlamaToolkit and all clients")