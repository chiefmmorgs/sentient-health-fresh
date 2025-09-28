from __future__ import annotations

"""Base Data Toolkit Helper Class
=================================

A helper class providing common data management functionality for data-related 
toolkits. This is NOT a toolkit itself, but rather a collection of utilities 
that data toolkits can inherit from or use for common operations.

Key Features:
- Parquet file storage for large datasets
- Configurable data thresholds and storage paths
- Data validation and conversion utilities
- Standardized data directory management
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Union, Optional

import pandas as _pd
from loguru import logger

# E2B detection and integration
try:
    import e2b
    _E2B_AVAILABLE = True
except ImportError:
    _E2B_AVAILABLE = False

__all__ = ["BaseDataToolkit"]


class BaseDataToolkit:
    """Helper class for data-intensive toolkit operations.
    
    Provides common functionality for toolkits that handle large datasets and
    need to store data to disk. This class should be inherited by data toolkits
    alongside the main Toolkit class.
    
    Features:
    - Automatic parquet storage for large datasets
    - Configurable data directories and thresholds
    - Data validation and conversion utilities
    - Standardized file naming and organization
    
    Example:
        ```python
        class MyDataToolkit(Toolkit, BaseDataToolkit):
            def __init__(self, data_dir="./data", parquet_threshold=1000, **kwargs):
                # Initialize Toolkit
                super().__init__(**toolkit_kwargs)
                
                # Initialize BaseDataToolkit helpers
                self._init_data_helpers(data_dir, parquet_threshold)
                
            async def get_large_dataset(self, symbol: str):
                data = await self._fetch_large_data(symbol)
                
                if self._should_store_as_parquet(data):
                    file_path = self._store_parquet(data, f"dataset_{symbol}")
                    return {"success": True, "file_path": file_path}
                else:
                    return {"success": True, "data": data}
        ```
    """

    def _init_data_helpers(
        self,
        data_dir: str | Path,
        parquet_threshold: int = 1000,
        file_prefix: str = "",
        toolkit_name: str = "",
    ) -> None:
        """Initialize data management helpers with project-specific folder structure.
        
        Args:
            data_dir: Base directory path for storing parquet files (used as fallback)
            parquet_threshold: Minimum size to trigger parquet storage
            file_prefix: Optional prefix for all generated files
            toolkit_name: Name of the toolkit (used for folder organization)
        """
        # Persist base fallback directory for future reconfiguration on project change
        try:
            self._base_data_dir_fallback = Path(data_dir)
        except Exception:
            self._base_data_dir_fallback = Path(str(data_dir))

        # Get project ID from thread-local context
        from sentientresearchagent.core.project_context import get_project_context
        project_id = get_project_context()
        
        if not project_id:
            # Allow initialization without project context for validation/testing
            # Use a default fallback directory, but mark that we need context later
            project_id = "validation_mode"
            self._needs_project_context = True
            logger.debug(f"BaseDataToolkit initialized without project context - using validation mode")
        else:
            self._needs_project_context = False
        
        # Use centralized project structure
        from sentientresearchagent.core.project_structure import ProjectStructure
        
        if project_id == "validation_mode":
            # Use temporary directory for validation
            if toolkit_name:
                self.data_dir = Path(data_dir) / "validation" / toolkit_name
            else:
                self.data_dir = Path(data_dir) / "validation"
            logger.debug(f"Using validation directory for {toolkit_name}: {self.data_dir}")
        else:
            project_toolkits_dir = ProjectStructure.get_toolkits_dir(project_id)
            if toolkit_name:
                self.data_dir = Path(project_toolkits_dir) / toolkit_name
            else:
                self.data_dir = Path(project_toolkits_dir)
            logger.debug(f"Using project structure for {toolkit_name}: {self.data_dir}")
        
        # Create directory structure
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._parquet_threshold = parquet_threshold
        self._file_prefix = file_prefix
        self._project_id = project_id
        self._toolkit_name = toolkit_name
        
        # S3 integration detection and path configuration
        self._detect_e2b_context()
        
        # Initialize ResponseBuilder with toolkit information
        from ..utils.response_builder import ResponseBuilder
        toolkit_info = self._get_toolkit_info()
        self.response_builder = ResponseBuilder(toolkit_info)
        
        logger.info(f"Data helpers initialized - Project: {project_id}, Toolkit: {toolkit_name or 'unknown'}, Dir: {self.data_dir}, S3: {self._s3_available}")

    def _maybe_refresh_project_context(self) -> None:
        """Refresh data directories if project context changed after initialization.

        This ensures that toolkits created before a project starts will switch to the
        correct project-scoped directory as soon as they are used.
        """
        try:
            from sentientresearchagent.core.project_context import get_project_context
            current_project_id = get_project_context()
            
            if not current_project_id:
                if hasattr(self, '_needs_project_context') and self._needs_project_context:
                    logger.warning(f"Toolkit refresh skipped - no project context available")
                    return
                else:
                    logger.debug(f"Toolkit refresh skipped - no project context in thread {threading.get_ident()}")
                    return
            
            # Check if project changed
            project_changed = getattr(self, "_project_id", None) != current_project_id
            
            if project_changed:
                prev = getattr(self, "_project_id", None)
                logger.debug(f"Refreshing data context - project: {prev} -> {current_project_id}")
                self._init_data_helpers(
                    self._base_data_dir_fallback,
                    getattr(self, "_parquet_threshold", 1000),
                    getattr(self, "_file_prefix", ""),
                    getattr(self, "_toolkit_name", ""),
                )
        except Exception as e:
            logger.warning(f"Failed to refresh project context: {e}")

    def _ensure_project_context(self) -> None:
        """Ensure project context is available for data operations.
        
        This method should be called before any actual data operations
        to ensure the toolkit has proper project context.
        """
        if hasattr(self, '_needs_project_context') and self._needs_project_context:
            from sentientresearchagent.core.project_context import get_project_context
            project_id = get_project_context()
            
            if not project_id:
                raise RuntimeError(
                    "No project context available for data operations. "
                    "This toolkit was initialized in validation mode but is now being used for actual data operations. "
                    "Ensure the toolkit is used within a proper project execution context."
                )
            
            # Re-initialize with proper project context
            logger.info(f"Switching from validation mode to project context: {project_id}")
            self._init_data_helpers(
                getattr(self, '_base_data_dir_fallback', './data'),
                getattr(self, '_parquet_threshold', 1000),
                getattr(self, '_file_prefix', ''),
                getattr(self, '_toolkit_name', '')
            )

    def _detect_e2b_context(self) -> None:
        """Detect if we're running in an E2B execution context and configure S3 paths."""
        # Check for S3 integration first (works for both local and E2B)
        s3_bucket = os.getenv("S3_BUCKET_NAME")
        if s3_bucket:
            # Use S3-mounted directory structure
            # Local: mounted via goofys at configured mount point
            # E2B: mounted at /home/user/s3-bucket via startup script
            self._s3_available = True
            logger.info(f"S3 integration detected with bucket: {s3_bucket}")
        else:
            self._s3_available = False
            logger.debug("No S3 integration - using local storage only")

    def _get_storage_path(self, subdirectory: Optional[str] = None) -> Path:
        """Get storage path - always use local data_dir for actual file operations.
        
        Args:
            subdirectory: Optional subdirectory within data folder
            
        Returns:
            Path: Local storage path for file operations
        """
        # Ensure project context is available and up to date
        self._ensure_project_context()
        self._maybe_refresh_project_context()

        # Always use local data_dir for actual file storage
        # S3 sync happens automatically via goofys if configured
        if subdirectory:
            return self.data_dir / subdirectory
        return self.data_dir
    
    def _translate_path_for_e2b(self, local_path: str) -> str:
        """Translate local file path to E2B-compatible path.
        
        Args:
            local_path: Local file path where file was saved
            
        Returns:
            str: E2B-compatible path if in E2B context, original path otherwise
        """
        # Ensure project context is available and current for translation
        self._ensure_project_context()
        self._maybe_refresh_project_context()

        if not self._s3_available:
            return local_path
            
        # Check if we're in E2B execution context
        in_e2b_context = any([
            os.path.exists("/tmp/.template-id"),  # Our E2B template marker
            os.getenv("E2B_SANDBOX_ID"),
            os.getenv("AGNO_E2B_ACTIVE"),  # AgnoAgent E2B context
        ])
        
        if in_e2b_context:
            # Translate local path to E2B S3 mount path preserving directory structure
            # Local: ./data/project-id/toolkit/[subdir/]file.parquet  
            # E2B:   /home/user/s3-bucket/data/project-id/toolkit/[subdir/]file.parquet
            
            local_path_obj = Path(local_path)
            
            # Find the relative path from the data directory
            try:
                # Get path relative to data directory by finding project_id
                path_parts = local_path_obj.parts
                if self._project_id in path_parts:
                    project_index = path_parts.index(self._project_id)
                    # Get everything from project_id onwards (includes subdirs)
                    relative_parts = path_parts[project_index:]
                    relative_path = "/".join(relative_parts)
                    
                    # Construct E2B path preserving full structure
                    e2b_path = f"/home/user/s3-bucket/data/{relative_path}"
                else:
                    # Fallback: construct path with known structure
                    # This handles cases where project_id isn't in path parts
                    relative_to_toolkit = local_path_obj.relative_to(self.data_dir)
                    e2b_path = f"/home/user/s3-bucket/data/{self._project_id}/{self._toolkit_name or 'unknown'}/{relative_to_toolkit}"
                
                logger.debug(f"Translated path for E2B: {local_path} -> {e2b_path}")
                return e2b_path
                
            except Exception as e:
                # If path parsing fails, fall back to simple construction
                logger.warning(f"Path translation failed: {e}, using fallback")
                filename = local_path_obj.name
                e2b_path = f"/home/user/s3-bucket/data/{self._project_id}/{self._toolkit_name or 'unknown'}/{filename}"
                return e2b_path
        
        return local_path

    def _clean_data_for_parquet(self, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Clean data to handle mixed data types that cause Parquet conversion errors.
        
        This method provides generic handling for any column that contains mixed data types
        (e.g., lists mixed with strings/None values) which breaks Parquet serialization.
        
        Args:
            data: Raw data that may contain mixed types in columns
            
        Returns:
            Cleaned data suitable for Parquet conversion
        """
        import json
        
        def normalize_value(value: Any) -> Any:
            """Normalize a single value to be Parquet-compatible."""
            if value is None:
                return None
            elif isinstance(value, (list, dict)):
                # Convert complex objects to JSON strings
                return json.dumps(value) if value else None
            elif isinstance(value, (int, float, str, bool)):
                # Keep primitive types as-is
                return value
            else:
                # Convert other types to strings
                return str(value)
        
        def clean_item(item: Dict[str, Any]) -> Dict[str, Any]:
            """Clean a single data item by normalizing all values."""
            return {key: normalize_value(value) for key, value in item.items()}
        
        if isinstance(data, list):
            return [clean_item(item) for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            return clean_item(data)
        else:
            return data

    def _store_parquet(
        self, 
        data: Union[List[Dict[str, Any]], _pd.DataFrame], 
        prefix: str,
        subdirectory: Optional[str] = None,
    ) -> str:
        """Store data as a parquet file and return the path.
        
        Args:
            data: Data to store (list of dicts or DataFrame)
            prefix: Filename prefix for the parquet file
            subdirectory: Optional subdirectory within data_dir
            
        Returns:
            str: Full path to the created parquet file
            
        Raises:
            ValueError: If data is empty or invalid
            IOError: If file cannot be written
            
        Example:
            ```python
            # Store list of dicts
            data = [{"symbol": "BTCUSDT", "price": 50000}, ...]
            path = self._store_parquet(data, "prices_btc")
            
            # Store DataFrame with subdirectory
            df = pd.DataFrame(data)
            path = self._store_parquet(df, "order_book", subdirectory="binance")
            ```
        """
        if isinstance(data, list):
            if not data:
                raise ValueError("Cannot store empty list as parquet")
            
            # Clean data to handle mixed types before DataFrame conversion
            if data and isinstance(data[0], dict):
                logger.debug("Cleaning data for Parquet storage to handle mixed data types")
                data = self._clean_data_for_parquet(data)
            
            df = _pd.DataFrame(data)
        else:
            df = data
        
        if df.empty:
            raise ValueError("Cannot store empty DataFrame as parquet")
        
        # Prepare file path - always use local storage for file operations
        ts = int(time.time())
        filename = f"{self._file_prefix}{prefix}_{ts}.parquet"
        
        # Get local storage path (S3 sync happens automatically via goofys)
        storage_path = self._get_storage_path(subdirectory)
        storage_path.mkdir(parents=True, exist_ok=True)
        file_path = storage_path / filename
        
        try:
            # Try direct write first (works for local filesystems)
            df.to_parquet(file_path, compression='snappy', index=False)
            
            file_path_str = str(file_path)
            if self._s3_available:
                logger.info(f"Stored {len(df)} records to S3-synced path: {file_path_str}")
            else:
                logger.info(f"Stored {len(df)} records to local path: {file_path_str}")
            
            return file_path_str
            
        except Exception as e:
            # Check if this is the "Operation not supported" error from S3 filesystem
            if "Operation not supported" in str(e) or "errno 45" in str(e).lower():
                logger.warning(f"Direct parquet write failed, using BytesIO buffer method: {e}")
                return self._store_parquet_via_buffer(df, file_path)
            else:
                logger.error(f"Failed to write parquet file {file_path}: {e}")
                raise IOError(f"Cannot write parquet file: {e}")

    def _store_parquet_via_buffer(self, df: _pd.DataFrame, file_path: Path) -> str:
        """Store parquet file using BytesIO buffer to avoid random write issues with goofys.
        
        Creates the parquet file in memory first, then writes it as a single sequential 
        operation to avoid random write issues with S3 filesystem mounts.
        
        Args:
            df: DataFrame to store
            file_path: Complete path where the file should be stored
            
        Returns:
            str: Path to the stored file
        """
        from io import BytesIO
        
        try:
            # Create parquet file in memory to avoid random writes
            buffer = BytesIO()
            df.to_parquet(buffer, engine='pyarrow', compression='snappy', index=False)
            
            # Write complete file in single sequential operation
            with open(file_path, 'wb') as f:
                f.write(buffer.getvalue())
            
            buffer.close()
            
            file_path_str = str(file_path)
            if self._s3_available:
                logger.info(f"Stored {len(df)} records to S3-synced path via buffer: {file_path_str}")
            else:
                logger.info(f"Stored {len(df)} records to local path via buffer: {file_path_str}")
            
            return file_path_str
            
        except Exception as e:
            logger.error(f"Failed to write parquet file via buffer {file_path}: {e}")
            raise IOError(f"Buffer parquet storage failed: {e}")

    def _should_store_as_parquet(
        self, 
        data: Union[List, _pd.DataFrame, Dict[str, Any]]
    ) -> bool:
        """Check if data should be stored as parquet based on size threshold.
        
        Args:
            data: Data to check (list, DataFrame, or dict with length info)
            
        Returns:
            bool: True if data should be stored as parquet, False otherwise
            
        Example:
            ```python
            large_data = [{"id": i} for i in range(5000)]
            should_store = self._should_store_as_parquet(large_data)  # True
            
            small_data = [{"id": 1}, {"id": 2}]
            should_store = self._should_store_as_parquet(small_data)  # False
            ```
        """
        if isinstance(data, list):
            return len(data) > self._parquet_threshold
        elif isinstance(data, _pd.DataFrame):
            return len(data) > self._parquet_threshold
        elif isinstance(data, dict):
            # For response dicts that might contain data arrays
            if 'data' in data and isinstance(data['data'], (list, _pd.DataFrame)):
                return self._should_store_as_parquet(data['data'])
            # Check if dict has length-like fields
            for key in ['count', 'size', 'length', 'total']:
                if key in data and isinstance(data[key], int):
                    return data[key] > self._parquet_threshold
        
        return False

    def _convert_to_dataframe(
        self, 
        data: Union[List[Dict[str, Any]], Dict[str, Any], _pd.DataFrame],
        index_column: Optional[str] = None,
    ) -> _pd.DataFrame:
        """Convert various data formats to a pandas DataFrame.
        
        Args:
            data: Data to convert
            index_column: Optional column to use as DataFrame index
            
        Returns:
            pd.DataFrame: Converted DataFrame
            
        Raises:
            ValueError: If data format is not supported
            
        Example:
            ```python
            # Convert list of dicts
            data = [{"symbol": "BTC", "price": 50000}, {"symbol": "ETH", "price": 3000}]
            df = self._convert_to_dataframe(data, index_column="symbol")
            
            # Convert nested dict
            data = {"symbols": ["BTC", "ETH"], "prices": [50000, 3000]}
            df = self._convert_to_dataframe(data)
            ```
        """
        if isinstance(data, _pd.DataFrame):
            df = data.copy()
        elif isinstance(data, list):
            if not data:
                raise ValueError("Cannot convert empty list to DataFrame")
            df = _pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to convert dict to DataFrame
            try:
                df = _pd.DataFrame(data)
            except Exception as e:
                raise ValueError(f"Cannot convert dict to DataFrame: {e}")
        else:
            raise ValueError(f"Unsupported data type for DataFrame conversion: {type(data)}")
        
        if index_column and index_column in df.columns:
            df = df.set_index(index_column)
        
        return df

    # REMOVED: _validate_data_structure - Use DataValidator.validate_structure() from utils instead

    def _get_data_summary(
        self, 
        data: Union[List, _pd.DataFrame, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate a summary of data for logging and responses.
        
        Args:
            data: Data to summarize
            
        Returns:
            dict: Data summary with size, type, and other metadata
            
        Example:
            ```python
            summary = self._get_data_summary(large_dataset)
            logger.info(f"Processed data: {summary}")
            # Output: {"type": "list", "size": 5000, "memory_mb": 12.5, ...}
            ```
        """
        summary = {
            "type": type(data).__name__,
            "timestamp": int(time.time()),
        }
        
        if isinstance(data, (list, _pd.DataFrame)):
            summary["size"] = len(data)
            summary["empty"] = len(data) == 0
            
            if isinstance(data, _pd.DataFrame):
                summary["columns"] = list(data.columns)
                summary["memory_mb"] = round(data.memory_usage(deep=True).sum() / (1024 * 1024), 2)
            elif isinstance(data, list) and data:
                # Estimate memory for list
                import sys
                summary["memory_mb"] = round(sys.getsizeof(data) / (1024 * 1024), 2)
                
                # Analyze structure of first item
                if isinstance(data[0], dict):
                    summary["fields"] = list(data[0].keys())
                    
        elif isinstance(data, dict):
            summary["keys"] = list(data.keys())
            
            # Check for nested data
            for key, value in data.items():
                if isinstance(value, (list, _pd.DataFrame)) and hasattr(value, '__len__'):
                    summary[f"{key}_size"] = len(value)
        
        summary["should_store_parquet"] = self._should_store_as_parquet(data)
        
        return summary

    # =========================================================================
    # Standardized Data Response Methods  
    # =========================================================================
    
    # REMOVED: _build_data_response - Use ResponseBuilder.build_data_response_with_storage() from utils instead

    # REMOVED: _generate_data_filename - Use FileNameGenerator.generate_data_filename() from utils instead

    # REMOVED: _build_data_response_with_analysis - Use ResponseBuilder.build_data_response_with_storage() from utils instead

    # REMOVED: _extract_ohlcv_data - Not used, OHLCV extraction handled directly in individual toolkit implementations

    def _clean_data_directory(
        self, 
        max_age_hours: int = 24,
        pattern: str = "*.parquet",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Clean old files from the data directory.
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            pattern: File pattern to match for cleanup
            dry_run: If True, only report what would be deleted
            
        Returns:
            dict: Cleanup results with counts and file lists
            
        Example:
            ```python
            # Clean files older than 48 hours
            result = self._clean_data_directory(max_age_hours=48)
            logger.info(f"Cleaned {result['deleted_count']} old files")
            
            # Dry run to see what would be deleted
            result = self._clean_data_directory(dry_run=True)
            ```
        """
        import glob
        import time
        
        if not hasattr(self, 'data_dir'):
            raise ValueError("Data directory not initialized. Call _init_data_helpers first.")
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        # Find matching files
        pattern_path = self.data_dir / pattern
        matching_files = glob.glob(str(pattern_path), recursive=True)
        
        old_files = []
        total_size = 0
        
        for file_path in matching_files:
            file_stat = os.stat(file_path)
            file_age = current_time - file_stat.st_mtime
            
            if file_age > max_age_seconds:
                old_files.append({
                    "path": file_path,
                    "age_hours": round(file_age / 3600, 1),
                    "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                })
                total_size += file_stat.st_size
        
        deleted_count = 0
        if not dry_run:
            for file_info in old_files:
                try:
                    os.remove(file_info["path"])
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_info['path']}")
                except Exception as e:
                    logger.error(f"Failed to delete {file_info['path']}: {e}")
        
        return {
            "total_files_checked": len(matching_files),
            "old_files_found": len(old_files),
            "deleted_count": deleted_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "dry_run": dry_run,
            "max_age_hours": max_age_hours,
            "old_files": old_files if dry_run else [],
        }

    def _get_toolkit_info(self) -> Dict[str, Any]:
        """Get toolkit identification information automatically.
        
        Returns:
            dict: Toolkit identification info including name, category, type, and icon
        """
        class_name = self.__class__.__name__
        
        # Automatic toolkit information based on class name
        return {
            'toolkit_name': class_name,
            'toolkit_category': getattr(self, '_toolkit_category', 'custom'),
            'toolkit_type': getattr(self, '_toolkit_type', 'custom'),
            'toolkit_icon': getattr(self, '_toolkit_icon', '🛠️')
        }

