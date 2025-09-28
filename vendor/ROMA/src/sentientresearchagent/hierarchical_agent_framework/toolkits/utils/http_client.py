from __future__ import annotations

"""Generic Async HTTP Client for Data Toolkits
==============================================

A reusable HTTP client that provides standardized HTTP functionality for 
data-related toolkits. Supports multiple base URLs, custom headers, 
timeouts, and proper resource management.

Key Features:
- Multiple endpoint support with different base URLs
- Custom headers per endpoint or globally
- Automatic JSON parsing and error handling
- Proper async resource management
- Configurable timeouts and retry logic
"""

import asyncio
from typing import Any, Dict, Optional, Union
from pathlib import Path
import datetime
import time
import httpx
from loguru import logger

__all__ = ["DataHTTPClient"]


class HTTPClientError(Exception):
    """Base exception for HTTP client errors."""
    
    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class DataHTTPClient:
    """Generic async HTTP client for data toolkit operations.
    
    Provides a unified interface for making HTTP requests across different 
    data sources and APIs. Supports multiple endpoints, authentication 
    headers, and automatic resource management.
    
    Example:
        ```python
        # Basic usage
        client = DataHTTPClient()
        await client.add_endpoint("binance_spot", "https://api.binance.com")
        response = await client.get("binance_spot", "/api/v3/ticker/price", 
                                  params={"symbol": "BTCUSDT"})
        
        # With authentication
        client = DataHTTPClient()
        await client.add_endpoint("binance_spot", "https://api.binance.com", 
                                headers={"X-MBX-APIKEY": "your_key"})
        
        # Multiple endpoints
        await client.add_endpoint("binance_futures", "https://fapi.binance.com")
        await client.add_endpoint("coinbase", "https://api.coinbase.com")
        ```
    """

    def __init__(
        self,
        default_timeout: float = 30.0,
        default_headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        default_rate_limit: Optional[float] = None,
    ):
        """Initialize the HTTP client.
        
        Args:
            default_timeout: Default timeout for all requests in seconds
            default_headers: Default headers applied to all requests
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Delay between retry attempts in seconds
            default_rate_limit: Default minimum seconds between requests (None = no limit)
        """
        self._default_timeout = default_timeout
        self._default_headers = default_headers or {}
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._default_rate_limit = default_rate_limit
        
        # Store endpoint configurations
        self._endpoints: Dict[str, Dict[str, Any]] = {}
        
        # Store active HTTP clients per endpoint
        self._clients: Dict[str, httpx.AsyncClient] = {}
        
        # Rate limiting tracking - store last request time per endpoint
        self._last_request_times: Dict[str, float] = {}
        
        logger.debug(f"Initialized DataHTTPClient with {default_timeout}s timeout")

    async def add_endpoint(
        self,
        name: str,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        rate_limit: Optional[float] = None,
        **client_kwargs: Any,
    ) -> None:
        """Add a new endpoint configuration.
        
        Args:
            name: Unique identifier for this endpoint
            base_url: Base URL for the endpoint
            headers: Additional headers specific to this endpoint
            timeout: Custom timeout for this endpoint (overrides default)
            rate_limit: Minimum seconds between requests to this endpoint (overrides default)
            **client_kwargs: Additional arguments passed to httpx.AsyncClient
            
        Example:
            ```python
            await client.add_endpoint(
                "binance_spot",
                "https://api.binance.com",
                headers={"X-MBX-APIKEY": "your_key"},
                timeout=60.0
            )
            ```
        """
        if name in self._endpoints:
            logger.warning(f"Endpoint '{name}' already exists, updating configuration")
            # Close existing client if it exists
            if name in self._clients:
                await self._clients[name].aclose()
                del self._clients[name]
        
        # Merge headers
        endpoint_headers = {**self._default_headers}
        if headers:
            endpoint_headers.update(headers)
        
        self._endpoints[name] = {
            "base_url": base_url,
            "headers": endpoint_headers,
            "timeout": timeout or self._default_timeout,
            "rate_limit": rate_limit if rate_limit is not None else self._default_rate_limit,
            "client_kwargs": client_kwargs,
        }
        
        logger.debug(f"Added endpoint '{name}' with base URL: {base_url}")

    def _get_client(self, endpoint_name: str) -> httpx.AsyncClient:
        """Get or create HTTP client for the specified endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            
        Returns:
            httpx.AsyncClient: Configured client for the endpoint
            
        Raises:
            ValueError: If endpoint is not configured
        """
        if endpoint_name not in self._endpoints:
            available = list(self._endpoints.keys())
            raise ValueError(f"Endpoint '{endpoint_name}' not configured. Available: {available}")
        
        if endpoint_name not in self._clients:
            config = self._endpoints[endpoint_name]
            
            self._clients[endpoint_name] = httpx.AsyncClient(
                base_url=config["base_url"],
                headers=config["headers"],
                timeout=config["timeout"],
                **config["client_kwargs"],
            )
            
            logger.debug(f"Created HTTP client for endpoint '{endpoint_name}'")
        
        return self._clients[endpoint_name]

    async def _apply_rate_limit(self, endpoint_name: str) -> None:
        """Apply rate limiting for the specified endpoint.
        
        Args:
            endpoint_name: Name of the endpoint to check rate limiting for
        """
        if endpoint_name not in self._endpoints:
            return
            
        rate_limit = self._endpoints[endpoint_name].get("rate_limit")
        if rate_limit is None:
            return
            
        current_time = time.time()
        last_request_time = self._last_request_times.get(endpoint_name, 0)
        
        time_since_last = current_time - last_request_time
        if time_since_last < rate_limit:
            sleep_time = rate_limit - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for endpoint '{endpoint_name}'")
            await asyncio.sleep(sleep_time)
        
        self._last_request_times[endpoint_name] = time.time()

    async def get(
        self,
        endpoint_name: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make a GET request to the specified endpoint.
        
        Args:
            endpoint_name: Name of the configured endpoint
            path: URL path (relative to endpoint base URL)
            params: Query parameters
            headers: Additional headers for this request
            timeout: Custom timeout for this request
            retries: Custom retry count for this request
            
        Returns:
            dict: JSON response data
            
        Raises:
            HTTPClientError: For HTTP errors or invalid responses
            
        Example:
            ```python
            response = await client.get(
                "binance_spot",
                "/api/v3/ticker/price",
                params={"symbol": "BTCUSDT"}
            )
            ```
        """
        return await self._make_request(
            endpoint_name, "GET", path, params=params, 
            headers=headers, timeout=timeout, retries=retries
        )

    async def post(
        self,
        endpoint_name: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make a POST request to the specified endpoint.
        
        Args:
            endpoint_name: Name of the configured endpoint
            path: URL path (relative to endpoint base URL)
            json_data: JSON data to send in request body
            data: Form data to send in request body
            params: Query parameters
            headers: Additional headers for this request
            timeout: Custom timeout for this request
            retries: Custom retry count for this request
            
        Returns:
            dict: JSON response data
            
        Raises:
            HTTPClientError: For HTTP errors or invalid responses
        """
        return await self._make_request(
            endpoint_name, "POST", path, json_data=json_data, data=data,
            params=params, headers=headers, timeout=timeout, retries=retries
        )

    async def _make_request(
        self,
        endpoint_name: str,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic.
        
        Args:
            endpoint_name: Name of the configured endpoint
            method: HTTP method (GET, POST, etc.)
            path: URL path
            json_data: JSON payload
            data: Form data payload
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout
            retries: Number of retries
            
        Returns:
            dict: JSON response data
            
        Raises:
            HTTPClientError: For HTTP errors or invalid responses
        """
        client = self._get_client(endpoint_name)
        max_retries = retries if retries is not None else self._max_retries
        
        # Apply rate limiting if configured for this endpoint
        await self._apply_rate_limit(endpoint_name)
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Making {method} request to {endpoint_name}{path} (attempt {attempt + 1})")
                
                response = await client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json_data,
                    data=data,
                    headers=headers,
                    timeout=timeout,
                )
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except Exception as e:
                    raise HTTPClientError(f"Invalid JSON response: {e}", response.status_code, response.text)
                    
            except httpx.HTTPStatusError as e:
                last_error = HTTPClientError(
                    f"HTTP {e.response.status_code} error: {e.response.text}",
                    e.response.status_code,
                    e.response.text
                )
                
                # Don't retry client errors (4xx), only server errors (5xx)
                if 400 <= e.response.status_code < 500:
                    break
                    
            except httpx.RequestError as e:
                last_error = HTTPClientError(f"Request failed: {e}")
                
            except Exception as e:
                last_error = HTTPClientError(f"Unexpected error: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))  # Exponential backoff
                logger.debug(f"Retrying request after {self._retry_delay * (attempt + 1)}s delay")
        
        # All retries exhausted
        logger.error(f"Request to {endpoint_name}{path} failed after {max_retries + 1} attempts")
        raise last_error

    # REMOVED: update_endpoint_headers - Only used in tests, not in actual toolkit code

    # REMOVED: remove_endpoint - Only used in tests, not in actual toolkit code

    def get_endpoints(self) -> Dict[str, str]:
        """Get a summary of configured endpoints.
        
        Returns:
            dict: Mapping of endpoint names to their base URLs
        """
        return {name: config["base_url"] for name, config in self._endpoints.items()}

    async def update_endpoint_headers(self, endpoint_name: str, headers: Dict[str, str]) -> None:
        """Update headers for an existing endpoint.
        
        Args:
            endpoint_name: Name of the endpoint to update
            headers: New headers to merge with existing ones
            
        Raises:
            ValueError: If endpoint is not configured
        """
        if endpoint_name not in self._endpoints:
            available = list(self._endpoints.keys())
            raise ValueError(f"Endpoint '{endpoint_name}' not configured. Available: {available}")
        
        # Update headers in endpoint configuration
        self._endpoints[endpoint_name]["headers"].update(headers)
        
        # If client exists, close it so it gets recreated with new headers
        if endpoint_name in self._clients:
            await self._clients[endpoint_name].aclose()
            del self._clients[endpoint_name]
        
        logger.debug(f"Updated headers for endpoint '{endpoint_name}'")

    async def remove_endpoint(self, endpoint_name: str) -> None:
        """Remove an endpoint and close its associated client.
        
        Args:
            endpoint_name: Name of the endpoint to remove
        """
        # Close client if it exists
        if endpoint_name in self._clients:
            await self._clients[endpoint_name].aclose()
            del self._clients[endpoint_name]
        
        # Remove endpoint configuration
        if endpoint_name in self._endpoints:
            del self._endpoints[endpoint_name]
        
        logger.debug(f"Removed endpoint '{endpoint_name}'")

    async def aclose(self) -> None:
        """Close all HTTP clients and clean up resources.
        
        This should be called when the client is no longer needed to prevent
        resource leaks.
        """
        for endpoint_name, client in self._clients.items():
            await client.aclose()
            logger.debug(f"Closed HTTP client for endpoint '{endpoint_name}'")
        
        self._clients.clear()
        self._endpoints.clear()
        logger.debug("Closed DataHTTPClient and all endpoints")
    
    @staticmethod
    def unix_to_iso8601(timestamp_ms):
        if timestamp_ms:
            return datetime.datetime.fromtimestamp(timestamp_ms / 1000, datetime.timezone.utc).replace(tzinfo=None).isoformat() + "Z"
        return None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()