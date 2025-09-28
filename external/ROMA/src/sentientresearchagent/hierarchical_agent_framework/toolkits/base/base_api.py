from __future__ import annotations

"""Base API Toolkit Helper Class
===============================

A helper class providing common API business logic for data toolkits.
Focuses on API-specific concerns like parameter validation, identifier
resolution, and response formatting - separate from HTTP transport
(DataHTTPClient) and data storage (BaseDataToolkit).

Key Features:
- API parameter validation and cleaning
- Identifier resolution (symbols, coin IDs, etc.)
- Standardized response formatting
- Business logic error handling

This class follows single responsibility principle by focusing solely on
API business logic concerns, working together with:
- DataHTTPClient: HTTP transport and endpoint management
- BaseDataToolkit: Data storage and file management
"""

import time
from typing import Any, Dict, List, Optional, Callable, Union, Set
from datetime import datetime, timezone

from loguru import logger

__all__ = ["BaseAPIToolkit"]


class BaseAPIToolkit:
    """Helper class for API business logic functionality.
    
    Provides reusable patterns for API parameter validation, identifier
    resolution, and response formatting that are common across different
    data source integrations.
    
    This class should be inherited alongside other base classes:
    
    Example:
        ```python
        class CoinGeckoToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._init_data_helpers("./data")
                self._init_api_helpers()
                
                # HTTP client for transport
                self.http_client = DataHTTPClient()
                
            async def get_coin_price(self, symbol: str):
                # Use API helpers for business logic
                coin_id = self._resolve_identifier(
                    symbol, "symbol",
                    resolver_func=self._symbol_to_coin_id
                )
                
                params = self._validate_api_parameters(
                    {"vs_currency": "usd"},
                    required_params=["vs_currency"]
                )
                
                try:
                    # Use HTTP client for transport
                    result = await self.http_client.get("main", f"/coins/{coin_id}")
                    
                    # Use ResponseBuilder for response formatting (automatic toolkit info injection)
                    return self.response_builder.success_response(
                        data=result,
                        coin_id=coin_id,
                        endpoint=f"/coins/{coin_id}"
                    )
                except Exception as e:
                    return self.response_builder.api_error_response(
                        api_endpoint=f"/coins/{coin_id}",
                        api_message=str(e),
                        coin_id=coin_id
                    )
        ```
    """

    def _resolve_identifier(
        self,
        identifier: str,
        identifier_type: str = "symbol",
        resolver_func: Optional[Callable[[str], str]] = None,
        fallback_value: Optional[str] = None,
    ) -> str:
        """Generic method to resolve and validate identifiers (symbols, coin IDs, etc.).
        
        Args:
            identifier: The identifier to resolve (e.g., "BTC", "bitcoin")
            identifier_type: Type of identifier for error messages ("symbol", "coin_id", etc.)
            resolver_func: Optional function to resolve the identifier
            fallback_value: Fallback value if resolution fails
            
        Returns:
            str: Resolved identifier
            
        Raises:
            ValueError: If identifier is invalid and no fallback provided
        """
        if not identifier or not isinstance(identifier, str):
            if fallback_value:
                logger.warning(f"Invalid {identifier_type} '{identifier}', using fallback: {fallback_value}")
                return fallback_value
            raise ValueError(f"Invalid {identifier_type}: {identifier}")
        
        cleaned = identifier.strip()
        if not cleaned:
            if fallback_value:
                logger.warning(f"Empty {identifier_type}, using fallback: {fallback_value}")
                return fallback_value
            raise ValueError(f"Empty {identifier_type} provided")
        
        if resolver_func:
            try:
                resolved = resolver_func(cleaned)
                if resolved:
                    return resolved
                elif fallback_value:
                    logger.warning(f"Resolver failed for {identifier_type} '{cleaned}', using fallback: {fallback_value}")
                    return fallback_value
                else:
                    raise ValueError(f"Cannot resolve {identifier_type}: {cleaned}")
            except Exception as e:
                if fallback_value:
                    logger.warning(f"Resolver error for {identifier_type} '{cleaned}': {e}, using fallback: {fallback_value}")
                    return fallback_value
                raise ValueError(f"Error resolving {identifier_type} '{cleaned}': {e}")
        
        return cleaned

    def _validate_api_parameters(
        self,
        params: Dict[str, Any],
        required_params: List[str],
        optional_params: Optional[List[str]] = None,
        param_validators: Optional[Dict[str, Callable]] = None,
    ) -> Dict[str, Any]:
        """Validate API parameters and return cleaned parameter dict.
        
        Args:
            params: Dictionary of parameters to validate
            required_params: List of required parameter names
            optional_params: List of optional parameter names
            param_validators: Dict mapping param names to validation functions
            
        Returns:
            dict: Validated and cleaned parameters
            
        Raises:
            ValueError: If required parameters are missing or validation fails
        """
        cleaned_params = {}
        all_allowed = set(required_params)
        
        if optional_params:
            all_allowed.update(optional_params)
        
        # Check for required parameters
        for param in required_params:
            if param not in params or params[param] is None:
                raise ValueError(f"Required parameter '{param}' is missing")
            cleaned_params[param] = params[param]
        
        # Add optional parameters if present
        if optional_params:
            for param in optional_params:
                if param in params and params[param] is not None:
                    cleaned_params[param] = params[param]
        
        # Validate parameters using custom validators
        if param_validators:
            for param, validator in param_validators.items():
                if param in cleaned_params:
                    try:
                        if not validator(cleaned_params[param]):
                            raise ValueError(f"Validation failed for parameter '{param}': {cleaned_params[param]}")
                    except Exception as e:
                        raise ValueError(f"Validation error for parameter '{param}': {e}")
        
        # Check for unexpected parameters
        unexpected = set(params.keys()) - all_allowed
        if unexpected:
            logger.warning(f"Unexpected parameters ignored: {unexpected}")
        
        return cleaned_params

    # REMOVED: _build_success_response - Use ResponseBuilder.success_response() from utils instead

    # REMOVED: _build_error_response - Use ResponseBuilder.error_response() from utils instead

    # REMOVED: _handle_api_error - Use ResponseBuilder.api_error_response() from utils instead

    # REMOVED: _normalize_symbol - Not used, symbol normalization handled differently in each toolkit

    # REMOVED: _parse_time_parameter - Not used, direct ISO/Unix conversion methods used instead

    # =========================================================================
    # DateTime Utilities
    # =========================================================================
    
    @staticmethod
    def iso_to_unix(iso_date: str) -> int:
        """Convert ISO 8601 date string to Unix timestamp.
        
        Args:
            iso_date: ISO 8601 formatted date string
            
        Returns:
            int: Unix timestamp in seconds
            
        Raises:
            ValueError: If date format is invalid
        """
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return int(dt.timestamp())
        except Exception as e:
            raise ValueError(f"Invalid ISO date format '{iso_date}': {e}")
    
    @staticmethod
    def unix_to_iso(unix_timestamp: Union[int, float]) -> str:
        """Convert Unix timestamp to ISO 8601 date string.
        
        Args:
            unix_timestamp: Unix timestamp (seconds or milliseconds)
            
        Returns:
            str: ISO 8601 formatted date string
            
        Raises:
            ValueError: If timestamp is invalid
        """
        try:
            # Handle millisecond timestamps
            if unix_timestamp > 1e10:
                unix_timestamp = unix_timestamp / 1000
            dt = datetime.fromtimestamp(unix_timestamp, timezone.utc)
            return dt.isoformat().replace('+00:00', 'Z')
        except Exception as e:
            raise ValueError(f"Invalid Unix timestamp '{unix_timestamp}': {e}")

    # =========================================================================
    # Enhanced Response Building
    # =========================================================================
    
    # REMOVED: _build_success_response_with_analysis - Use ResponseBuilder methods from utils instead

    # REMOVED: _build_error_response_with_context - Use ResponseBuilder.validation_error_response() or ResponseBuilder.api_error_response() from utils instead

    # =========================================================================
    # Advanced Caching and Validation Patterns
    # =========================================================================
    
    def _init_cache_system(self, cache_ttl_seconds: int = 3600) -> None:
        """Initialize caching system for any data types (identifiers, lists, objects).
        
        Args:
            cache_ttl_seconds: Time-to-live for cached data in seconds
        """
        self._cache_ttl = cache_ttl_seconds
        self._data_caches: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        logger.debug(f"Initialized generic cache system with TTL: {cache_ttl_seconds}s")

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache entry is still valid based on TTL.
        
        Args:
            cache_key: Cache key to check
            
        Returns:
            bool: True if cache is valid, False if expired or missing
        """
        if not hasattr(self, '_cache_timestamps') or cache_key not in self._cache_timestamps:
            return False
            
        age = time.time() - self._cache_timestamps[cache_key]
        return age < getattr(self, '_cache_ttl', 3600)

    def _cache_data(
        self, 
        cache_key: str, 
        data: Any, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Cache any data type with optional metadata.
        
        Args:
            cache_key: Unique key for this cache entry
            data: Data to cache (can be list, set, dict, string, etc.)
            metadata: Optional metadata to store with data
        """
        if not hasattr(self, '_data_caches'):
            self._init_cache_system()
            
        self._data_caches[cache_key] = {
            "data": data,
            "metadata": metadata or {},
            "data_type": type(data).__name__
        }
        self._cache_timestamps[cache_key] = time.time()
        
        size_info = f" ({len(data)} items)" if hasattr(data, '__len__') else ""
        logger.debug(f"Cached {type(data).__name__} data{size_info} for key '{cache_key}'")

    def _get_cached_data(self, cache_key: str) -> Optional[Any]:
        """Retrieve cached data if still valid.
        
        Args:
            cache_key: Cache key to retrieve
            
        Returns:
            Any or None: Cached data if valid, None if expired/missing
        """
        if not self._is_cache_valid(cache_key):
            return None
            
        cache_entry = self._data_caches.get(cache_key, {})
        return cache_entry.get("data")

    # Backward compatibility methods
    def _cache_identifiers(
        self, 
        cache_key: str, 
        identifiers: Union[Set[str], List[str]], 
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Cache identifiers (backward compatibility wrapper)."""
        identifier_set = set(identifiers) if isinstance(identifiers, list) else identifiers
        self._cache_data(cache_key, identifier_set, metadata)

    def _get_cached_identifiers(self, cache_key: str) -> Optional[Set[str]]:
        """Retrieve cached identifiers (backward compatibility wrapper)."""
        return self._get_cached_data(cache_key)

    def _validate_configuration_enum(
        self,
        value: str,
        enum_class: type,
        config_name: str = "configuration"
    ) -> None:
        """Validate a configuration value against an enum class.
        
        Args:
            value: Value to validate
            enum_class: Enum class for validation
            config_name: Name for error messages
            
        Raises:
            ValueError: If value is not in enum
        """
        if hasattr(enum_class, '__members__'):
            # Handle Python enum
            valid_values = [v.value for v in enum_class.__members__.values()]
        else:
            # Handle other iterable types
            valid_values = list(enum_class)
            
        if value not in valid_values:
            raise ValueError(
                f"Unsupported {config_name} '{value}'. "
                f"Supported: {valid_values}"
            )

    def _validate_configuration_mapping(
        self,
        value: str,
        config_mapping: Dict[str, Any],
        config_name: str = "configuration"
    ) -> None:
        """Validate a configuration value against a mapping.
        
        Args:
            value: Value to validate
            config_mapping: Dictionary of valid configurations
            config_name: Name for error messages
            
        Raises:
            ValueError: If value is not in mapping
        """
        if value not in config_mapping:
            raise ValueError(
                f"Unsupported {config_name} '{value}'. "
                f"Supported: {list(config_mapping.keys())}"
            )

    def _setup_multi_endpoint_authentication(
        self,
        endpoint_configs: Dict[str, Dict[str, Any]],
        auth_header_builder: Callable[[str, Dict[str, Any]], Dict[str, str]]
    ) -> None:
        """Setup multiple endpoints with authentication headers.
        
        Args:
            endpoint_configs: Mapping of endpoint names to configurations
            auth_header_builder: Function to build auth headers for each endpoint
        """
        async def setup_endpoints():
            if not hasattr(self, '_http_client'):
                raise RuntimeError("HTTP client not initialized")
                
            for endpoint_name, config in endpoint_configs.items():
                headers = auth_header_builder(endpoint_name, config)
                
                await self._http_client.add_endpoint(
                    name=endpoint_name,
                    base_url=config["base_url"],
                    headers=headers,
                    timeout=config.get("timeout", 30.0),
                )
                
            logger.debug(f"Setup {len(endpoint_configs)} authenticated endpoints")
        
        # Store for later async execution
        self._pending_endpoint_setup = setup_endpoints

    async def _execute_pending_endpoint_setup(self) -> None:
        """Execute pending endpoint setup if available."""
        if hasattr(self, '_pending_endpoint_setup'):
            await self._pending_endpoint_setup()
            delattr(self, '_pending_endpoint_setup')

    def _find_fuzzy_match(
        self, 
        target: str, 
        candidates: Union[Set[str], List[str]], 
        threshold: float = 0.6
    ) -> Optional[str]:
        """Find fuzzy match for target string in candidates.
        
        Args:
            target: Target string to match
            candidates: Candidate strings to search
            threshold: Minimum similarity threshold (0.0 to 1.0)
            
        Returns:
            str or None: Best matching candidate if above threshold
        """
        try:
            import difflib
        except ImportError:
            logger.warning("difflib not available for fuzzy matching")
            return None
            
        candidate_list = list(candidates) if isinstance(candidates, set) else candidates
        target_upper = target.upper()
        
        matches = difflib.get_close_matches(
            target_upper,
            [c.upper() for c in candidate_list],
            n=1,
            cutoff=threshold
        )
        
        if matches:
            # Find original case candidate
            for candidate in candidate_list:
                if candidate.upper() == matches[0]:
                    return candidate
                    
        return None

    def _build_identifier_validation_response(
        self,
        identifier: str,
        is_valid: bool,
        config_context: str,
        identifier_type: str = "identifier",
        suggestions: Optional[List[str]] = None,
        **additional_data: Any
    ) -> Dict[str, Any]:
        """Build standardized identifier validation response.
        
        Args:
            identifier: The identifier that was validated
            is_valid: Whether identifier is valid
            config_context: Configuration context (e.g., market type, API version)
            identifier_type: Type of identifier for messages
            suggestions: Optional suggestions for invalid identifiers
            **additional_data: Additional data to include
            
        Returns:
            dict: Standardized validation response
        """
        base_data = {
            "identifier": identifier,
            "config_context": config_context,
            "valid": is_valid,
            "identifier_type": identifier_type,
            **additional_data
        }
        
        if is_valid:
            message = f"{identifier_type.title()} is valid"
            # Use ResponseBuilder for proper toolkit info injection
            return self.response_builder.success_response(
                data=base_data,
                message=message,
                validation_type="identifier",
                analysis={"message": message}
            )
        else:
            message = f"{identifier_type.title()} '{identifier}' not found in '{config_context}'"
            # Use ResponseBuilder for proper toolkit info injection
            response = self.response_builder.error_response(
                message=message,
                error_type="identifier_not_found",
                details=base_data,
                validation_type="identifier"
            )
            if suggestions:
                response["suggestions"] = suggestions
            return response

    # REMOVED: _get_cache_statistics - Not used, was intended for debugging/monitoring but never implemented

    # =========================================================================
    # HTTP Client Initialization and Management
    # =========================================================================

    def _init_standard_configuration(
        self,
        http_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        cache_ttl_seconds: int = 3600
    ) -> None:
        """Initialize standard configuration for API toolkits.
        
        Args:
            http_timeout: HTTP request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        # Import here to avoid circular imports
        from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import DataHTTPClient
        
        # Initialize cache system
        self._init_cache_system(cache_ttl_seconds)
        
        # Initialize HTTP client with standard configuration
        self._http_client = DataHTTPClient(
            default_timeout=http_timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        
        logger.debug(f"Initialized standard configuration: timeout={http_timeout}s, retries={max_retries}, cache_ttl={cache_ttl_seconds}s")

    # REMOVED: _clear_identifier_cache - Not used, cache management handled differently in practice

    async def _validate_identifier_and_prepare_params(
        self,
        identifier: str,
        identifier_type: str,
        validation_func: Callable,
        additional_params: Optional[Dict[str, Any]] = None,
        identifier_transform_func: Optional[Callable[[str], str]] = None
    ) -> Dict[str, Any]:
        """Generic method to validate identifiers and prepare standardized parameters.
        
        This consolidates the common pattern of identifier validation and parameter
        preparation that's used across different data toolkits (Binance, CoinGecko, etc.).
        
        Args:
            identifier: The identifier to validate (symbol, coin_id, etc.)
            identifier_type: Type description for error messages ("symbol", "coin_id", etc.)
            validation_func: Async function that validates the identifier
            additional_params: Additional parameters to include
            identifier_transform_func: Optional function to transform identifier (e.g., upper/lower case)
            
        Returns:
            dict: Validated parameters
            
        Raises:
            ValueError: If identifier validation fails
            
        Example:
            ```python
            # In Binance toolkit
            params = await self._validate_identifier_and_prepare_params(
                identifier=symbol,
                identifier_type="symbol", 
                validation_func=lambda s, mt: self.validate_symbol(s, mt),
                additional_params={"market_type": market_type},
                identifier_transform_func=str.upper
            )
            
            # In CoinGecko toolkit  
            params = await self._validate_identifier_and_prepare_params(
                identifier=coin_name_or_id,
                identifier_type="coin_id",
                validation_func=lambda c: self.resolve_coin_name_or_id(c),
                additional_params={"vs_currency": vs_currency},
                identifier_transform_func=str.lower
            )
            ```
        """
        # Transform identifier if transformation function provided
        if identifier_transform_func:
            identifier = identifier_transform_func(identifier)
        
        # Prepare base parameters
        base_params = {identifier_type: identifier}
        if additional_params:
            base_params.update(additional_params)
        
        # Validate parameters using base class method
        # All additional parameters are treated as optional for flexibility
        optional_param_names = list(additional_params.keys()) if additional_params else []
        validated_params = self._validate_api_parameters(
            params=base_params,
            required_params=[identifier_type],
            optional_params=optional_param_names
        )
        
        # Call validation function with the identifier
        if validation_func:
            validation_result = await validation_func(validated_params[identifier_type])
            
            # Handle different validation result formats
            if isinstance(validation_result, dict):
                if not validation_result.get("success", True):
                    raise ValueError(validation_result.get("message", f"Failed to validate {identifier_type}: {identifier}"))
                    
                # If validation returns additional data (like resolved coin_id), merge it
                if "coin_id" in validation_result:
                    validated_params["coin_id"] = validation_result["coin_id"]
            elif validation_result is False:
                raise ValueError(f"Invalid {identifier_type}: {identifier}")
        
        return validated_params