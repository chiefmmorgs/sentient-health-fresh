"""Data Validation Utilities
==========================

Extracted validation utilities for consistent data validation across toolkits.
Provides comprehensive validation for various data structures commonly used in 
cryptocurrency and financial data toolkits.
"""

from typing import Any, Dict, List, Optional, Union
import pandas as _pd
from loguru import logger

__all__ = ["DataValidator"]


class DataValidator:
    """Utility class for validating data structures and content.
    
    Provides comprehensive validation methods for various data types commonly
    encountered in financial and cryptocurrency data processing.
    """

    @staticmethod
    def validate_structure(
        data: Any, 
        required_fields: Optional[List[str]] = None,
        expected_type: Optional[type] = None,
    ) -> Dict[str, Any]:
        """Validate data structure and return validation results.
        
        Args:
            data: Data to validate
            required_fields: Required fields for dict/DataFrame data
            expected_type: Expected data type
            
        Returns:
            dict: Validation results with 'valid' boolean and 'errors' list
            
        Example:
            ```python
            # Validate API response
            validation = DataValidator.validate_structure(
                response_data,
                required_fields=["symbol", "price"],
                expected_type=list
            )
            
            if not validation["valid"]:
                logger.error(f"Data validation failed: {validation['errors']}")
            ```
        """
        errors = []
        
        # Type validation
        if expected_type and not isinstance(data, expected_type):
            errors.append(f"Expected {expected_type.__name__}, got {type(data).__name__}")
        
        # Field validation for structured data
        if required_fields:
            if isinstance(data, list) and data:
                # Check first item for required fields
                first_item = data[0]
                if isinstance(first_item, dict):
                    missing_fields = [field for field in required_fields if field not in first_item]
                    if missing_fields:
                        errors.append(f"Missing required fields in list items: {missing_fields}")
            elif isinstance(data, dict):
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    errors.append(f"Missing required fields: {missing_fields}")
            elif isinstance(data, _pd.DataFrame):
                missing_columns = [field for field in required_fields if field not in data.columns]
                if missing_columns:
                    errors.append(f"Missing required columns: {missing_columns}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "data_type": type(data).__name__,
            "size": len(data) if hasattr(data, '__len__') else None,
        }

    @staticmethod
    def validate_ohlcv_fields(
        data: List[Dict[str, Any]], 
        price_fields: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Validate OHLCV data structure and field availability.
        
        Args:
            data: List of market data dictionaries
            price_fields: Mapping of OHLCV fields to data keys
                         Default: {"open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}
            
        Returns:
            dict: Validation results with field mappings and availability
        """
        if not data:
            return {"valid": False, "error": "No data provided"}
        
        # Default field mappings
        if price_fields is None:
            price_fields = {
                "open": "open",
                "high": "high", 
                "low": "low",
                "close": "close",
                "volume": "volume"
            }
        
        # Analyze structure from first item
        first_item = data[0]
        available_fields = set(first_item.keys())
        
        # Map fields with fallbacks
        field_mappings = {}
        missing_fields = []
        
        for ohlcv_field, default_key in price_fields.items():
            if default_key in available_fields:
                field_mappings[ohlcv_field] = default_key
            else:
                # Try common variations
                variations = {
                    "open": ["openPrice", "open_price", "priceOpen"],
                    "high": ["highPrice", "high_price", "priceHigh"],
                    "low": ["lowPrice", "low_price", "priceLow"],
                    "close": ["closePrice", "close_price", "priceClose", "price"],
                    "volume": ["baseVolume", "base_volume", "vol", "quantity"]
                }
                
                found = False
                for variation in variations.get(ohlcv_field, []):
                    if variation in available_fields:
                        field_mappings[ohlcv_field] = variation
                        found = True
                        break
                
                if not found:
                    missing_fields.append(ohlcv_field)
        
        return {
            "valid": len(missing_fields) == 0,
            "field_mappings": field_mappings,
            "missing_fields": missing_fields,
            "available_fields": list(available_fields),
            "total_records": len(data)
        }

    @staticmethod
    def validate_numeric_data(data: Any, field_name: str = "value") -> Dict[str, Any]:
        """Validate that data contains valid numeric values.
        
        Args:
            data: Data to validate (list, dict, or DataFrame)
            field_name: Name of the field being validated (for error messages)
            
        Returns:
            dict: Validation results with numeric statistics
        """
        try:
            if isinstance(data, list):
                numeric_values = [float(x) for x in data if x is not None]
                invalid_count = len(data) - len(numeric_values)
            elif isinstance(data, dict):
                if field_name in data:
                    numeric_values = [float(data[field_name])] if data[field_name] is not None else []
                    invalid_count = 1 - len(numeric_values)
                else:
                    return {"valid": False, "error": f"Field '{field_name}' not found in data"}
            elif isinstance(data, _pd.DataFrame):
                if field_name in data.columns:
                    numeric_values = data[field_name].dropna().astype(float).tolist()
                    invalid_count = len(data) - len(numeric_values)
                else:
                    return {"valid": False, "error": f"Column '{field_name}' not found in DataFrame"}
            else:
                return {"valid": False, "error": f"Unsupported data type: {type(data)}"}
            
            if not numeric_values:
                return {"valid": False, "error": "No valid numeric values found"}
            
            return {
                "valid": True,
                "valid_count": len(numeric_values),
                "invalid_count": invalid_count,
                "min_value": min(numeric_values),
                "max_value": max(numeric_values),
                "mean_value": sum(numeric_values) / len(numeric_values)
            }
            
        except (ValueError, TypeError) as e:
            return {"valid": False, "error": f"Numeric validation failed: {str(e)}"}

    @staticmethod
    def validate_timestamps(
        data: Union[List[int], List[str], _pd.Series], 
        format_type: str = "unix_ms"
    ) -> Dict[str, Any]:
        """Validate timestamp data format and range.
        
        Args:
            data: Timestamp data to validate
            format_type: Expected format ("unix_ms", "unix_s", "iso8601")
            
        Returns:
            dict: Validation results with timestamp statistics
        """
        try:
            valid_timestamps = []
            invalid_count = 0
            
            for ts in data:
                try:
                    if format_type == "unix_ms":
                        # Unix milliseconds should be 13 digits for recent dates
                        ts_int = int(ts)
                        if 1000000000000 <= ts_int <= 9999999999999:  # Reasonable range
                            valid_timestamps.append(ts_int)
                        else:
                            invalid_count += 1
                    elif format_type == "unix_s":
                        # Unix seconds should be 10 digits for recent dates
                        ts_int = int(ts)
                        if 1000000000 <= ts_int <= 9999999999:  # Reasonable range
                            valid_timestamps.append(ts_int)
                        else:
                            invalid_count += 1
                    elif format_type == "iso8601":
                        # Basic ISO8601 validation (could be more comprehensive)
                        if isinstance(ts, str) and len(ts) >= 19:  # Basic length check
                            valid_timestamps.append(ts)
                        else:
                            invalid_count += 1
                except (ValueError, TypeError):
                    invalid_count += 1
            
            if not valid_timestamps:
                return {"valid": False, "error": "No valid timestamps found"}
            
            result = {
                "valid": True,
                "valid_count": len(valid_timestamps),
                "invalid_count": invalid_count,
                "format_type": format_type
            }
            
            # Add timestamp range for numeric timestamps
            if format_type in ["unix_ms", "unix_s"]:
                result["earliest"] = min(valid_timestamps)
                result["latest"] = max(valid_timestamps)
                result["span_seconds"] = (max(valid_timestamps) - min(valid_timestamps))
                if format_type == "unix_ms":
                    result["span_seconds"] = result["span_seconds"] / 1000
            
            return result
            
        except Exception as e:
            return {"valid": False, "error": f"Timestamp validation failed: {str(e)}"}