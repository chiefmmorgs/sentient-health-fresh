from __future__ import annotations

"""Binance Cryptocurrency Market Data Toolkit
==========================================

A comprehensive Agno-compatible toolkit that provides access to Binance's public REST APIs 
across multiple market types with intelligent data management and LLM-optimized responses.

## Supported Market Types

**Spot Trading (`spot`)**
- URL: https://api.binance.com
- Traditional spot trading pairs (BTC/USDT, ETH/BTC, etc.)
- Immediate settlement
- Physical asset delivery

**USDⓈ-M Futures (`usdm`)**  
- URL: https://fapi.binance.com
- USDT-margined perpetual and quarterly futures
- Higher leverage available
- Cash settlement in USDT

**COIN-M Futures (`coinm`)**
- URL: https://dapi.binance.com  
- Coin-margined perpetual and quarterly futures
- Settled in the underlying cryptocurrency
- Traditional futures contracts

## Key Features

✅ **Multi-Market Support**: Each tool accepts `market_type` parameter for dynamic market switching
✅ **Smart Data Management**: Large responses automatically stored as Parquet files  
✅ **Symbol Validation**: Comprehensive symbol validation with allowlists
✅ **LLM-Optimized**: Standardized response formats with clear success/failure indicators
✅ **Async Performance**: Full async/await support with proper resource management
✅ **Framework Integration**: Seamless integration with agent YAML configuration

## Configuration Examples

### Basic Configuration
```yaml
toolkits:
  - name: "BinanceToolkit"
    params:
      symbols: ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
      default_market_type: "spot"
      data_dir: "./data/binance"
      parquet_threshold: 1000
    available_tools:
      - "get_current_price"
      - "get_klines" 
      - "get_order_book"
```

### Multi-Market Configuration
```yaml
toolkits:
  - name: "BinanceToolkit"
    params:
      symbols: ["BTCUSDT", "ETHUSDT"]
      default_market_type: "spot"
      api_key: "${BINANCE_API_KEY}"
      api_secret: "${BINANCE_API_SECRET}"
    available_tools:
      - "get_current_price"
      - "get_symbol_ticker_change"
      - "get_klines"
      - "get_book_ticker"
```

## Environment Variables

- `BINANCE_API_KEY`: API key for authenticated endpoints (optional for public data)
- `BINANCE_API_SECRET`: API secret for signed requests (optional for public data)  
- `BINANCE_BIG_DATA_THRESHOLD`: Global threshold for parquet storage (default: 1000)

## Response Format Standards

All tools return consistent JSON structures:

**Success Response:**
```json
{
  "success": true,
  "data": {...},           // Small responses
  "file_path": "...",      // Large responses stored as Parquet
  "market_type": "spot",
  "symbol": "BTCUSDT",
  "fetched_at": 1704067200
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Human-readable error description",
  "error_type": "validation_error|api_error|...",
  "symbol": "BTCUSDT",
  "market_type": "spot"
}
```
"""

import os
import time
import hmac
import hashlib
import urllib.parse
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union, Literal

import pandas as _pd
import numpy as _np
from agno.tools import Toolkit
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit, BaseAPIToolkit
from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import (
    DataHTTPClient, StatisticalAnalyzer, DataValidator, FileNameGenerator
)

__all__ = ["BinanceToolkit"]

# Supported market types
MarketType = Literal["spot", "usdm", "coinm"]

# Market configuration for different Binance API endpoints
_MARKET_CONFIG = {
    "spot": {
        "base_url": "https://api.binance.us",
        "prefix": "/api/v3", 
        "description": "Binance Spot Trading",
        "features": ["Immediate settlement", "Physical delivery", "Traditional pairs"]
    },
    "usdm": {
        "base_url": "https://fapi.binance.com",
        "prefix": "/fapi/v1",
        "description": "USDⓈ-M Futures (USDT-Margined)",
        "features": ["Perpetual contracts", "USDT settlement", "High leverage"]
    },
    "coinm": {
        "base_url": "https://dapi.binance.com", 
        "prefix": "/dapi/v1",
        "description": "COIN-M Futures (Coin-Margined)",
        "features": ["Coin settlement", "Traditional futures", "Physical delivery"]
    },
}

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "binance"
BIG_DATA_THRESHOLD = int(os.getenv("BINANCE_BIG_DATA_THRESHOLD", "1000"))

# API endpoint mappings
_API_ENDPOINTS = {
    "ticker_price": "/ticker/price",
    "ticker_24hr": "/ticker/24hr", 
    "order_book": "/depth",
    "klines": "/klines",
    "book_ticker": "/ticker/bookTicker",
    "exchange_info": "/exchangeInfo",
    "ping": "/ping",
    "server_time": "/time"
}


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class BinanceToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """Multi-Market Binance Trading Data Toolkit
    
    A comprehensive toolkit providing access to Binance market data across spot trading,
    USDⓈ-M futures, and COIN-M futures markets. Each tool method accepts a `market_type`
    parameter for dynamic market switching without requiring separate toolkit instances.
    
    **Supported Markets:**
    - `spot`: Traditional spot trading with immediate settlement
    - `usdm`: USDT-margined futures with high leverage
    - `coinm`: Coin-margined futures with cryptocurrency settlement
    
    **Key Capabilities:**
    - Real-time price data and market statistics
    - Order book depth analysis
    - Historical candlestick data for technical analysis  
    - Trade history and market activity
    - Automatic parquet storage for large datasets
    - Symbol validation and filtering
    
    **Data Management:**
    Large responses (>threshold) are automatically stored as Parquet files and the
    file path is returned instead of raw data, optimizing memory usage and enabling
    efficient downstream processing with pandas/polars.
    """

    # Toolkit metadata for enhanced display
    _toolkit_category = "trading"
    _toolkit_type = "data_api" 
    _toolkit_icon = "📈"

    def __init__(
        self,
        symbols: Optional[Sequence[str]] = None,
        default_market_type: MarketType = "spot",
        api_key: str | None = None,
        api_secret: str | None = None,
        data_dir: str | Path = DEFAULT_DATA_DIR,
        parquet_threshold: int = BIG_DATA_THRESHOLD,
        name: str = "binance_toolkit",
        **kwargs: Any,
    ):
        """Initialize the Multi-Market Binance Toolkit.
        
        Args:
            symbols: Optional list of trading symbols to restrict API calls to.
                    If None, all valid symbols from exchanges are allowed.
                    Examples: ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
            default_market_type: Default market type for tools when not specified.
                                Options: "spot", "usdm", "coinm"
            api_key: Binance API key for authenticated requests. If None,
                    reads from BINANCE_API_KEY environment variable.
                    Not required for public endpoints.
            api_secret: Binance API secret for signed requests. If None,
                       reads from BINANCE_API_SECRET environment variable.
                       Not required for public endpoints.
            data_dir: Directory path where Parquet files will be stored for large
                     responses. Defaults to tools/data/binance/
            parquet_threshold: Size threshold in KB for Parquet storage.
                             Responses with JSON payload > threshold KB will be
                             saved to disk and file path returned instead of data.
                             Recommended: 50-200 KB for exchange data (many records).
            name: Name identifier for this toolkit instance
            **kwargs: Additional arguments passed to Toolkit
            
        Raises:
            ValueError: If default_market_type is not supported
            
        Example:
            ```python
            # Basic multi-market toolkit
            toolkit = BinanceToolkit(
                symbols=["BTCUSDT", "ETHUSDT"],
                default_market_type="spot"
            )
            
            # Get spot price
            spot_price = await toolkit.get_current_price("BTCUSDT")
            
            # Get futures price from same toolkit
            futures_price = await toolkit.get_current_price("BTCUSDT", market_type="usdm")
            ```
        """
        # Use enhanced configuration validation from BaseAPIToolkit
        self._validate_configuration_mapping(
            default_market_type, 
            _MARKET_CONFIG, 
            "default_market_type"
        )
        
        self.default_market_type = default_market_type
        self._api_key = api_key or os.getenv("BINANCE_API_KEY")
        self._api_secret = api_secret or os.getenv("BINANCE_API_SECRET")
        
        # Symbol management - using enhanced caching from BaseAPIToolkit
        self._user_symbols = {s.upper() for s in symbols} if symbols else None
        
        # Initialize standard configuration (includes cache system and HTTP client)
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=3600
        )
        
        # Define available tools for this toolkit
        available_tools = [
            self.get_symbol_ticker_change,
            self.get_current_price,
            self.get_order_book,
            self.get_recent_trades,
            self.get_klines,
            self.get_book_ticker,
        ]
        
        # Initialize Toolkit
        super().__init__(name=name, tools=available_tools, **kwargs)
        
        # Initialize BaseDataToolkit helpers
        self._init_data_helpers(
            data_dir=data_dir,
            parquet_threshold=parquet_threshold,
            file_prefix="binance_",
            toolkit_name="binance",
        )
        
        # Initialize statistical analyzer
        self.stats = StatisticalAnalyzer()
        
        logger.debug(
            f"Initialized Multi-Market BinanceToolkit with default market '{default_market_type}' "
            f"and {len(self._user_symbols) if self._user_symbols else 'all'} symbols"
        )

    def _build_binance_auth_headers(self, endpoint_name: str, config: Dict[str, Any]) -> Dict[str, str]:
        """Build authentication headers for Binance endpoints."""
        # Parameters kept for interface compatibility with BaseAPIToolkit
        _ = endpoint_name, config  # Acknowledge parameters
        headers = {}
        if self._api_key:
            headers["X-MBX-APIKEY"] = self._api_key
        return headers

    async def _setup_endpoints(self):
        """Setup HTTP endpoints for all market types using enhanced base class patterns."""
        # Use enhanced multi-endpoint authentication from BaseAPIToolkit
        self._setup_multi_endpoint_authentication(
            endpoint_configs=_MARKET_CONFIG,
            auth_header_builder=self._build_binance_auth_headers
        )
        await self._execute_pending_endpoint_setup()

    async def _make_api_request(
        self, 
        endpoint: str, 
        market_type: str,
        params: Dict[str, Any] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """Make API request directly using HTTP client (no abstraction layers).
        
        Args:
            endpoint: API endpoint path
            market_type: Market type identifier
            params: Query parameters
            signed: Whether request requires signature
            
        Returns:
            dict: Raw JSON response from API
        """
        # Use base class validation for market type
        self._validate_configuration_mapping(market_type, _MARKET_CONFIG, "market_type")
        
        # Ensure endpoints are setup
        if market_type not in self._http_client.get_endpoints():
            await self._setup_endpoints()
        
        config = _MARKET_CONFIG[market_type]
        
        if signed:
            if not (self._api_key and self._api_secret):
                raise ValueError("Signed endpoint requires API key and secret")
            
            params = params or {}
            params["timestamp"] = str(int(time.time() * 1000))
            query_string = urllib.parse.urlencode(params)
            signature = hmac.new(
                self._api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
        
        # Use HTTP client directly
        full_endpoint = f"{config['prefix']}{endpoint}"
        return await self._http_client.get(market_type, full_endpoint, params=params)

    async def _validate_symbol_and_prepare_params(
        self, 
        symbol: str, 
        market_type: str,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate symbol and prepare standardized parameters using base class method.
        
        Args:
            symbol: Trading symbol to validate
            market_type: Market type for validation
            additional_params: Additional parameters to include
            
        Returns:
            dict: Validated parameters
            
        Raises:
            ValueError: If validation fails
        """
        # Use generic base class validation method
        return await self._validate_identifier_and_prepare_params(
            identifier=symbol,
            identifier_type="symbol",
            validation_func=lambda s: self.validate_symbol(s, market_type),
            additional_params={
                "market_type": market_type,
                **(additional_params or {})
            },
            identifier_transform_func=str.upper
        )

    async def _ensure_symbols_loaded(self, market_type: str):
        """Ensure symbol list is loaded for specific market type using enhanced caching."""
        cache_key = f"symbols_{market_type}"
        cached_symbols = self._get_cached_identifiers(cache_key)
        if cached_symbols is None:
            await self.reload_symbols(market_type=market_type)

    async def _resolve_symbol(self, symbol: str, market_type: str) -> Optional[str]:
        """Resolve a symbol to a valid trading symbol using enhanced caching.
        
        Args:
            symbol: Symbol to resolve (e.g., "BTCUSDT", "btcusdt")
            market_type: Market type to validate against
            
        Returns:
            str or None: Valid symbol or None if not found
        """
        await self._ensure_symbols_loaded(market_type)
        
        cache_key = f"symbols_{market_type}"
        valid_symbols = self._get_cached_identifiers(cache_key) or set()
        
        symbol_upper = symbol.upper()
        
        # Direct match
        if symbol_upper in valid_symbols:
            return symbol_upper
        
        # Try fuzzy matching using enhanced base class method
        fuzzy_match = self._find_fuzzy_match(symbol_upper, valid_symbols, threshold=0.8)
        return fuzzy_match

    # =========================================================================
    # Symbol Management Tools
    # =========================================================================
    
    async def reload_symbols(self, market_type: Optional[MarketType] = None) -> Dict[str, Any]:
        """Fetch and cache all tradable symbols from Binance exchange.
        
        Retrieves the complete list of active trading symbols for the specified market
        and caches them for validation. This is automatically called when needed but
        can be manually triggered to refresh the symbol list.
        
        Args:
            market_type: Market to load symbols from. Options:
                        - "spot": Binance Spot Trading
                        - "usdm": USDⓈ-M Futures (USDT-Margined)
                        - "coinm": COIN-M Futures (Coin-Margined)
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Symbol loading result
            
        **Success Response:**
        ```json
        {
            "success": true,
            "symbol_count": 2487,
            "market_type": "spot",
            "market_description": "Binance Spot Trading",
            "fetched_at": 1704067200,
            "sample_symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        }
        ```
        
        **Failure Response:**
        ```json
        {
            "success": false,
            "message": "Failed to reload symbols: Connection timeout",
            "error_type": "symbol_reload_error",
            "market_type": "spot"
        }
        ```
        
        Example Usage:
        ```python
        # Load spot symbols
        result = await toolkit.reload_symbols("spot")
        if result["success"]:
            print(f"Loaded {result['symbol_count']} spot symbols")
            
        # Load futures symbols
        futures_result = await toolkit.reload_symbols("usdm")
        if futures_result["success"]:
            print(f"Loaded {futures_result['symbol_count']} futures symbols")
        ```
        
        Performance:
        - Response time: 1-3 seconds depending on market
        - Rate limit: 1200 requests per minute per market
        - Caching: Results cached until manual reload
        """
        market_type = market_type or self.default_market_type
        
        try:
            # Use standardized API request method
            response_data = await self._make_api_request(_API_ENDPOINTS["exchange_info"], market_type)
            symbols = {s["symbol"] for s in response_data.get("symbols", []) if s.get("status") == "TRADING"}

            # Use enhanced caching from BaseAPIToolkit
            cache_key = f"symbols_{market_type}"
            config = _MARKET_CONFIG[market_type]
            metadata = {
                "market_type": market_type,
                "market_description": config["description"],
                "loaded_at": time.time()
            }
            self._cache_identifiers(cache_key, symbols, metadata)
            
            logger.info(
                f"Loaded {len(symbols)} symbols for {config['description']}"
            )
            
            return self.response_builder.success_response(
                message=f"Successfully loaded {len(symbols)} symbols for {config['description']}",
                symbol_count=len(symbols),
                market_type=market_type,
                market_description=config["description"],
                fetched_at=int(time.time()),
                sample_symbols=list(symbols)[:5] if symbols else []
            )
        except Exception as e:
            logger.error(f"Failed to reload symbols for {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["exchange_info"],
                api_message=f"Failed to reload symbols: {str(e)}",
                market_type=market_type
            )
    
    async def validate_symbol(self, symbol: str, market_type: Optional[MarketType] = None) -> Dict[str, Any]:
        """Validate that a trading symbol is supported and allowed.
        
        Checks if a symbol is:
        1. Listed on the specified Binance market
        2. Allowed by the toolkit's symbol filter (if configured)
        
        Args:
            symbol: Trading pair symbol to validate (case-insensitive)
                   Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            market_type: Market to validate against. Options:
                        - "spot": Traditional spot trading pairs
                        - "usdm": USDT-margined futures contracts  
                        - "coinm": Coin-margined futures contracts
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Validation result with detailed status
            
        **Success Response:**
        ```json
        {
            "success": true,
            "message": "Symbol is valid",
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "market_description": "Binance Spot Trading"
        }
        ```
        
        **Invalid Symbol Response:**
        ```json
        {
            "success": false,
            "message": "Symbol 'INVALID' not found on Binance 'spot' market",
            "symbol": "INVALID",
            "market_type": "spot",
            "error_type": "invalid_symbol",
            "available_count": 2487
        }
        ```
        
        **Not Allowed Response:**
        ```json
        {
            "success": false,
            "message": "Symbol 'ADAUSDT' not in configured allowlist",
            "symbol": "ADAUSDT",
            "market_type": "spot", 
            "error_type": "symbol_not_allowed",
            "allowed_symbols": ["BTCUSDT", "ETHUSDT"]
        }
        ```
        
        Example Usage:
        ```python
        # Validate before trading operations
        validation = await toolkit.validate_symbol("BTCUSDT", "spot")
        if validation["success"]:
            # Proceed with API calls
            price = await toolkit.get_current_price("BTCUSDT", "spot")
        else:
            print(f"Invalid symbol: {validation['message']}")
            
        # Cross-market validation
        spot_valid = await toolkit.validate_symbol("BTCUSDT", "spot")
        futures_valid = await toolkit.validate_symbol("BTCUSDT", "usdm")
        ```
        
        Note:
        This tool automatically loads symbols if not already cached. Different
        markets may have different symbol formats (e.g., spot uses BTCUSDT while
        some futures use BTCUSD_PERP).
        """
        market_type = market_type or self.default_market_type
        await self._ensure_symbols_loaded(market_type)
        
        symbol = symbol.upper()
        config = _MARKET_CONFIG[market_type]
        cache_key = f"symbols_{market_type}"
        valid_symbols = self._get_cached_identifiers(cache_key) or set()
        
        # Check if symbol exists in market
        is_valid = symbol in valid_symbols
        suggestions = []
        
        if not is_valid:
            # Try to find fuzzy matches for suggestions
            fuzzy_match = self._find_fuzzy_match(symbol, valid_symbols, threshold=0.6)
            if fuzzy_match:
                suggestions.append(f"Did you mean '{fuzzy_match}'?")
                
        # Check user symbols filter if configured
        if is_valid and self._user_symbols and symbol not in self._user_symbols:
            return self.response_builder.validation_error_response(
                field_name="symbol",
                field_value=symbol,
                validation_errors=[f"Symbol '{symbol}' not in configured allowlist"],
                symbol=symbol,
                market_type=market_type,
                market_description=config["description"],
                user_symbols_count=len(self._user_symbols),
                suggestions=["Check your symbol allowlist configuration"]
            )
        
        # Use enhanced validation response builder
        return self._build_identifier_validation_response(
            identifier=symbol,
            is_valid=is_valid,
            config_context=f"Binance {market_type} market",
            identifier_type="symbol",
            suggestions=suggestions,
            market_type=market_type,
            market_description=config["description"],
            available_count=len(valid_symbols)
        )

    # =========================================================================
    # Market Data Tools  
    # =========================================================================
    
    async def get_current_price(self, symbol: str, market_type: Optional[MarketType] = None) -> Dict[str, Any]:
        """Get the latest price for a trading symbol.
        
        Fetches the most recent trading price for the specified symbol from the chosen
        Binance market. This provides real-time pricing data updated approximately
        every 100ms across all supported markets.
        
        Args:
            symbol: Trading pair symbol (case-insensitive)
                   Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            market_type: Market to query. Options:
                        - "spot": Current spot trading price
                        - "usdm": USDT-margined futures mark price
                        - "coinm": Coin-margined futures mark price
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Current price data with market context
            
        **Success Response:**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "price": 67342.8,
            "market_type": "spot",
            "market_description": "Binance Spot Trading",
            "fetched_at": 1704067200,
            "currency": "USDT"
        }
        ```
        
        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Symbol 'INVALID' not found on Binance 'spot' market",
            "error_type": "validation_error",
            "symbol": "INVALID",
            "market_type": "spot"
        }
        ```
        
        **API Error Response:**
        ```json
        {
            "success": false,
            "message": "API request failed: Server temporarily unavailable",
            "error_type": "api_error",
            "symbol": "BTCUSDT",
            "market_type": "spot"
        }
        ```
        
        Example Usage:
        ```python
        # Get Bitcoin spot price
        btc_spot = await toolkit.get_current_price("BTCUSDT", "spot")
        if btc_spot["success"]:
            print(f"BTC Spot: ${btc_spot['price']:,.2f}")
            
        # Compare spot vs futures pricing
        btc_futures = await toolkit.get_current_price("BTCUSDT", "usdm")
        if btc_futures["success"]:
            spot_price = btc_spot["price"] 
            futures_price = btc_futures["price"]
            basis = futures_price - spot_price
            print(f"Futures Basis: ${basis:.2f}")
            
        # Monitor multiple symbols
        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
        for symbol in symbols:
            result = await toolkit.get_current_price(symbol, "spot")
            if result["success"]:
                print(f"{symbol}: ${result['price']}")
        ```
        
        **Market-Specific Notes:**
        - **Spot**: Actual trading price from order book
        - **USDⓈ-M Futures**: Mark price used for PnL calculation
        - **COIN-M Futures**: Index price for coin-settled contracts
        
        Performance:
        - Response time: 100-300ms
        - Rate limit: 1200 requests per minute
        - Data freshness: Updated every ~100ms
        """
        try:
            market_type = market_type or self.default_market_type
            
            # Use BaseAPIToolkit for identifier resolution
            resolved_symbol = await self._resolve_symbol(symbol, market_type)
            if not resolved_symbol:
                resolved_symbol = self._resolve_identifier(
                    symbol,
                    identifier_type="symbol",
                    fallback_value=symbol.upper()
                )
            
            # Use consolidated validation and parameter preparation
            params = await self._validate_symbol_and_prepare_params(resolved_symbol, market_type)
            
            # Use standardized API request method
            price_data = await self._make_api_request(
                _API_ENDPOINTS["ticker_price"], 
                params["market_type"], 
                {"symbol": params["symbol"]}
            )
            
            # Create enriched response data
            config = _MARKET_CONFIG[params["market_type"]]
            
            # Extract quote currency properly - handle different quote assets
            symbol = params["symbol"]
            quote_currency = "UNKNOWN"
            if symbol.endswith("USDT"):
                quote_currency = "USDT"
            elif symbol.endswith("USDC"):
                quote_currency = "USDC"
            elif symbol.endswith("BTC"):
                quote_currency = "BTC"
            elif symbol.endswith("ETH"):
                quote_currency = "ETH"
            elif symbol.endswith("BNB"):
                quote_currency = "BNB"
            else:
                # For other cases, try to extract the last 3-4 characters as quote currency
                # Common patterns: XXX/YYY where YYY is 3-4 chars
                for quote_len in [4, 3]:
                    if len(symbol) > quote_len:
                        quote_currency = symbol[-quote_len:]
                        break
                        
            response_data = {
                "symbol": params["symbol"],
                "price": float(price_data["price"]),
                "market_type": params["market_type"],
                "market_description": config["description"], 
                "fetched_at": int(time.time()),
                "currency": quote_currency
            }
            
            # Build analysis using helper method
            analysis = {
                "price_trend": self.stats.classify_trend_from_change(0),  # Single price point, no trend
                "market_type_features": config.get("features", []),
                "currency": quote_currency
            }
            
            # Use ResponseBuilder for standardized success response with analysis
            return self.response_builder.success_response(
                data=response_data,
                symbol=params["symbol"],
                market_type=params["market_type"],
                endpoint=_API_ENDPOINTS["ticker_price"],
                analysis=analysis
            )
            
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol} on {market_type or self.default_market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["ticker_price"],
                api_message=f"Failed to get current price: {str(e)}",
                symbol=symbol,
                market_type=market_type or self.default_market_type
            )

    async def get_symbol_ticker_change(
        self, 
        symbol: str, 
        window_size: str = "24h",
        market_type: Optional[MarketType] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive price change statistics for a symbol over a rolling window.

        Retrieves detailed price movement statistics including price changes,
        percentage changes, high/low prices, volume, and trade count over the
        specified rolling window period. For spot markets, supports various rolling window
        sizes. For futures markets, only 24 hours is supported.

        Args:
            symbol: Trading pair symbol (case-insensitive)
                Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            window_size: Rolling window size in Binance API format.
                Supported for spot: "1m" to "59m" (minutes), "1h" to "23h" (hours), "1d" to "7d" (days)
                Supported for usdm/coinm: "24h" only (default)
                Examples: "1h", "4h", "24h", "7d"
                Note: Units cannot be combined (e.g. "1d2h" is not allowed)
            market_type: Market to query. Options:
                - "spot": Spot trading statistics (supports rolling window)
                - "usdm": USDT-margined futures statistics (24h only)
                - "coinm": Coin-margined futures statistics (24h only)
                If None, uses toolkit's default_market_type

        Returns:
            dict: Comprehensive ticker statistics

        **Success Response:**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "data": {
                "symbol": "BTCUSDT",
                "priceChange": "1250.50000000",
                "priceChangePercent": "1.89",
                "weightedAvgPrice": "66825.45123456",
                "openPrice": "66000.00000000",
                "highPrice": "68000.00000000", 
                "lowPrice": "65500.00000000",
                "lastPrice": "67250.50000000",
                "volume": "15234.25000000",
                "quoteVolume": "1023456789.12345678",
                "openTime": "2024-01-01T00:00:00Z",
                "closeTime": "2024-01-02T00:00:00Z",
                "firstId": 12345678,
                "lastId": 87654321,
                "count": 425234
            },
            "window_size": "24h",
            "analysis": {
                "trend": "bullish",
                "volatility": "moderate",
                "volume_rating": "high"
            }
        }
        ```

        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Symbol 'INVALID' not found on Binance 'spot' market",
            "error_type": "validation_error",
            "symbol": "INVALID",
            "market_type": "spot"
        }
        ```

        **Unsupported Period Response:**
        ```json
        {
            "success": false,
            "message": "Unsupported window size '200h' for spot market",
            "error_type": "unsupported_period",
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "requested_window_size": "200h",
            "supported_formats": ["1m-59m", "1h-23h", "1d-7d"]
        }
        ```

        Example Usage:
        ```python
        # Get 4h Bitcoin statistics (spot)
        stats = await toolkit.get_symbol_ticker_change("BTCUSDT", window_size="4h", market_type="spot")
        if stats["success"]:
            data = stats["data"]
            print(f"BTC 4h Change: {float(data['priceChangePercent']):+.2f}%")

        # Get 3 day statistics for spot
        stats = await toolkit.get_symbol_ticker_change("BTCUSDT", window_size="3d", market_type="spot")
        if stats["success"]:
            print(f"BTC 3d Change: {float(stats['data']['priceChangePercent']):+.2f}%")

        # Get 24h statistics for futures
        stats = await toolkit.get_symbol_ticker_change("BTCUSDT", window_size="24h", market_type="usdm")
        if stats["success"]:
            print(f"BTCUSDT USDM 24h Change: {float(stats['data']['priceChangePercent']):+.2f}%")
        ```

        **Data Field Explanations:**
        - `priceChange`: Absolute price change in base currency
        - `priceChangePercent`: Percentage change over the period
        - `weightedAvgPrice`: Volume-weighted average price (VWAP)
        - `volume`: Base asset trading volume
        - `quoteVolume`: Quote asset trading volume (typically USDT value)
        - `count`: Number of individual trades executed
        - `openTime`/`closeTime`: ISO8601 timestamp strings

        **Market-Specific Insights:**
        - **Spot**: Physical trading volume and price discovery (supports rolling window)
        - **USDⓈ-M Futures**: Leveraged trading activity and funding rates (24h only)
        - **COIN-M Futures**: Traditional futures with physical settlement (24h only)

        Performance:
        - Response time: 150-400ms
        - Rate limit: 1200 requests per minute
        - Update frequency: Real-time tick data aggregation
        """
        market_type = market_type or self.default_market_type

        # Validate and normalize window_size parameter
        if not window_size or not isinstance(window_size, str) or len(window_size.strip()) == 0:
            window_size = "1d"  # Fallback to safe default (API expects "1d" format, not "24h")
        else:
            window_size = window_size.strip()
            # Convert "24h" to "1d" for compatibility with rolling window API
            if window_size == "24h":
                window_size = "1d"

        # Use consolidated validation
        try:
            params = await self._validate_symbol_and_prepare_params(symbol, market_type)
        except ValueError as e:
            return self.response_builder.validation_error_response(
                field_name="symbol",
                field_value=symbol,
                validation_errors=[str(e)],
                symbol=symbol,
                market_type=market_type
            )

        # Debug: Log the market_type to see what's happening
        logger.debug(f"get_symbol_ticker_change: market_type='{market_type}', window_size='{window_size}'")
        
        if market_type == "spot":
            # For spot market, use rolling window ticker endpoint with windowSize parameter
            api_params = {
                "symbol": params["symbol"],
                "windowSize": window_size
            }
            endpoint = "/ticker"
        else:
            # For usdm/coinm, only 24h is supported
            if window_size != "24h":
                return self.response_builder.error_response(
                    message=f"Window size '{window_size}' not supported for {market_type} market. Only '24h' is supported.",
                    error_type="unsupported_period",
                    details={
                        "symbol": symbol,
                        "market_type": market_type,
                        "requested_window_size": window_size,
                        "supported_window_sizes": ["24h"]
                    }
                )
            api_params = {"symbol": params["symbol"]}
            endpoint = _API_ENDPOINTS["ticker_24hr"]

        try:
            data = await self._make_api_request(endpoint, market_type, api_params)
            
            # Handle response format differences using DataValidator
            validation = DataValidator.validate_structure(
                data, 
                expected_type=(list, dict),
                required_fields=None  # Will validate structure without specific field requirements
            )
            
            if not validation["valid"]:
                logger.warning(f"Unexpected ticker data structure: {validation['errors']}")
            
            # Normalize response format
            if isinstance(data, list):
                data = data[0] if data else {}
            elif isinstance(data, dict) and "response" in data:
                if isinstance(data["response"], list):
                    data = data["response"][0] if data["response"] else {}
                else:
                    data = data["response"]



            # Convert timestamp fields
            for field in ["openTime", "closeTime"]:
                if field in data and data[field] is not None:
                    data[field] = DataHTTPClient.unix_to_iso8601(data[field])

            # Add basic analysis using base class helpers
            change_pct = float(data.get("priceChangePercent", 0))
            volume = float(data.get("volume", 0))

            analysis = {
                "trend": self.stats.classify_trend_from_change(change_pct),
                "volatility": self.stats.classify_volatility_from_change(change_pct),
                "volume_rating": "high" if volume > 1000 else "moderate" if volume > 100 else "low"
            }

            return self.response_builder.success_response(
                data=data,
                symbol=params["symbol"],
                market_type=market_type,
                window_size=window_size,
                analysis=analysis
            )
        except Exception as e:
            logger.error(f"Failed to get ticker change for {symbol} on {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["ticker_24hr"],
                api_message=f"Failed to get ticker statistics: {str(e)}",
                symbol=symbol,
                market_type=market_type
            )

    async def get_order_book(
        self, 
        symbol: str, 
        limit: int = 100,
        market_type: Optional[MarketType] = None
    ) -> Dict[str, Any]:
        """Get order book depth showing pending buy and sell orders.
        
        Retrieves the current order book with bids (buy orders) and asks (sell orders)
        at various price levels. Essential for analyzing market depth, liquidity,
        and potential price impact of large trades.
        
        Args:
            symbol: Trading pair symbol (case-insensitive)
                   Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            limit: Number of price levels to return for both bids and asks
                  Valid values: 5, 10, 20, 50, 100, 500, 1000, 5000
                  Default: 100
            market_type: Market to query. Options:
                        - "spot": Spot order book with immediate settlement
                        - "usdm": USDT-margined futures order book
                        - "coinm": Coin-margined futures order book
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Order book data or file path for large responses
            
        **Success Response (Small Order Book):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "limit": 100,
            "size": 200,
            "data": {
                "lastUpdateId": 12345678901,
                "bids": [
                    ["67200.10", "0.50000000"],
                    ["67200.00", "1.25000000"],
                    ["67199.90", "0.75000000"]
                ],
                "asks": [
                    ["67200.20", "0.30000000"],
                    ["67200.30", "0.85000000"],
                    ["67200.40", "1.10000000"]
                ]
            },
            "analysis": {
                "spread": 0.10,
                "spread_pct": 0.000149,
                "bid_depth": 2.50,
                "ask_depth": 2.25,
                "imbalance_ratio": 1.11
            }
        }
        ```
        
        **Success Response (Large Order Book - Stored as Parquet):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "limit": 5000,
            "size": 10000,
            "file_path": "/path/to/data/binance/order_book_BTCUSDT_spot_5000_1704067200.parquet",
            "note": "Large order book stored as Parquet file",
            "parquet_info": {
                "columns": ["side", "price", "quantity", "price_level"],
                "format": "pandas_compatible",
                "compression": "snappy"
            }
        }
        ```
        
        Example Usage:
        ```python
        # Analyze market depth for trading decisions
        order_book = await toolkit.get_order_book("BTCUSDT", limit=100, market_type="spot")
        if order_book["success"]:
            if "data" in order_book:
                # Small order book - analyze directly (data is now structured list)
                book_data = order_book["data"]
                bids = [item for item in book_data if item['side'] == 'bid']
                asks = [item for item in book_data if item['side'] == 'ask']
                
                best_bid = max(bids, key=lambda x: x['price'])['price'] if bids else 0
                best_ask = min(asks, key=lambda x: x['price'])['price'] if asks else 0
                spread = best_ask - best_bid
                
                print(f"Best Bid: ${best_bid:,.2f}")
                print(f"Best Ask: ${best_ask:,.2f}")
                print(f"Spread: ${spread:.2f} ({spread/best_bid*100:.3f}%)")
                
                # Calculate depth at 1% price impact
                target_price = best_ask * 1.01
                total_depth = sum(item['quantity'] for item in asks if item['price'] <= target_price)
                print(f"Ask depth to +1%: {total_depth:.4f} BTC")
                
            elif "file_path" in order_book:
                # Large order book - load from Parquet
                import pandas as pd
                df = pd.read_parquet(order_book["file_path"])
                print(f"Loaded deep order book: {len(df)} levels")
                
                # Analyze large order book
                bids_df = df[df['side'] == 'bid'].sort_values('price', ascending=False)
                asks_df = df[df['side'] == 'ask'].sort_values('price', ascending=True)
                
        # Compare liquidity across markets
        markets = ["spot", "usdm"]
        for market in markets:
            book = await toolkit.get_order_book("BTCUSDT", limit=20, market_type=market)
            if book["success"] and "data" in book:
                spread = book["analysis"]["spread"]
                print(f"{market.upper()} spread: ${spread:.2f}")
        ```
        
        **Order Book Structure:**
        - `bids`: Buy orders sorted by price (highest first)
        - `asks`: Sell orders sorted by price (lowest first)
        - Each entry: `[price, quantity]` where both are strings
        - `lastUpdateId`: Sequence number for real-time updates
        
        **Analysis Fields:**
        - `spread`: Price difference between best bid and ask
        - `spread_pct`: Spread as percentage of mid-price
        - `bid_depth`: Total quantity in top bid levels
        - `ask_depth`: Total quantity in top ask levels
        - `imbalance_ratio`: Bid depth / ask depth ratio
        
        **Market Insights:**
        - **Tight spreads**: High liquidity, efficient price discovery
        - **Large depth**: Can absorb big orders without slippage
        - **Bid/ask imbalance**: Potential directional pressure
        
        Performance:
        - Response time: 200-500ms (depends on limit)
        - Rate limit: 1200 requests per minute
        - Memory: Auto-managed via Parquet storage
        """
        market_type = market_type or self.default_market_type
        
        # Use consolidated validation
        try:
            params = await self._validate_symbol_and_prepare_params(symbol, market_type)
        except ValueError as e:
            return self.response_builder.validation_error_response(
                field_name="symbol",
                field_value=symbol,
                validation_errors=[str(e)],
                symbol=symbol,
                market_type=market_type
            )
        
        try:
            data = await self._make_api_request(_API_ENDPOINTS["order_book"], market_type, {
                "symbol": params["symbol"],
                "limit": str(limit)
            })
            
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            size = len(bids) + len(asks)
            
            # Validate data structure before processing
            if bids and asks:
                if not isinstance(bids[0], (list, tuple)) or not isinstance(asks[0], (list, tuple)):
                    logger.error(f"Unexpected data format - bids[0]: {type(bids[0])}, asks[0]: {type(asks[0])}")
                    return self.response_builder.error_response(
                        message="Invalid order book data format received from API",
                        error_type="data_format_error",
                        symbol=symbol,
                        market_type=market_type
                    )
            
            base_response = {
                "success": True,
                "symbol": params["symbol"],
                "market_type": market_type,
                "limit": limit,
                "size": size
            }
            
            # Calculate basic analysis
            analysis = {}
            if bids and asks:
                try:
                    # Binance API returns bids/asks as arrays of [price, quantity] strings
                    best_bid = float(bids[0][0])  # First bid price
                    best_ask = float(asks[0][0])  # First ask price
                    spread = best_ask - best_bid
                    mid_price = (best_bid + best_ask) / 2
                    
                    # Calculate depth for top 5 levels
                    bid_depth = sum(float(qty) for price, qty in bids[:5])
                    ask_depth = sum(float(qty) for price, qty in asks[:5])
                except (IndexError, ValueError, TypeError, KeyError) as e:
                    logger.error(f"Error parsing order book data: {e}. First bid: {bids[0] if bids else 'None'}, First ask: {asks[0] if asks else 'None'}")
                    # Log more details about the data structure
                    if bids:
                        logger.error(f"Bid data types: {[type(item) for item in bids[:3]]}")
                    if asks:
                        logger.error(f"Ask data types: {[type(item) for item in asks[:3]]}")
                    # Set default values if parsing fails
                    best_bid = best_ask = spread = mid_price = bid_depth = ask_depth = 0
                
                analysis = {
                    "spread": spread,
                    "spread_pct": spread / mid_price if mid_price > 0 else 0,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "imbalance_ratio": bid_depth / ask_depth if ask_depth > 0 else 0
                }
            
            # Convert to structured format for Parquet storage
            book_data = []
            try:
                for price, qty in bids:
                    book_data.append({"side": "bid", "price": float(price), "quantity": float(qty)})
                for price, qty in asks:
                    book_data.append({"side": "ask", "price": float(price), "quantity": float(qty)})
            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Error processing bid/ask data for Parquet storage: {e}")
                logger.error(f"Sample bid: {bids[0] if bids else 'None'}, Sample ask: {asks[0] if asks else 'None'}")
                if bids:
                    logger.error(f"Bid data sample types: {[type(item) for item in bids[:2]]}")
                if asks:
                    logger.error(f"Ask data sample types: {[type(item) for item in asks[:2]]}")
                # Fallback: create minimal book_data
                book_data = []
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "order_book", params["symbol"], market_type, {"limit": limit}, 
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=book_data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large order book stored as Parquet file",
                **base_response,
                analysis=analysis
            )
        except Exception as e:
            logger.error(f"Failed to get order book for {symbol} on {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["order_book"],
                api_message=f"Failed to get order book: {str(e)}",
                symbol=symbol,
                market_type=market_type,
                limit=limit
            )

    async def get_recent_trades(
        self, 
        symbol: str, 
        limit: int = 500,
        market_type: Optional[MarketType] = None
    ) -> Dict[str, Any]:
        """Get recent public trades showing actual market transactions.
        
        Retrieves the most recent executed trades for the specified symbol,
        providing insights into market activity, trade sizes, and price trends.
        Essential for analyzing market momentum and trading patterns.
        
        Args:
            symbol: Trading pair symbol (case-insensitive)
                   Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            limit: Number of recent trades to return (max: 1000, default: 500)
            market_type: Market to query. Options:
                        - "spot": Spot market trades with immediate settlement
                        - "usdm": USDT-margined futures trades
                        - "coinm": Coin-margined futures trades  
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Recent trades data or file path for large responses
            
        **Success Response (Small Dataset):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "limit": 500,
            "count": 500,
            "data": [
                {
                    "id": 123456789,
                    "price": "67250.50000000",
                    "qty": "0.01250000",
                    "quoteQty": "840.63125000", 
                    "time": 1704067200000,
                    "isBuyerMaker": false,
                    "isBestMatch": true
                }
            ],
            "analysis": {
                "avg_trade_size": 0.0245,
                "total_volume": 12.25,
                "price_trend": "bullish",
                "buyer_maker_ratio": 0.45,
                "trade_frequency": "high"
            }
        }
        ```
        
        **Success Response (Large Dataset - Stored as Parquet):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "usdm", 
            "limit": 1000,
            "count": 1000,
            "file_path": "/path/to/data/binance/trades_BTCUSDT_usdm_1000_1704067200.parquet",
            "note": "Large trade dataset stored as Parquet file",
            "analysis": {
                "avg_trade_size": 0.156,
                "total_volume": 156.8,
                "dominant_side": "buy",
                "price_range": [67180.5, 67340.2]
            }
        }
        ```
        
        Example Usage:
        ```python
        # Analyze recent trading activity
        trades = await toolkit.get_recent_trades("BTCUSDT", limit=100, market_type="spot")
        if trades["success"]:
            if "data" in trades:
                # Analyze trade data directly
                trade_data = trades["data"]
                total_volume = sum(float(t["qty"]) for t in trade_data)
                buy_volume = sum(float(t["qty"]) for t in trade_data if not t["isBuyerMaker"])
                sell_volume = total_volume - buy_volume
                
                print(f"Recent Trading Activity ({len(trade_data)} trades):")
                print(f"  Total Volume: {total_volume:.4f} BTC")
                print(f"  Buy Volume: {buy_volume:.4f} BTC ({buy_volume/total_volume*100:.1f}%)")
                print(f"  Sell Volume: {sell_volume:.4f} BTC ({sell_volume/total_volume*100:.1f}%)")
                
                # Analyze price momentum
                prices = [float(t["price"]) for t in trade_data]
                if len(prices) >= 10:
                    recent_avg = sum(prices[:10]) / 10
                    older_avg = sum(prices[-10:]) / 10
                    momentum = "📈 Bullish" if recent_avg > older_avg else "📉 Bearish"
                    print(f"  Price Momentum: {momentum}")
                    
            elif "file_path" in trades:
                # Load large dataset from Parquet
                import pandas as pd
                df = pd.read_parquet(trades["file_path"])
                
                # Advanced analysis on large dataset
                df["price"] = df["price"].astype(float)
                df["qty"] = df["qty"].astype(float)
                
                # Volume-weighted average price (VWAP)
                df["notional"] = df["price"] * df["qty"]
                vwap = df["notional"].sum() / df["qty"].sum()
                print(f"VWAP: ${vwap:,.2f}")
                
                # Trade size distribution
                large_trades = df[df["qty"] > df["qty"].quantile(0.9)]
                print(f"Large trades (>90th percentile): {len(large_trades)}")
                
        # Compare trading activity across markets
        markets = ["spot", "usdm"]
        for market in markets:
            result = await toolkit.get_recent_trades("BTCUSDT", limit=50, market_type=market)
            if result["success"] and "analysis" in result:
                freq = result["analysis"]["trade_frequency"]
                avg_size = result["analysis"]["avg_trade_size"]
                print(f"{market.upper()}: {freq} frequency, avg {avg_size:.4f} BTC")
        ```
        
        **Trade Data Fields:**
        - `id`: Unique trade identifier for deduplication
        - `price`: Execution price in quote currency
        - `qty`: Base asset quantity traded
        - `quoteQty`: Quote asset value (price × qty)
        - `time`: Trade execution timestamp (milliseconds)
        - `isBuyerMaker`: true if buyer placed limit order (market taker was seller)
        - `isBestMatch`: true if trade was from the best price match
        
        **Analysis Insights:**
        - `buyer_maker_ratio`: Proportion of trades where buyer was maker (passive)
        - `price_trend`: Directional bias based on recent vs older trades
        - `trade_frequency`: High/medium/low based on time intervals
        - `avg_trade_size`: Mean quantity per trade
        
        **Market Behavior Patterns:**
        - **High buyer_maker_ratio**: Market showing buying pressure via limit orders
        - **Low buyer_maker_ratio**: Aggressive buying via market orders
        - **Large avg_trade_size**: Institutional activity or whale movements
        - **High frequency**: Active trading environment with tight spreads
        
        Performance:
        - Response time: 200-600ms (depends on limit)
        - Rate limit: 1200 requests per minute
        - Data freshness: Real-time trade feed
        """
        market_type = market_type or self.default_market_type
        
        # Use consolidated validation
        try:
            params = await self._validate_symbol_and_prepare_params(symbol, market_type)
        except ValueError as e:
            return self.response_builder.validation_error_response(
                field_name="symbol",
                field_value=symbol,
                validation_errors=[str(e)],
                symbol=symbol,
                market_type=market_type
            )
        
        try:
            data = await self._make_api_request("/trades", market_type, {
                "symbol": params["symbol"],
                "limit": str(limit)
            })
            
            base_response = {
                "success": True,
                "symbol": params["symbol"],
                "market_type": market_type,
                "limit": limit,
                "count": len(data)
            }
            
            # Validate trade data structure using DataValidator
            if data:
                trade_validation = DataValidator.validate_structure(
                    data,
                    expected_type=list,
                    required_fields=["qty", "price", "isBuyerMaker"]
                )
                
                if not trade_validation["valid"]:
                    logger.warning(f"Trade data validation failed: {trade_validation['errors']}")
            
            # Calculate analysis
            analysis = {}
            if data:
                # Additional validation for numeric data
                for trade in data[:5]:  # Validate first 5 trades as sample
                    numeric_validation = DataValidator.validate_numeric_data(
                        [trade.get("qty"), trade.get("price")], 
                        field_name="trade_amounts"
                    )
                    if not numeric_validation["valid"]:
                        logger.warning(f"Trade numeric validation failed: {numeric_validation['errors']}")
                        break
                
                volumes = [float(t["qty"]) for t in data]
                prices = [float(t["price"]) for t in data]
                buyer_maker_count = sum(1 for t in data if t["isBuyerMaker"])
                
                # Use StatisticalAnalyzer for comprehensive volume analysis
                volume_stats = self.stats.calculate_volume_statistics(_np.array(volumes), _np.array(prices))
                price_stats = self.stats.calculate_price_statistics(_np.array(prices))
                
                analysis = {
                    "avg_trade_size": volume_stats.get("avg_daily_volume", sum(volumes) / len(volumes)),
                    "total_volume": sum(volumes),
                    "buyer_maker_ratio": buyer_maker_count / len(data),
                    "price_range": [price_stats.get("min", min(prices)), price_stats.get("max", max(prices))],
                    "trade_frequency": "high" if len(data) >= limit * 0.8 else "moderate",
                    "volume_volatility": volume_stats.get("volume_volatility", 0),
                    "volume_trend": volume_stats.get("volume_trend", "stable"),
                    "price_statistics": price_stats
                }
                
                # Use StatisticalAnalyzer for trend analysis
                if len(prices) >= 20:
                    trend_analysis = self.stats.analyze_price_trends(_np.array(prices), window=10)
                    analysis["price_trend"] = trend_analysis.get("trend_direction", "sideways")
                    analysis["momentum_pct"] = trend_analysis.get("momentum_pct", 0)
            
            filename_template = FileNameGenerator.generate_market_data_filename(
                "trades", params['symbol'], market_type, 
                file_prefix=self._file_prefix
            )
            
            return self.response_builder.build_data_response_with_storage(
                data=data,
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large trade dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
        except Exception as e:
            logger.error(f"Failed to get recent trades for {symbol} on {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint="/trades",
                api_message=f"Failed to get recent trades: {str(e)}",
                symbol=symbol,
                market_type=market_type,
                limit=limit
            )

    async def get_klines(
        self, 
        symbol: str, 
        interval: str = "1h",
        limit: int = 500,
        market_type: Optional[MarketType] = None
    ) -> Dict[str, Any]:
        """Get candlestick/K-line data for technical analysis and charting.
        
        Retrieves historical OHLCV (Open, High, Low, Close, Volume) candlestick data
        for technical analysis, trend identification, and algorithmic trading strategies.
        Essential for backtesting and pattern recognition.
        
        Args:
            symbol: Trading pair symbol (case-insensitive)
                   Examples: "BTCUSDT", "ETHBTC", "ADAUSDT"
            interval: Candlestick time interval. Supported values:
                     - Seconds: "1s"
                     - Minutes: "1m", "3m", "5m", "15m", "30m"
                     - Hours: "1h", "2h", "4h", "6h", "8h", "12h"
                     - Days: "1d", "3d"
                     - Weeks: "1w"
                     - Months: "1M"
                     Default: "1h"
            limit: Number of candlesticks to return (max: 1000, default: 500)
            market_type: Market to query. Options:
                        - "spot": Spot trading candlesticks
                        - "usdm": USDT-margined futures candlesticks
                        - "coinm": Coin-margined futures candlesticks
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Candlestick data or file path for large datasets
            
        **Success Response (Small Dataset):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "interval": "1h",
            "limit": 500,
            "count": 500,
            "data": [
                {
                    "open_time": 1704063600000,
                    "open": "67000.00000000",
                    "high": "67500.50000000",
                    "low": "66800.25000000", 
                    "close": "67250.75000000",
                    "volume": "125.45000000",
                    "close_time": 1704067199999,
                    "quote_asset_volume": "8456789.12345678",
                    "number_of_trades": 1542,
                    "taker_buy_base_asset_volume": "65.25000000",
                    "taker_buy_quote_asset_volume": "4398765.43210987"
                }
            ],
            "technical_analysis": {
                "trend": "bullish",
                "volatility": "moderate",
                "recent_high": 67500.50,
                "recent_low": 66800.25,
                "avg_volume": 125.45,
                "price_change_pct": 0.374
            }
        }
        ```
        
        **Success Response (Large Dataset - Stored as Parquet):**
        ```json
        {
            "success": true,
            "symbol": "BTCUSDT",
            "market_type": "spot",
            "interval": "1m",
            "limit": 1000,
            "count": 1000,
            "file_path": "/path/to/data/binance/klines_BTCUSDT_spot_1m_1000_1704067200.parquet",
            "note": "Large candlestick dataset stored as Parquet file",
            "technical_analysis": {
                "timeframe": "short_term",
                "data_points": 1000,
                "coverage_hours": 16.67
            }
        }
        ```
        
        Example Usage:
        ```python
        # Technical analysis with hourly data
        klines = await toolkit.get_klines("BTCUSDT", interval="1h", limit=100, market_type="spot")
        if klines["success"]:
            if "data" in klines:
                # Calculate technical indicators
                candles = klines["data"]
                closes = [float(c["close"]) for c in candles]
                highs = [float(c["high"]) for c in candles]
                lows = [float(c["low"]) for c in candles]
                volumes = [float(c["volume"]) for c in candles]
                
                # Simple Moving Average (20 periods)
                if len(closes) >= 20:
                    sma_20 = sum(closes[-20:]) / 20
                    current_price = closes[-1]
                    
                    print(f"Current Price: ${current_price:,.2f}")
                    print(f"SMA(20): ${sma_20:,.2f}")
                    
                    if current_price > sma_20:
                        print("📈 Price above SMA20 - Bullish signal")
                    else:
                        print("📉 Price below SMA20 - Bearish signal")
                
                # Support/Resistance levels
                recent_high = max(highs[-10:])
                recent_low = min(lows[-10:])
                print(f"Recent Range: ${recent_low:,.2f} - ${recent_high:,.2f}")
                
                # Volume analysis
                avg_volume = sum(volumes[-10:]) / 10
                latest_volume = volumes[-1]
                volume_ratio = latest_volume / avg_volume
                
                if volume_ratio > 1.5:
                    print("🔊 High volume - Strong conviction")
                elif volume_ratio < 0.5:
                    print("🔇 Low volume - Weak momentum")
                    
            elif "file_path" in klines:
                # Advanced analysis with large dataset
                import pandas as pd
                df = pd.read_parquet(klines["file_path"])
                
                # Convert to numeric for calculations
                df["close"] = df["close"].astype(float)
                df["high"] = df["high"].astype(float)
                df["low"] = df["low"].astype(float)
                df["volume"] = df["volume"].astype(float)
                
                # Calculate Bollinger Bands
                df["sma_20"] = df["close"].rolling(20).mean()
                df["std_20"] = df["close"].rolling(20).std()
                df["bb_upper"] = df["sma_20"] + (df["std_20"] * 2)
                df["bb_lower"] = df["sma_20"] - (df["std_20"] * 2)
                
                latest = df.iloc[-1]
                if latest["close"] > latest["bb_upper"]:
                    print("🚀 Price above Bollinger Band - Potential overbought")
                elif latest["close"] < latest["bb_lower"]:
                    print("💥 Price below Bollinger Band - Potential oversold")
                    
        # Multi-timeframe analysis
        timeframes = [("5m", "short"), ("1h", "medium"), ("1d", "long")]
        for interval, term in timeframes:
            result = await toolkit.get_klines("BTCUSDT", interval=interval, limit=20, market_type="spot")
            if result["success"] and "technical_analysis" in result:
                trend = result["technical_analysis"]["trend"]
                print(f"{term.title()}-term ({interval}): {trend}")
        ```
        
        **Candlestick Data Fields:**
        - `open_time`: Candle start time (milliseconds since epoch)
        - `open`: Opening price of the period
        - `high`: Highest price during the period
        - `low`: Lowest price during the period
        - `close`: Closing price of the period
        - `volume`: Base asset volume traded
        - `close_time`: Candle end time (milliseconds since epoch)
        - `quote_asset_volume`: Quote asset volume (USDT value)
        - `number_of_trades`: Number of trades in the period
        - `taker_buy_*`: Volumes from market buy orders (aggressive buyers)
        
        **Technical Analysis Applications:**
        - **Trend Analysis**: Moving averages, trend lines
        - **Support/Resistance**: Key price levels and ranges
        - **Volatility**: Bollinger Bands, ATR calculations
        - **Momentum**: RSI, MACD, volume indicators
        - **Pattern Recognition**: Candlestick patterns, chart formations
        
        **Interval Selection Guide:**
        - **1m-5m**: Scalping, high-frequency trading
        - **15m-1h**: Day trading, short-term analysis
        - **4h-1d**: Swing trading, medium-term trends
        - **1w-1M**: Position trading, long-term analysis
        
        **Market-Specific Insights:**
        - **Spot**: Physical trading patterns, actual demand/supply
        - **USDⓈ-M Futures**: Leveraged activity, funding rate impacts
        - **COIN-M Futures**: Traditional futures behavior, basis convergence
        
        Performance:
        - Response time: 300-800ms (depends on interval and limit)
        - Rate limit: 1200 requests per minute
        - Historical coverage: Several years for most intervals
        """
        market_type = market_type or self.default_market_type
        
        # Use consolidated validation
        try:
            params = await self._validate_symbol_and_prepare_params(symbol, market_type)
        except ValueError as e:
            return self.response_builder.validation_error_response(
                field_name="symbol",
                field_value=symbol,
                validation_errors=[str(e)],
                symbol=symbol,
                market_type=market_type
            )
        
        try:
            api_params = {
                "symbol": params["symbol"],
                "interval": interval,
                "limit": str(limit)
            }
            raw_data = await self._make_api_request(_API_ENDPOINTS["klines"], market_type, api_params)
            
            # Convert to structured format
            columns = [
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
            ]
            
            df = _pd.DataFrame(raw_data, columns=columns)
            df = df.drop(columns=["ignore"])
            structured_data = df.to_dict(orient="records")
            
            base_response = {
                "success": True,
                "symbol": params["symbol"],
                "market_type": market_type,
                "interval": interval,
                "limit": limit,
                "count": len(structured_data)
            }
            
            # Use generic analysis orchestration from StatisticalAnalyzer
            analysis = {}
            if structured_data:
                # Validate OHLCV data structure using DataValidator
                ohlcv_validation = DataValidator.validate_ohlcv_fields(structured_data)
                if not ohlcv_validation["valid"]:
                    logger.warning(f"OHLCV data validation failed: {ohlcv_validation['errors']}")
                
                # Validate timestamps in kline data
                timestamp_validation = DataValidator.validate_timestamps(
                    [c.get("open_time") for c in structured_data[:5]]  # Sample first 5
                )
                if not timestamp_validation["valid"]:
                    logger.warning(f"Kline timestamp validation failed: {timestamp_validation['errors']}")
                
                closes = _np.array([float(c["close"]) for c in structured_data])
                highs = _np.array([float(c["high"]) for c in structured_data])
                lows = _np.array([float(c["low"]) for c in structured_data])
                volumes = _np.array([float(c["volume"]) for c in structured_data])
                
                if len(closes) >= 2:
                    # Use generic analysis orchestration
                    analysis = self.stats.build_analysis_report(
                        prices=closes,
                        volumes=volumes,
                        analysis_types=["price_stats", "returns", "volatility", "technical", "volume", "trends"]
                    )
                    
                    # Add klines-specific metrics
                    analysis["klines_specifics"] = {
                        "recent_high": float(_np.max(highs[-10:]) if len(highs) >= 10 else _np.max(highs)),
                        "recent_low": float(_np.min(lows[-10:]) if len(lows) >= 10 else _np.min(lows)),
                        "avg_volume": float(_np.mean(volumes)),
                        "data_quality": "complete" if len(closes) == len(volumes) else "partial"
                    }
            
            # Enhance analysis for large datasets
            if analysis:
                analysis.update({
                    "timeframe": "short_term" if "m" in interval else "medium_term" if "h" in interval else "long_term",
                    "data_points": len(structured_data),
                })
            
            # Use standardized data response builder
            filename_template = FileNameGenerator.generate_data_filename(
                "klines", params["symbol"], market_type, {"interval": interval, "limit": limit},
                file_prefix=self._file_prefix
            )
            
            response = self.response_builder.build_data_response_with_storage(
                data=df,  # Use DataFrame for parquet storage
                storage_threshold=self._parquet_threshold,
                storage_callback=lambda data, filename: self._store_parquet(data, filename),
                filename_template=filename_template,
                large_data_note="Large candlestick dataset stored as Parquet file",
                **base_response,
                analysis=analysis
            )
            
            # Replace analysis key name for backwards compatibility
            if "analysis" in response:
                response["technical_analysis"] = response.pop("analysis")
            
            return response
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol} on {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["klines"],
                api_message=f"Failed to get candlestick data: {str(e)}",
                symbol=symbol,
                market_type=market_type,
                interval=interval,
                limit=limit
            )

    async def get_book_ticker(
        self, 
        symbols: List[str],
        market_type: Optional[MarketType] = None
    ) -> Dict[str, Any]:
        """Get best bid/ask prices and quantities for symbols.
        
        Retrieves the best (highest bid, lowest ask) prices and their quantities
        from the order book. Essential for spread analysis, arbitrage detection,
        and real-time price monitoring across multiple symbols simultaneously.
        
        Args:
            symbols: List of trading symbols to fetch data for (required).
                    Examples: ["BTCUSDT", "ETHUSDT", "ADAUSDT"]
                    Case-insensitive, automatically converted to uppercase
            market_type: Market to query. Options:
                        - "spot": Spot market best bid/ask
                        - "usdm": USDT-margined futures best bid/ask  
                        - "coinm": Coin-margined futures best bid/ask
                        If None, uses toolkit's default_market_type
                        
        Returns:
            dict: Book ticker data or file path for large responses
            
        **Success Response (Single Symbol):**
        ```json
        {
            "success": true,
            "symbol_count": 1,
            "symbols": ["BTCUSDT"],
            "market_type": "spot",
            "data": {
                "symbol": "BTCUSDT",
                "bidPrice": "67200.10000000",
                "bidQty": "0.50000000",
                "askPrice": "67200.20000000",
                "askQty": "0.30000000"
            },
            "analysis": {
                "spread": 0.10,
                "spread_pct": 0.000149,
                "mid_price": 67200.15,
                "liquidity_score": "high"
            }
        }
        ```
        
        **Success Response (Multiple Symbols):**
        ```json
        {
            "success": true,
            "symbol_count": 3,
            "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT"],
            "market_type": "spot",
            "data": [
                {
                    "symbol": "BTCUSDT",
                    "bidPrice": "67200.10000000",
                    "bidQty": "0.50000000",
                    "askPrice": "67200.20000000",
                    "askQty": "0.30000000"
                },
                {
                    "symbol": "ETHUSDT", 
                    "bidPrice": "3850.25000000",
                    "bidQty": "2.50000000",
                    "askPrice": "3850.35000000",
                    "askQty": "1.75000000"
                }
            ],
            "summary": {
                "avg_spread_pct": 0.00026,
                "tightest_spread": "BTCUSDT",
                "highest_liquidity": "ETHUSDT"
            }
        }
        ```
    
        **Validation Error Response:**
        ```json
        {
            "success": false,
            "message": "Invalid symbols found: INVALID1, INVALID2",
            "error_type": "validation_error",
            "invalid_symbols": ["INVALID1", "INVALID2"],
            "valid_symbols": ["BTCUSDT"],
            "market_type": "spot"
        }
        ```
        
        Example Usage:
        ```python
        # Monitor specific symbols for trading opportunities
        tickers = await toolkit.get_book_ticker(["BTCUSDT", "ETHUSDT"], market_type="spot")
        if tickers["success"]:
            for ticker in tickers["data"]:
                symbol = ticker["symbol"]
                bid = float(ticker["bidPrice"])
                ask = float(ticker["askPrice"])
                spread = ask - bid
                spread_pct = (spread / bid) * 100
                
                print(f"{symbol}:")
                print(f"  Bid: ${bid:,.2f} (qty: {ticker['bidQty']})")
                print(f"  Ask: ${ask:,.2f} (qty: {ticker['askQty']})")
                print(f"  Spread: ${spread:.2f} ({spread_pct:.3f}%)")
                
                # Trading opportunity detection
                if spread_pct < 0.01:
                    print(f"  🟢 Tight spread - Good for market making")
                elif spread_pct > 0.1:
                    print(f"  🔴 Wide spread - Lower liquidity")
                    
        # Arbitrage analysis across markets
        markets = ["spot", "usdm"]
        btc_prices = {}
        
        for market in markets:
            result = await toolkit.get_book_ticker(["BTCUSDT"], market_type=market)
            if result["success"]:
                data = result["data"]
                mid_price = (float(data["bidPrice"]) + float(data["askPrice"])) / 2
                btc_prices[market] = mid_price
                
        if len(btc_prices) == 2:
            basis = btc_prices["usdm"] - btc_prices["spot"]
            basis_pct = (basis / btc_prices["spot"]) * 100
            print(f"Futures Basis: ${basis:.2f} ({basis_pct:.3f}%)")
            
            if abs(basis_pct) > 0.1:
                print("🚨 Arbitrage opportunity detected!")
                
        # Multi-symbol spread analysis
        major_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT"]
        multi_tickers = await toolkit.get_book_ticker(major_symbols, market_type="spot")
        if multi_tickers["success"]:
            print("Major symbol spreads:")
            for ticker in multi_tickers["data"]:
                bid = float(ticker["bidPrice"])
                ask = float(ticker["askPrice"])
                spread_pct = ((ask - bid) / bid) * 100
                print(f"  {ticker['symbol']}: {spread_pct:.4f}%")
        ```
        
        **Book Ticker Data Fields:**
        - `symbol`: Trading pair symbol
        - `bidPrice`: Best bid (buy) price available
        - `bidQty`: Quantity available at the best bid price
        - `askPrice`: Best ask (sell) price available
        - `askQty`: Quantity available at the best ask price
        
        **Analysis Metrics:**
        - `spread`: Absolute price difference (ask - bid)
        - `spread_pct`: Spread as percentage of bid price
        - `mid_price`: Average of bid and ask prices
        - `liquidity_score`: Assessment based on quantities and spread
        
        **Trading Applications:**
        - **Market Making**: Identify symbols with profitable spreads
        - **Arbitrage**: Detect price differences across markets
        - **Execution Planning**: Assess market impact before large trades
        - **Risk Management**: Monitor liquidity conditions
        - **Algorithm Trading**: Real-time price feeds for strategies
        
        **Spread Analysis:**
        - **< 0.01%**: Excellent liquidity, institutional-grade
        - **0.01-0.05%**: Good liquidity, suitable for most trading
        - **0.05-0.1%**: Moderate liquidity, consider market impact
        - **> 0.1%**: Lower liquidity, higher trading costs
        
        Performance:
        - Single symbol: 100-250ms
        - Multiple symbols: 200-500ms
        - Rate limit: 1200 requests per minute
        - Data freshness: Real-time (updated continuously)
        """
        market_type = market_type or self.default_market_type
        
        # Validate all symbols asynchronously
        validation_tasks = [self.validate_symbol(s, market_type) for s in symbols]
        validation_results = await asyncio.gather(*validation_tasks)
        
        invalid_symbols = [
            symbols[i] for i, result in enumerate(validation_results)
            if not result["success"]
        ]
        
        if invalid_symbols:
            valid_symbols = [
                symbols[i] for i, result in enumerate(validation_results)
                if result["success"]
            ]
            return self.response_builder.validation_error_response(
                field_name="symbols",
                field_value=invalid_symbols,
                validation_errors=[f"Invalid symbols found: {', '.join(invalid_symbols)}"],
                invalid_symbols=invalid_symbols,
                valid_symbols=valid_symbols,
                market_type=market_type
            )
        
        symbols_upper = [s.upper() for s in symbols]
        
        try:
            if len(symbols_upper) == 1:
                # Single symbol request
                data = await self._make_api_request(_API_ENDPOINTS["book_ticker"], market_type, {
                    "symbol": symbols_upper[0]
                })
                
                # Calculate analysis for single symbol
                analysis = {}
                if data:
                    bid = float(data["bidPrice"])
                    ask = float(data["askPrice"])
                    spread = ask - bid
                    mid_price = (bid + ask) / 2
                    
                    analysis = {
                        "spread": spread,
                        "spread_pct": spread / bid,
                        "mid_price": mid_price,
                        "liquidity_score": "high" if spread / bid < 0.001 else "moderate" if spread / bid < 0.01 else "low"
                    }
                
                return self.response_builder.success_response(
                    data=data,
                    symbol_count=1,
                    symbols=symbols_upper,
                    market_type=market_type,
                    analysis=analysis
                )
            else:
                # Multiple symbols request
                symbols_param = f'["{"\",\"".join(symbols_upper)}"]'
                data = await self._make_api_request(_API_ENDPOINTS["book_ticker"], market_type, {
                    "symbols": symbols_param
                })
                
                base_response = {
                    "success": True,
                    "symbol_count": len(data),
                    "symbols": symbols_upper,
                    "market_type": market_type
                }
                
                # Calculate summary analysis
                summary = {}
                if data:
                    spreads = []
                    liquidities = {}
                    
                    for ticker in data:
                        bid = float(ticker["bidPrice"])
                        ask = float(ticker["askPrice"])
                        spread_pct = (ask - bid) / bid
                        spreads.append(spread_pct)
                        
                        bid_qty = float(ticker["bidQty"])
                        ask_qty = float(ticker["askQty"])
                        liquidity = min(bid_qty, ask_qty)
                        liquidities[ticker["symbol"]] = liquidity
                    
                    if spreads:
                        summary = {
                            "avg_spread_pct": sum(spreads) / len(spreads),
                            "tightest_spread": min(data, key=lambda x: (float(x["askPrice"]) - float(x["bidPrice"])) / float(x["bidPrice"]))["symbol"],
                            "highest_liquidity": max(liquidities.items(), key=lambda x: x[1])[0]
                        }
                
                filename_template = FileNameGenerator.generate_market_data_filename(
                    "book_ticker", "multiple", market_type,
                    file_prefix=self._file_prefix
                )
                
                return self.response_builder.build_data_response_with_storage(
                    data=data,
                    storage_threshold=self._parquet_threshold,
                    storage_callback=lambda data, filename: self._store_parquet(data, filename),
                    filename_template=filename_template,
                    large_data_note="Large response stored as Parquet file",
                    **base_response,
                    summary=summary
                )
        except Exception as e:
            logger.error(f"Failed to get book ticker for {symbols} on {market_type}: {e}")
            return self.response_builder.api_error_response(
                api_endpoint=_API_ENDPOINTS["book_ticker"],
                api_message=f"Failed to get book ticker: {str(e)}",
                symbols=symbols,
                market_type=market_type
            )

    async def aclose(self):
        """Close all HTTP clients and clean up resources.
        
        This method should be called when the toolkit is no longer needed
        to properly close all underlying HTTP clients and free resources.
        
        Example:
            ```python
            toolkit = BinanceToolkit()
            try:
                # Use toolkit...
                result = await toolkit.get_current_price("BTCUSDT")
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
        
        logger.debug("Closed BinanceToolkit and all market clients")