"""
Hierarchical Agent Framework Toolkits

This package provides a comprehensive toolkit framework for the hierarchical agent system,
including base classes for building toolkits, utility modules for common functionality,
and specialized data toolkits for cryptocurrency market analysis.

Architecture:
- base/: Core base classes for building custom toolkits
- utils/: Reusable utility modules for common functionality  
- data/: Specialized data toolkits for various data sources
- tests/: Comprehensive test suite for all components

Usage:
    from sentientresearchagent.hierarchical_agent_framework.toolkits import (
        BaseDataToolkit, BaseAPIToolkit,  # Base classes
        DataValidator, ResponseBuilder,   # Utilities
        BinanceToolkit, CoinGeckoToolkit, ArkhamToolkit, DefiLlamaToolkit  # Data toolkits
    )
"""

# Base classes for building custom toolkits
from .base import (
    BaseDataToolkit,
    BaseAPIToolkit,
)

# Utility modules for common functionality
from .utils import (
    DataValidator,
    FileNameGenerator, 
    ResponseBuilder,
    DataHTTPClient,
    HTTPClientError,
    StatisticalAnalyzer,
)

# Specialized data toolkits
from .data import (
    BinanceToolkit,
    CoinGeckoToolkit,
    ArkhamToolkit,
    DefiLlamaToolkit,
)

# Comprehensive exports for easy importing
__all__ = [
    # Base classes
    "BaseDataToolkit",
    "BaseAPIToolkit",
    
    # Utility modules
    "DataValidator",
    "FileNameGenerator",
    "ResponseBuilder", 
    "DataHTTPClient",
    "HTTPClientError",
    "StatisticalAnalyzer",
    
    # Data toolkits
    "BinanceToolkit",
    "CoinGeckoToolkit",
    "ArkhamToolkit",
    "DefiLlamaToolkit",
]