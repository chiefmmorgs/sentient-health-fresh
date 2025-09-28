# Data Toolkits Development Guide

This guide provides comprehensive instructions for adding new data toolkits to the SentientResearchAgent framework. Data toolkits provide agents with access to external APIs, databases, and data sources.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Step-by-Step Implementation](#step-by-step-implementation)
- [Configuration & Registration](#configuration--registration)
- [Testing](#testing)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

### What are Data Toolkits?

Data toolkits are specialized classes that:
- **Provide API access** to external data sources (APIs, databases, etc.)
- **Standardize responses** for LLM consumption 
- **Handle large datasets** efficiently with Parquet storage
- **Include statistical analysis** and data processing capabilities
- **Support YAML configuration** for agent integration

### Architecture

```
BaseDataToolkit (base class)
├── BaseAPIToolkit (API-specific features)
├── ArkhamToolkit (blockchain intelligence)
├── BinanceToolkit (cryptocurrency trading)
├── CoinGeckoToolkit (crypto market data)
└── YourNewToolkit (your implementation)
```

## Quick Start

### 1. Create Your Toolkit File

```bash
# Create your toolkit file
touch src/sentientresearchagent/hierarchical_agent_framework/toolkits/data/your_toolkit.py
```

### 2. Basic Implementation Template

```python
from __future__ import annotations

"""Your Toolkit Description
==========================

Brief description of your toolkit and its capabilities.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from enum import Enum

import pandas as _pd
import numpy as _np
from agno.tools import Toolkit
from loguru import logger

from sentientresearchagent.hierarchical_agent_framework.toolkits.base import BaseDataToolkit, BaseAPIToolkit
from sentientresearchagent.hierarchical_agent_framework.toolkits.utils import (
    DataHTTPClient, StatisticalAnalyzer, DataValidator, ResponseBuilder, FileNameGenerator
)

__all__ = ["YourToolkit"]

class YourToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """Your toolkit description."""

    def __init__(
        self,
        api_key: str | None = None,
        name: str = "your_toolkit",
        **kwargs: Any,
    ):
        # Initialize configuration
        self._api_key = api_key or os.getenv("YOUR_API_KEY")
        if not self._api_key:
            raise ValueError("API key is required")
        
        # Initialize standard configuration
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=1800
        )
        
        # Define available tools
        available_tools = [self.your_method]
        
        # Initialize Toolkit
        super().__init__(name=name, tools=available_tools, **kwargs)
        
        # Initialize data helpers  
        self._init_data_helpers(
            data_dir="./data/your_toolkit",
            parquet_threshold=1000,
            file_prefix="your_"
        )

    async def your_method(self, param: str) -> Dict[str, Any]:
        """Your method description."""
        try:
            # Implementation here
            pass
        except Exception as e:
            logger.error(f"Failed to execute method: {e}")
            return self.response_builder.api_error_response(
                api_endpoint="/your/endpoint",
                api_message=f"Method failed: {str(e)}"
            )
```

## Step-by-Step Implementation

### Step 1: Implement Your Toolkit Class

Create `src/sentientresearchagent/hierarchical_agent_framework/toolkits/data/your_toolkit.py`:

```python
class YourToolkit(Toolkit, BaseDataToolkit, BaseAPIToolkit):
    """Your comprehensive toolkit description."""

    def __init__(self, api_key: str, param1: str = "default", **kwargs):
        # 1. Validate required parameters
        self._api_key = api_key or os.getenv("YOUR_API_KEY")
        if not self._api_key:
            raise ValueError("API key required")
        
        # 2. Initialize standard configuration (HTTP client, cache, etc.)
        self._init_standard_configuration(
            http_timeout=30.0,
            max_retries=3,
            retry_delay=1.0,
            cache_ttl_seconds=1800
        )
        
        # 3. Define your methods as tools
        available_tools = [
            self.get_data,
            self.search_items,
            self.analyze_trends,
        ]
        
        # 4. Initialize Toolkit parent class
        super().__init__(name=kwargs.get('name', 'your_toolkit'), tools=available_tools, **kwargs)
        
        # 5. Initialize data management helpers
        self._init_data_helpers(
            data_dir=kwargs.get('data_dir', './data/your_toolkit'),
            parquet_threshold=kwargs.get('parquet_threshold', 1000),
            file_prefix="your_"
        )
        
        # 6. Initialize statistical analyzer
        self.stats = StatisticalAnalyzer()
```

### Step 2: Implement Your Methods

Each method should follow this pattern:

```python
async def get_data(
    self,
    query: str,
    limit: int = 100,
    optional_param: Optional[str] = None
) -> Dict[str, Any]:
    """Get data from your API.
    
    Args:
        query: Search query
        limit: Maximum results (1-1000)
        optional_param: Optional parameter
        
    Returns:
        dict: API response or file path for large datasets
    """
    try:
        # 1. Validate parameters
        if limit <= 0 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        
        # 2. Prepare API request
        api_params = {
            "q": query,
            "limit": limit
        }
        if optional_param:
            api_params["optional"] = optional_param
        
        # 3. Make API request
        data = await self._make_api_request("/your/endpoint", api_params)
        
        # 4. Process response
        results_list = data.get("results", [])
        
        # 5. Build base response
        base_response = {
            "success": True,
            "query": query,
            "limit": limit,
            "count": len(results_list),
            "fetched_at": BaseAPIToolkit.unix_to_iso(time.time())
        }
        
        # 6. Add analysis if relevant
        analysis = {}
        if results_list:
            # Add your analysis here
            analysis["trend"] = "increasing"  # example
        
        # 7. Handle large datasets with Parquet storage
        filename_template = FileNameGenerator.generate_data_filename(
            "data_export", query, "filtered", {"limit": limit},
            file_prefix=self._file_prefix
        )
        
        return self.response_builder.build_data_response_with_storage(
            data=results_list,
            storage_threshold=self._parquet_threshold,
            storage_callback=lambda data, filename: self._store_parquet(data, filename),
            filename_template=filename_template,
            large_data_note="Large dataset stored as Parquet file",
            **base_response,
            analysis=analysis
        )
        
    except Exception as e:
        logger.error(f"Failed to get data: {e}")
        return self.response_builder.api_error_response(
            api_endpoint="/your/endpoint",
            api_message=f"Failed to get data: {str(e)}",
            query=query
        )
```

### Step 3: Add Module Exports

Update `src/sentientresearchagent/hierarchical_agent_framework/toolkits/data/__init__.py`:

```python
from __future__ import annotations
from .binance_toolkit import BinanceToolkit
from .coingecko_toolkit import CoinGeckoToolkit
from .arkham_toolkit import ArkhamToolkit
from .your_toolkit import YourToolkit  # Add this line

__all__ = [
    "BinanceToolkit",
    "CoinGeckoToolkit",
    "ArkhamToolkit", 
    "YourToolkit",  # Add this line
]
```

Update `src/sentientresearchagent/hierarchical_agent_framework/toolkits/__init__.py`:

```python
# Add to imports
from .data import (
    BinanceToolkit,
    CoinGeckoToolkit,
    ArkhamToolkit,
    YourToolkit,  # Add this line
)

# Add to __all__
__all__ = [
    # ...existing items...
    "YourToolkit",  # Add this line
]
```

## Configuration & Registration

### Step 4: Create Pydantic Configuration Model

Add to `src/sentientresearchagent/hierarchical_agent_framework/agent_configs/models.py`:

```python
class YourToolkitParams(BaseDataToolkitParams):
    """Parameters for YourToolkit configuration."""
    
    # Override base class defaults
    data_dir: Union[str, Path] = Field(
        "./data/your_toolkit",
        description="Directory for storing parquet files"
    )
    
    # Your toolkit-specific parameters
    api_key: str = Field(
        default_factory=lambda: os.getenv("YOUR_API_KEY") or "",
        min_length=10,
        description="Your API key"
    )
    base_url: str = Field(
        "https://api.yourservice.com",
        description="Base URL for API"
    )
    default_param: str = Field(
        "default_value",
        description="Default parameter value"
    )
    
    @model_validator(mode='after')
    def validate_required_credentials(self):
        """Validate required credentials."""
        if not self.api_key:
            raise ValueError("API key is required. Set YOUR_API_KEY environment variable.")
        return self
    
    @classmethod
    def get_valid_tools(cls) -> List[str]:
        """Return list of valid tools for YourToolkit."""
        return [
            "get_data", "search_items", "analyze_trends"
        ]

# Add to toolkit registry
def get_toolkit_params_class(cls, name: str) -> Type[BaseModel]:
    """Get the appropriate parameter class for a toolkit name."""
    toolkit_registry = {
        "BinanceToolkit": BinanceToolkitParams,
        "CoingeckoToolkit": CoingeckoToolkitParams,
        "ArkhamToolkit": ArkhamToolkitParams,
        "YourToolkit": YourToolkitParams,  # Add this line
    }
    return toolkit_registry.get(name)

# Add to exports
__all__ = [
    # ...existing items...
    "YourToolkitParams",  # Add this line
]
```

### Step 5: Register in Agent Factory

Update `src/sentientresearchagent/hierarchical_agent_framework/agent_configs/agent_factory.py`:

```python
# Add to imports
from sentientresearchagent.hierarchical_agent_framework.toolkits.data import (
    BinanceToolkit, CoinGeckoToolkit, ArkhamToolkit, YourToolkit  # Add YourToolkit
)

# Add to __init__ method
self._toolkits = {
    "BinanceToolkit": BinanceToolkit,
    "CoingeckoToolkit": CoinGeckoToolkit,
    "ArkhamToolkit": ArkhamToolkit,
    "YourToolkit": YourToolkit,  # Add this line
}
```

## Testing

### Step 6: Create Comprehensive Tests

Create `src/sentientresearchagent/hierarchical_agent_framework/toolkits/tests/test_your_toolkit.py`:

```python
"""
Comprehensive tests for YourToolkit.
"""
import pytest
import os
from unittest.mock import Mock, AsyncMock, patch

# Mock dependencies before imports
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies."""
    mock_modules = {
        'agno.tools': Mock(),
        'agno.utils.log': Mock(),
    }
    
    with patch.dict('sys.modules', mock_modules), \
         patch('path.to.your_toolkit.Toolkit', Mock()), \
         patch('path.to.your_toolkit.BaseDataToolkit', Mock()):
        yield

from your_toolkit_path import YourToolkit

class TestYourToolkitInitialization:
    """Test initialization and configuration."""
    
    def test_requires_api_key(self):
        """Test that API key is required."""
        with pytest.raises(ValueError, match="API key required"):
            YourToolkit()
    
    def test_basic_initialization(self):
        """Test basic initialization."""
        toolkit = YourToolkit(api_key="test_key")
        assert toolkit._api_key == "test_key"

class TestYourToolkitMethods:
    """Test toolkit methods."""
    
    @pytest.fixture
    def toolkit(self):
        """Create toolkit for testing."""
        return YourToolkit(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_get_data_success(self, toolkit):
        """Test successful data retrieval."""
        with patch.object(toolkit, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"results": [{"id": 1, "name": "test"}]}
            
            result = await toolkit.get_data("test_query")
            
            assert result["success"] == True
            assert result["query"] == "test_query"
```

### Step 7: Run Tests

```bash
# Run your specific tests
python -m pytest src/sentientresearchagent/hierarchical_agent_framework/toolkits/tests/test_your_toolkit.py -v

# Run all toolkit tests
python -m pytest src/sentientresearchagent/hierarchical_agent_framework/toolkits/tests/ -v
```

## Best Practices

### Code Organization

1. **Follow existing patterns** - Study `arkham_toolkit.py`, `binance_toolkit.py`, and `coingecko_toolkit.py`
2. **Use base classes** - Inherit from `BaseDataToolkit` and `BaseAPIToolkit`
3. **Consistent naming** - Use clear, descriptive method and parameter names
4. **Type hints** - Use comprehensive type annotations

### Error Handling

```python
try:
    # Your logic here
    pass
except SpecificAPIError as e:
    logger.error(f"API error: {e}")
    return self.response_builder.api_error_response(...)
except ValidationError as e:
    logger.error(f"Validation error: {e}")
    return self.response_builder.validation_error_response(...)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return self.response_builder.general_error_response(...)
```

### Parameter Validation

```python
# Always validate parameters
if limit <= 0 or limit > 1000:
    raise ValueError("Limit must be between 1 and 1000")

if not query or not isinstance(query, str):
    raise ValueError("Query must be a non-empty string")

# Use enum for restricted options
class SortOption(str, Enum):
    PRICE = "price"
    VOLUME = "volume"
    DATE = "date"
```

### Data Management

```python
# Use the storage system for large datasets
return self.response_builder.build_data_response_with_storage(
    data=large_dataset,
    storage_threshold=self._parquet_threshold,
    storage_callback=lambda data, filename: self._store_parquet(data, filename),
    filename_template=filename_template,
    **base_response
)
```

### Documentation

```python
async def your_method(
    self,
    required_param: str,
    optional_param: Optional[int] = None
) -> Dict[str, Any]:
    """Brief description of what this method does.
    
    Longer description explaining the purpose, behavior,
    and any important details about the method.
    
    Args:
        required_param: Description of required parameter
        optional_param: Description of optional parameter
        
    Returns:
        dict: Description of return value structure
        
    Raises:
        ValueError: When parameter validation fails
        APIError: When API request fails
        
    Example:
        ```python
        result = await toolkit.your_method("example_query")
        if result["success"]:
            data = result["data"]  # or result["file_path"] for large datasets
        ```
    """
```

## Examples

### YAML Configuration Example

```yaml
agents:
  your_agent:
    type: "executor"
    model:
      provider: "litellm"
      model_id: "openai/gpt-4"
    toolkits:
      - name: "YourToolkit"
        params:
          api_key: "${YOUR_API_KEY}"
          base_url: "https://api.yourservice.com"
          data_dir: "./data/your_toolkit"
          parquet_threshold: 1000
          default_param: "custom_value"
        available_tools:
          - "get_data"
          - "search_items"
          - "analyze_trends"
```

### Usage in Agent Prompts

```python
# Agent can use your toolkit methods
results = await your_toolkit.get_data(
    query="market analysis",
    limit=100
)

if results["success"]:
    if "data" in results:
        # Small dataset returned directly
        for item in results["data"]:
            process_item(item)
    elif "file_path" in results:
        # Large dataset stored as Parquet
        df = pd.read_parquet(results["file_path"])
        analyze_dataframe(df)
```

## Checklist

Before submitting your toolkit:

- [ ] **Implementation**
  - [ ] Inherits from `BaseDataToolkit` and `BaseAPIToolkit`
  - [ ] Uses `_init_standard_configuration()` and `_init_data_helpers()`
  - [ ] Implements error handling with `ResponseBuilder`
  - [ ] Supports large dataset storage with Parquet
  - [ ] Includes statistical analysis where relevant
  - [ ] Has comprehensive parameter validation
  
- [ ] **Configuration**
  - [ ] Created Pydantic params model in `models.py`
  - [ ] Added to toolkit registry in `agent_factory.py`
  - [ ] Added to module exports in `__init__.py` files
  - [ ] Supports environment variable configuration
  
- [ ] **Testing**
  - [ ] Created comprehensive test file
  - [ ] Tests initialization, validation, and methods
  - [ ] Tests error handling and edge cases
  - [ ] All tests pass
  
- [ ] **Documentation**
  - [ ] Clear docstrings for all methods
  - [ ] Parameter descriptions and examples
  - [ ] Return value documentation
  - [ ] YAML configuration example

## Getting Help

- **Study existing toolkits**: Look at `arkham_toolkit.py`, `binance_toolkit.py`, and `coingecko_toolkit.py` for patterns
- **Check base classes**: Review `BaseDataToolkit` and `BaseAPIToolkit` for available methods
- **Run existing tests**: Use `pytest` to understand expected behavior
- **Review agent configurations**: Look at `agents.yaml` for integration examples

## Summary

Following this guide ensures your toolkit:
- **Integrates seamlessly** with the agent framework
- **Follows established patterns** and best practices  
- **Supports YAML configuration** for easy agent setup
- **Handles large datasets efficiently** with Parquet storage
- **Provides rich statistical analysis** capabilities
- **Has comprehensive testing** and error handling

Your toolkit will be ready for production use in the SentientResearchAgent framework!