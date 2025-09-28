"""Response Builder Utilities
===========================

Standardized response construction for consistent API responses across toolkits.
Provides uniform response formats for success, error, and data storage scenarios.
"""

import time
from typing import Any, Dict, Optional, Union
from pathlib import Path

__all__ = ["ResponseBuilder"]


class ResponseBuilder:
    """Stateful utility class for building standardized API responses.
    
    Automatically injects toolkit information into all responses when initialized
    with toolkit context, eliminating the need for manual injection.
    """
    
    def __init__(self, toolkit_info: Optional[Dict[str, Any]] = None):
        """Initialize ResponseBuilder with toolkit information.
        
        Args:
            toolkit_info: Dictionary containing toolkit identification info
                         (toolkit_name, toolkit_category, toolkit_type, toolkit_icon)
        """
        self.toolkit_info = toolkit_info or {}

    def success_response(
        self,
        data: Any = None,
        message: str = "Operation completed successfully",
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized success response with automatic toolkit information injection.
        
        Args:
            data: Response data payload
            message: Success message
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized success response with toolkit info automatically injected
        """
        response = {
            "success": True,
            "message": message,
            "fetched_at": int(time.time())
        }
        
        if data is not None:
            response["data"] = data
        
        # Automatically inject toolkit information
        response.update(self.toolkit_info)
        
        # Add any additional fields
        response.update(additional_fields)
        
        return response

    def error_response(
        self,
        message: str,
        error_type: str = "unknown_error",
        details: Optional[Dict[str, Any]] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized error response with optional toolkit information.
        
        Args:
            message: Human-readable error message
            error_type: Error classification (e.g., "validation_error", "api_error")
            details: Additional error details
            toolkit_name: Name of the toolkit that generated this error
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized error response
            
        Example:
            >>> ResponseBuilder.error_response(
            ...     message="Invalid symbol format",
            ...     error_type="validation_error",
            ...     symbol="INVALID",
            ...     toolkit_name="BinanceToolkit"
            ... )
            {
                "success": False,
                "message": "Invalid symbol format",
                "error_type": "validation_error",
                "symbol": "INVALID",
                "toolkit_name": "BinanceToolkit",
                "timestamp": 1640995200
            }
        """
        response = {
            "success": False,
            "message": message,
            "error_type": error_type,
            "timestamp": int(time.time())
        }
        
        if details:
            response["details"] = details
            
        # Automatically inject toolkit information
        response.update(self.toolkit_info)
        
        # Remove conflicting keys from additional_fields to prevent duplicate parameter errors
        # This handles cases where **kwargs might contain keys that are already explicit parameters
        safe_additional_fields = {
            k: v for k, v in additional_fields.items() 
            if k not in ["message", "error_type", "details", "success", "timestamp"] + list(self.toolkit_info.keys())
        }
        
        # Add any additional fields
        response.update(safe_additional_fields)
        
        return response

    def data_response(
        self,
        data: Any,
        file_path: Optional[Union[str, Path]] = None,
        data_summary: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a response for data operations with optional file storage.
        
        Args:
            data: Response data (included if file_path is None)  
            file_path: Path to stored data file (if data was stored)
            data_summary: Summary of the data
            note: Additional note about the response
            toolkit_name: Name of the toolkit that generated this response
            **additional_fields: Additional fields to include in response
            
        Returns:
            dict: Standardized data response
            
        Example:
            >>> ResponseBuilder.data_response(
            ...     data=None,
            ...     file_path="/data/klines_BTCUSDT_1640995200.parquet",
            ...     data_summary={"size": 5000, "type": "klines"},
            ...     note="Large dataset stored as Parquet file",
            ...     toolkit_name="BinanceToolkit"
            ... )
        """
        response = self.success_response(**additional_fields)
        
        if file_path:
            response["file_path"] = str(file_path)
            if data_summary:
                response["data_summary"] = data_summary
            if note:
                response["note"] = note
        else:
            response["data"] = data
        
        return response

    def build_data_response_with_storage(
        self,
        data: Any,
        storage_threshold: int,
        storage_callback: callable,
        filename_template: str,
        large_data_note: str = "Large dataset stored as file",
        **additional_fields
    ) -> Dict[str, Any]:
        """Build response with automatic data storage for large datasets.
        
        Args:
            data: The data to include in response
            storage_threshold: Size threshold for triggering storage
            storage_callback: Function to call for data storage
            filename_template: Template for storage filename
            large_data_note: Note to include when data is stored
            **additional_fields: Additional fields for response
            
        Returns:
            dict: Complete response with data or file path
        """
        # Check if data should be stored using simple size estimation
        should_store = self._should_store_data(data, storage_threshold)
        
        if should_store:
            try:
                file_path = storage_callback(data, filename_template)
                return self.data_response(
                    data=None,
                    file_path=file_path,
                    data_summary=self._get_data_summary(data),
                    note=large_data_note,
                    **additional_fields
                )
            except Exception as e:
                # Fallback to returning data directly if storage fails
                return self.success_response(
                    data=data,
                    message=f"Data storage failed, returning directly: {str(e)}",
                    **additional_fields
                )
        else:
            return self.success_response(
                data=data,
                **additional_fields
            )

    def validation_error_response(
        self,
        field_name: str,
        field_value: Any,
        validation_errors: list,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized validation error response.
        
        Args:
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            validation_errors: List of validation error messages
            toolkit_name: Name of the toolkit that generated this error
            **additional_fields: Additional fields to include
            
        Returns:
            dict: Standardized validation error response
        """
        return self.error_response(
            message=f"Validation failed for {field_name}: {', '.join(validation_errors)}",
            error_type="validation_error",
            details={
                "field": field_name,
                "value": field_value,
                "errors": validation_errors
            },
            **additional_fields
        )

    def api_error_response(
        self,
        api_endpoint: str,
        http_status: Optional[int] = None,
        api_message: Optional[str] = None,
        **additional_fields
    ) -> Dict[str, Any]:
        """Create a standardized API error response.
        
        Args:
            api_endpoint: API endpoint that failed
            http_status: HTTP status code received
            api_message: Original API error message
            toolkit_name: Name of the toolkit that generated this error
            **additional_fields: Additional fields to include
            
        Returns:
            dict: Standardized API error response
        """
        message = f"API request failed for {api_endpoint}"
        if http_status:
            message += f" (HTTP {http_status})"
        if api_message:
            message += f": {api_message}"
        
        details = {"endpoint": api_endpoint}
        if http_status:
            details["http_status"] = http_status
        if api_message:
            details["api_message"] = api_message
        
        return self.error_response(
            message=message,
            error_type="api_error",
            details=details,
            **additional_fields
        )

    def _get_data_summary(self, data: Any) -> Dict[str, Any]:
        """Generate a summary of data for responses.
        
        Args:
            data: Data to summarize
            
        Returns:
            dict: Data summary with size, type, and other metadata
        """
        summary = {
            "type": type(data).__name__,
            "timestamp": int(time.time()),
        }
        
        if hasattr(data, '__len__'):
            summary["size"] = len(data)
            summary["empty"] = len(data) == 0
            
            # For pandas DataFrames
            if hasattr(data, 'columns'):
                summary["columns"] = list(data.columns)
                if hasattr(data, 'memory_usage'):
                    summary["memory_mb"] = round(data.memory_usage(deep=True).sum() / (1024 * 1024), 2)
            
            # For lists of dicts
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                summary["fields"] = list(data[0].keys())
                
        # For nested data structures
        elif isinstance(data, dict):
            summary["keys"] = list(data.keys())
            
            # Check for nested data
            for key, value in data.items():
                if hasattr(value, '__len__'):
                    summary[f"{key}_size"] = len(value)
        
        return summary

    def _should_store_data(self, data: Any, threshold_kb: int) -> bool:
        """Determine if data should be stored based on JSON payload size.
        
        Uses JSON serialization to calculate actual response size in KB.
        This directly relates to LLM token usage and memory consumption.
        
        Args:
            data: Data to evaluate
            threshold_kb: Size threshold in KB for triggering storage
            
        Returns:
            bool: True if JSON payload size > threshold_kb
        """
        try:
            # Calculate JSON payload size
            json_str = self._serialize_for_size_check(data)
            size_bytes = len(json_str.encode('utf-8'))
            size_kb = size_bytes / 1024
            
            return size_kb > threshold_kb
            
        except (TypeError, ValueError, MemoryError):
            # Fallback: if JSON serialization fails, use conservative estimate
            # This handles edge cases like circular references or unserializable objects
            return self._fallback_size_check(data, threshold_kb)
    
    def _serialize_for_size_check(self, data: Any) -> str:
        """Serialize data to JSON string for size calculation.
        
        Args:
            data: Data to serialize
            
        Returns:
            str: JSON string representation
        """
        import json
        
        # Use compact JSON (no spaces) for accurate size measurement
        return json.dumps(data, default=str, separators=(',', ':'))
    
    def _fallback_size_check(self, data: Any, threshold_kb: int) -> bool:
        """Fallback size check when JSON serialization fails.
        
        Uses simple heuristics for edge cases.
        
        Args:
            data: Data to check
            threshold_kb: Size threshold in KB
            
        Returns:
            bool: Conservative estimate if data should be stored
        """
        # Conservative fallback: store if it's a complex structure
        if isinstance(data, list):
            return len(data) > (threshold_kb * 10)  # Rough estimate
        elif isinstance(data, dict):
            return len(data) > threshold_kb  # Very conservative for dicts
        elif isinstance(data, str):
            return len(data) > (threshold_kb * 1024)  # String size in bytes
        else:
            return False  # Don't store simple types

    # REMOVED: paginated_response - Not used anywhere in the codebase