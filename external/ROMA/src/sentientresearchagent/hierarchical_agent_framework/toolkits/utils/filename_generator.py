"""Filename Generation Utilities
==============================

Standardized filename generation for data storage across toolkits.
Provides consistent naming patterns for parquet files and other data storage.
"""

import time
from typing import Any, Dict, Optional

__all__ = ["FileNameGenerator"]


class FileNameGenerator:
    """Utility class for generating standardized filenames for data storage.
    
    Provides methods to create consistent, descriptive filenames for various
    data storage scenarios in financial and cryptocurrency toolkits.
    """

    @staticmethod
    def generate_data_filename(
        prefix: str,
        primary_identifier: str,
        secondary_identifier: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
        include_timestamp: bool = False,
        file_prefix: str = ""
    ) -> str:
        """Generate standardized filename for data storage.
        
        Args:
            prefix: Filename prefix (e.g., "klines", "market_chart")
            primary_identifier: Primary identifier (e.g., symbol, coin_id)
            secondary_identifier: Optional secondary identifier (e.g., market_type, vs_currency)
            additional_params: Optional additional parameters to include in filename
            include_timestamp: Whether to include timestamp in filename
            file_prefix: Optional prefix for all generated files
            
        Returns:
            str: Generated filename without extension
            
        Example:
            >>> FileNameGenerator.generate_data_filename(
            ...     "klines", "BTCUSDT", "spot", 
            ...     {"interval": "1h", "limit": 500}
            ... )
            "klines_BTCUSDT_spot_1h_500"
        """
        # Start with file prefix if provided
        filename_parts = []
        if file_prefix:
            filename_parts.append(file_prefix.rstrip('_'))
        
        # Add main components
        filename_parts.extend([prefix, primary_identifier])
        
        # Add secondary identifier if provided
        if secondary_identifier:
            filename_parts.append(secondary_identifier)
        
        # Add additional parameters in a consistent order
        if additional_params:
            # Sort parameters for consistent filenames
            for key in sorted(additional_params.keys()):
                value = additional_params[key]
                if value is not None:
                    # Convert value to string and sanitize
                    sanitized_value = str(value).replace('/', '_').replace(' ', '_')
                    filename_parts.append(sanitized_value)
        
        # Add timestamp if requested
        if include_timestamp:
            filename_parts.append(str(int(time.time())))
        
        # Join with underscore and sanitize
        filename = "_".join(filename_parts)
        
        # Remove any problematic characters
        filename = "".join(c for c in filename if c.isalnum() or c in "_-.")
        
        return filename

    @staticmethod
    def generate_timestamped_filename(
        base_name: str,
        extension: str = "parquet",
        file_prefix: str = ""
    ) -> str:
        """Generate a simple timestamped filename.
        
        Args:
            base_name: Base name for the file
            extension: File extension (without dot)
            file_prefix: Optional prefix for the file
            
        Returns:
            str: Complete filename with timestamp and extension
            
        Example:
            >>> FileNameGenerator.generate_timestamped_filename("market_data")
            "market_data_1640995200.parquet"
        """
        timestamp = int(time.time())
        
        if file_prefix:
            full_name = f"{file_prefix}{base_name}_{timestamp}"
        else:
            full_name = f"{base_name}_{timestamp}"
        
        return f"{full_name}.{extension}"

    @staticmethod
    def generate_market_data_filename(
        data_type: str,
        symbol: str,
        market_type: Optional[str] = None,
        interval: Optional[str] = None,
        date_range: Optional[str] = None,
        file_prefix: str = ""
    ) -> str:
        """Generate filename specifically for market data files.
        
        Args:
            data_type: Type of data (e.g., "klines", "orderbook", "trades")
            symbol: Trading symbol
            market_type: Market type (e.g., "spot", "futures")
            interval: Time interval if applicable (e.g., "1h", "1d")
            date_range: Date range if applicable (e.g., "20240101-20240131")
            file_prefix: Optional prefix for the file
            
        Returns:
            str: Generated filename for market data
            
        Example:
            >>> FileNameGenerator.generate_market_data_filename(
            ...     "klines", "BTCUSDT", "spot", "1h", "20240101-20240107"
            ... )
            "klines_BTCUSDT_spot_1h_20240101-20240107"
        """
        parts = [data_type, symbol]
        
        if market_type:
            parts.append(market_type)
        if interval:
            parts.append(interval)
        if date_range:
            parts.append(date_range)
        
        # Use the standard filename generator
        return FileNameGenerator.generate_data_filename(
            prefix=parts[0],
            primary_identifier=parts[1],
            secondary_identifier=parts[2] if len(parts) > 2 else None,
            additional_params={f"param_{i}": parts[i] for i in range(3, len(parts))},
            file_prefix=file_prefix
        )

    # REMOVED: sanitize_filename - Not used anywhere in the codebase

    # REMOVED: parse_data_filename - Not used anywhere in the codebase