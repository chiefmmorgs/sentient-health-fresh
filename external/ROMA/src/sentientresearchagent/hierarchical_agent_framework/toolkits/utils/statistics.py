from __future__ import annotations

"""Statistical Analysis Helper for Data Toolkits
==============================================

A dedicated class for common statistical operations used across cryptocurrency
and financial data toolkits. Provides standardized statistical analysis,
technical indicators, and data processing functions using NumPy.

Key Features:
- Price and volume statistical analysis
- Technical indicators (RSI, SMA, volatility)
- Return and risk metrics calculation
- OHLCV data processing
- Market analysis patterns
"""

import time
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

import numpy as _np
from loguru import logger

__all__ = ["StatisticalAnalyzer"]


class StatisticalAnalyzer:
    """Helper class for statistical analysis of financial time series data.
    
    Provides reusable statistical analysis functions that are commonly needed
    across different cryptocurrency and financial data toolkits. All methods
    are static/class methods to allow easy integration without inheritance.
    
    Example:
        ```python
        class MyDataToolkit(Toolkit, BaseDataToolkit):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.stats = StatisticalAnalyzer()
                
            async def analyze_prices(self, prices):
                stats = self.stats.calculate_price_statistics(prices)
                return stats
        ```
    """

    @staticmethod
    def calculate_price_statistics(prices: _np.ndarray) -> Dict[str, Any]:
        """Calculate comprehensive price statistics.
        
        Args:
            prices: Array of price values
            
        Returns:
            dict: Price statistics including basic stats and distributions
        """
        if len(prices) == 0:
            return {}
            
        return {
            "min": float(_np.min(prices)),
            "max": float(_np.max(prices)),
            "mean": float(_np.mean(prices)),
            "median": float(_np.median(prices)),
            "std_dev": float(_np.std(prices)),
            "variance": float(_np.var(prices)),
            "range": float(_np.max(prices) - _np.min(prices)),
            "coefficient_of_variation": float(_np.std(prices) / _np.mean(prices)) if _np.mean(prices) != 0 else 0,
            "skewness": StatisticalAnalyzer._calculate_skewness(prices),
            "kurtosis": StatisticalAnalyzer._calculate_kurtosis(prices)
        }

    @staticmethod
    def calculate_returns_analysis(prices: _np.ndarray, timestamps: Optional[_np.ndarray] = None) -> Dict[str, Any]:
        """Calculate returns and risk metrics.
        
        Args:
            prices: Array of price values
            timestamps: Optional array of timestamps for period calculation
            
        Returns:
            dict: Returns analysis including total return, volatility, and risk metrics
        """
        if len(prices) <= 1:
            return {}
            
        # Calculate returns with protection against division by zero
        with _np.errstate(divide='ignore', invalid='ignore'):
            returns = _np.diff(prices) / prices[:-1]
            returns = _np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
            total_return = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0.0
        
        # Calculate max drawdown with protection against division by zero
        running_max = _np.maximum.accumulate(prices)
        with _np.errstate(divide='ignore', invalid='ignore'):
            drawdowns = (prices - running_max) / running_max
            drawdowns = _np.nan_to_num(drawdowns, nan=0.0, posinf=0.0, neginf=0.0)
        max_drawdown = float(_np.min(drawdowns))
        
        # Determine period length for annualization
        period_days = len(prices)  # Default assumption: 1 price point = 1 day
        if timestamps is not None and len(timestamps) >= 2:
            period_seconds = (timestamps[-1] - timestamps[0]) / 1000  # Assuming milliseconds
            period_days = period_seconds / 86400  # Convert to days
        
        # Calculate annualization factor with safeguards
        # Note: Without timestamps, we assume each price represents 1 day
        # This may not be accurate for intraday data (hourly, minutely, etc.)
        annualization_factor = 365 / period_days if period_days > 0 else 1
        
        # Cap unrealistic annualized returns (occurs when period is very short)
        raw_annualized_return = ((1 + total_return) ** annualization_factor - 1) * 100
        # If annualized return is extreme (>1000% or <-90%), mark as unreliable
        annualized_return_pct = raw_annualized_return if abs(raw_annualized_return) < 1000 else float('nan')
        
        return {
            "total_return_pct": float(total_return * 100),
            "annualized_return_pct": annualized_return_pct,
            "daily_returns_mean": float(_np.mean(returns) * 100),
            "daily_returns_std": float(_np.std(returns) * 100),
            "sharpe_ratio": float(_np.mean(returns) / _np.std(returns)) if _np.std(returns) != 0 else 0,
            "max_drawdown_pct": float(max_drawdown * 100),
            "downside_deviation": StatisticalAnalyzer._calculate_downside_deviation(returns),
            "sortino_ratio": StatisticalAnalyzer._calculate_sortino_ratio(returns)
        }

    @staticmethod
    def calculate_volatility_metrics(prices: _np.ndarray, window: int = 30) -> Dict[str, Any]:
        """Calculate volatility metrics including rolling volatility.
        
        Args:
            prices: Array of price values
            window: Rolling window size for calculations
            
        Returns:
            dict: Volatility metrics and regime classification
        """
        if len(prices) <= 1:
            return {}
            
        # Calculate returns with numerical stability  
        with _np.errstate(divide='ignore', invalid='ignore'):
            returns = _np.diff(prices) / prices[:-1]
            returns = _np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)
        daily_vol = _np.std(returns) * 100
        annualized_vol = daily_vol * _np.sqrt(365)
        
        # Rolling volatility if we have enough data
        rolling_vol = None
        if len(returns) >= window:
            rolling_returns = []
            for i in range(window, len(returns) + 1):
                window_returns = returns[i-window:i]
                rolling_returns.append(_np.std(window_returns))
            rolling_vol = float(_np.mean(rolling_returns) * 100)
        
        return {
            "daily_volatility_pct": float(daily_vol),
            "annualized_volatility_pct": float(annualized_vol),
            "volatility_regime": StatisticalAnalyzer._classify_volatility_regime(daily_vol),
            "rolling_volatility_30d": rolling_vol or float(daily_vol),
            "garch_volatility": StatisticalAnalyzer._estimate_garch_volatility(returns)
        }

    @staticmethod
    def calculate_volume_statistics(volumes: _np.ndarray, prices: Optional[_np.ndarray] = None) -> Dict[str, Any]:
        """Calculate volume-related statistics.
        
        Args:
            volumes: Array of volume values
            prices: Optional array of prices for correlation analysis
            
        Returns:
            dict: Volume statistics and analysis
        """
        if len(volumes) == 0:
            return {}
            
        stats = {
            "avg_daily_volume": float(_np.mean(volumes)),
            "volume_volatility": float(_np.std(volumes)),
            "volume_trend": "increasing" if volumes[-1] > volumes[0] else "decreasing",
            "volume_spike_threshold": float(_np.mean(volumes) + 2 * _np.std(volumes)),
            "volume_distribution": StatisticalAnalyzer._analyze_volume_distribution(volumes)
        }
        
        # Price-volume correlation if prices provided
        if prices is not None and len(prices) > 1 and len(volumes) > 1:
            # Calculate price returns with protection against division by zero
            with _np.errstate(divide='ignore', invalid='ignore'):
                price_returns = _np.diff(prices) / prices[:-1] if len(prices) > 1 else _np.array([0])
                # Replace inf and -inf with 0, and handle NaN
                price_returns = _np.nan_to_num(price_returns, nan=0.0, posinf=0.0, neginf=0.0)
                
                # Calculate volume changes with protection against division by zero
                volume_changes = _np.diff(volumes) / volumes[:-1] if len(volumes) > 1 else _np.array([0])
                # Replace inf and -inf with 0, and handle NaN
                volume_changes = _np.nan_to_num(volume_changes, nan=0.0, posinf=0.0, neginf=0.0)
            
            if len(price_returns) > 1 and len(volume_changes) > 1:
                min_len = min(len(price_returns), len(volume_changes))
                # Additional check to ensure we have valid data for correlation
                price_slice = price_returns[:min_len]
                volume_slice = volume_changes[:min_len]
                
                # Only calculate correlation if we have non-zero variance in both arrays
                if _np.var(price_slice) > 1e-10 and _np.var(volume_slice) > 1e-10:
                    try:
                        correlation = _np.corrcoef(price_slice, volume_slice)[0, 1]
                        stats["volume_price_correlation"] = float(correlation) if not _np.isnan(correlation) else 0.0
                    except (ValueError, ZeroDivisionError):
                        stats["volume_price_correlation"] = 0.0
                else:
                    stats["volume_price_correlation"] = 0.0
        
        return stats

    @staticmethod
    def calculate_technical_indicators(prices: _np.ndarray, volumes: Optional[_np.ndarray] = None) -> Dict[str, Any]:
        """Calculate common technical indicators.
        
        Args:
            prices: Array of price values
            volumes: Optional array of volume values
            
        Returns:
            dict: Technical indicators and signals
        """
        indicators = {}
        
        if len(prices) == 0:
            return indicators
            
        # Simple Moving Averages
        if len(prices) >= 20:
            sma_20 = _np.mean(prices[-20:])
            indicators["sma_20"] = float(sma_20)
            indicators["price_vs_sma_20"] = float(prices[-1] / sma_20)
            indicators["trend_direction"] = "bullish" if prices[-1] > sma_20 else "bearish"
            
        if len(prices) >= 50:
            sma_50 = _np.mean(prices[-50:])
            indicators["sma_50"] = float(sma_50)
            indicators["golden_cross"] = indicators.get("sma_20", 0) > sma_50
            
        # RSI calculation
        if len(prices) >= 14:
            rsi = StatisticalAnalyzer._calculate_rsi(prices, period=14)
            indicators["rsi_14"] = float(rsi)
            indicators["rsi_signal"] = StatisticalAnalyzer._classify_rsi_signal(rsi)
            
        # Bollinger Bands
        if len(prices) >= 20:
            bb_upper, bb_middle, bb_lower = StatisticalAnalyzer._calculate_bollinger_bands(prices)
            indicators["bollinger_upper"] = float(bb_upper)
            indicators["bollinger_middle"] = float(bb_middle)
            indicators["bollinger_lower"] = float(bb_lower)
            indicators["bollinger_position"] = StatisticalAnalyzer._calculate_bollinger_position(prices[-1], bb_upper, bb_lower)
            
        # VWAP if volumes available
        if volumes is not None and len(volumes) == len(prices):
            vwap = StatisticalAnalyzer.calculate_vwap(prices, volumes)
            indicators["vwap"] = float(vwap)
            indicators["price_vs_vwap"] = float(prices[-1] / vwap) if vwap > 0 else 1.0
            
        return indicators

    @staticmethod
    def calculate_ohlcv_summary(prices: _np.ndarray, volumes: Optional[_np.ndarray] = None, 
                               timestamps: Optional[_np.ndarray] = None) -> Dict[str, Any]:
        """Calculate OHLCV summary statistics.
        
        Args:
            prices: Array of price values
            volumes: Optional array of volume values
            timestamps: Optional array of timestamps
            
        Returns:
            dict: OHLCV summary with derived metrics
        """
        if len(prices) == 0:
            return {}
            
        summary = {
            "open": float(prices[0]),
            "high": float(_np.max(prices)),
            "low": float(_np.min(prices)),
            "close": float(prices[-1]),
            "volume": float(_np.sum(volumes)) if volumes is not None else None,
            "typical_price": float((_np.max(prices) + _np.min(prices) + prices[-1]) / 3),
            "price_range_pct": float((_np.max(prices) - _np.min(prices)) / _np.min(prices) * 100)
        }
        
        if volumes is not None:
            summary["vwap"] = float(StatisticalAnalyzer.calculate_vwap(prices, volumes))
            summary["volume_profile"] = StatisticalAnalyzer._calculate_volume_profile(prices, volumes)
            
        if timestamps is not None and len(timestamps) >= 2:
            duration_hours = (timestamps[-1] - timestamps[0]) / (1000 * 3600)  # Assuming milliseconds
            summary["duration_hours"] = float(duration_hours)
            summary["data_frequency"] = len(prices) / duration_hours if duration_hours > 0 else 0
            
        return summary

    @staticmethod
    def calculate_vwap(prices: _np.ndarray, volumes: _np.ndarray) -> float:
        """Calculate Volume-Weighted Average Price.
        
        Args:
            prices: Array of price values
            volumes: Array of volume values
            
        Returns:
            float: VWAP value
        """
        if volumes is None or len(volumes) == 0:
            return float(_np.mean(prices))
        
        total_volume = _np.sum(volumes)
        if total_volume == 0:
            return float(_np.mean(prices))
        
        weighted_prices = prices * volumes
        vwap = _np.sum(weighted_prices) / total_volume
        return float(vwap)

    @staticmethod
    def analyze_price_trends(prices: _np.ndarray, window: int = 20) -> Dict[str, Any]:
        """Analyze price trends and momentum.
        
        Args:
            prices: Array of price values
            window: Window size for trend analysis
            
        Returns:
            dict: Trend analysis results
        """
        if len(prices) < window:
            return {}
            
        # Linear regression for trend
        x = _np.arange(len(prices))
        slope, intercept = _np.polyfit(x, prices, 1)
        
        # Momentum analysis
        momentum = (prices[-1] - prices[-window]) / prices[-window] * 100
        
        # Support and resistance levels
        recent_prices = prices[-window:]
        support = float(_np.min(recent_prices))
        resistance = float(_np.max(recent_prices))
        
        return {
            "trend_slope": float(slope),
            "trend_strength": abs(slope) / _np.mean(prices) * 100,
            "trend_direction": "bullish" if slope > 0 else "bearish" if slope < 0 else "sideways",
            "momentum_pct": float(momentum),
            "support_level": support,
            "resistance_level": resistance,
            "price_position": (prices[-1] - support) / (resistance - support) if resistance > support else 0.5
        }

    # Private helper methods
    @staticmethod
    def _calculate_skewness(data: _np.ndarray) -> float:
        """Calculate skewness of data distribution."""
        if len(data) < 3:
            return 0.0
        mean = _np.mean(data)
        std = _np.std(data)
        if std == 0:
            return 0.0
        return float(_np.mean(((data - mean) / std) ** 3))

    @staticmethod
    def _calculate_kurtosis(data: _np.ndarray) -> float:
        """Calculate kurtosis of data distribution."""
        if len(data) < 4:
            return 0.0
        mean = _np.mean(data)
        std = _np.std(data)
        if std == 0:
            return 0.0
        return float(_np.mean(((data - mean) / std) ** 4)) - 3.0

    @staticmethod
    def _calculate_downside_deviation(returns: _np.ndarray, target: float = 0.0) -> float:
        """Calculate downside deviation for Sortino ratio."""
        downside_returns = returns[returns < target]
        if len(downside_returns) == 0:
            return 0.0
        return float(_np.sqrt(_np.mean((downside_returns - target) ** 2)) * 100)

    @staticmethod
    def _calculate_sortino_ratio(returns: _np.ndarray, target: float = 0.0) -> float:
        """Calculate Sortino ratio."""
        excess_return = _np.mean(returns) - target
        downside_dev = StatisticalAnalyzer._calculate_downside_deviation(returns, target) / 100
        return float(excess_return / downside_dev) if downside_dev != 0 else 0.0

    @staticmethod
    def _classify_volatility_regime(daily_vol_pct: float) -> str:
        """Classify volatility regime."""
        if daily_vol_pct > 5:
            return "high"
        elif daily_vol_pct > 2:
            return "moderate"
        else:
            return "low"

    @staticmethod
    def _estimate_garch_volatility(returns: _np.ndarray, alpha: float = 0.1, beta: float = 0.85) -> float:
        """Simple GARCH(1,1) volatility estimate."""
        if len(returns) < 10:
            return float(_np.std(returns) * 100)
        
        # Simple GARCH estimation
        long_run_var = _np.var(returns)
        garch_var = long_run_var
        
        for ret in returns[-10:]:  # Use last 10 observations
            garch_var = (1 - alpha - beta) * long_run_var + alpha * ret**2 + beta * garch_var
            
        return float(_np.sqrt(garch_var) * 100)

    @staticmethod
    def _calculate_rsi(prices: _np.ndarray, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0
            
        price_changes = _np.diff(prices[-(period+1):])
        gains = _np.where(price_changes > 0, price_changes, 0)
        losses = _np.where(price_changes < 0, -price_changes, 0)
        
        avg_gain = _np.mean(gains)
        avg_loss = _np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    @staticmethod
    def _classify_rsi_signal(rsi: float) -> str:
        """Classify RSI signal."""
        if rsi > 70:
            return "overbought"
        elif rsi < 30:
            return "oversold"
        else:
            return "neutral"

    @staticmethod
    def _calculate_bollinger_bands(prices: _np.ndarray, period: int = 20, std_dev: float = 2) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            mean_price = _np.mean(prices)
            std_price = _np.std(prices)
        else:
            mean_price = _np.mean(prices[-period:])
            std_price = _np.std(prices[-period:])
        
        upper = mean_price + (std_dev * std_price)
        lower = mean_price - (std_dev * std_price)
        
        return upper, mean_price, lower

    @staticmethod
    def _calculate_bollinger_position(price: float, upper: float, lower: float) -> float:
        """Calculate position within Bollinger Bands (0-1)."""
        if upper == lower:
            return 0.5
        return (price - lower) / (upper - lower)

    @staticmethod
    def _analyze_volume_distribution(volumes: _np.ndarray) -> Dict[str, float]:
        """Analyze volume distribution patterns."""
        percentiles = [10, 25, 50, 75, 90]
        volume_percentiles = _np.percentile(volumes, percentiles)
        
        return {
            f"p{p}": float(vol) for p, vol in zip(percentiles, volume_percentiles)
        }

    @staticmethod
    def _calculate_volume_profile(prices: _np.ndarray, volumes: _np.ndarray, bins: int = 10) -> Dict[str, Any]:
        """Calculate volume profile by price levels."""
        if len(prices) != len(volumes) or len(prices) == 0:
            return {}
            
        # Create price bins
        price_min, price_max = _np.min(prices), _np.max(prices)
        if price_min == price_max:
            return {"poc": float(price_min), "high_volume_node": float(price_min)}
        
        bin_edges = _np.linspace(price_min, price_max, bins + 1)
        volume_by_price = _np.zeros(bins)
        
        for i, price in enumerate(prices):
            bin_idx = min(int((price - price_min) / (price_max - price_min) * bins), bins - 1)
            volume_by_price[bin_idx] += volumes[i]
        
        # Point of Control (highest volume)
        poc_idx = _np.argmax(volume_by_price)
        poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
        
        return {
            "poc": float(poc_price),
            "high_volume_node": float(poc_price),
            "volume_distribution": volume_by_price.tolist()
        }

    # =========================================================================
    # Market Analysis Helpers (moved from base_api.py for proper separation)
    # =========================================================================

    @staticmethod
    def analyze_market_performance(data: List[Dict[str, Any]], price_field: str = "price") -> Dict[str, Any]:
        """Analyze market performance from a list of market data.
        
        Args:
            data: List of market data dictionaries
            price_field: Field name containing price data
            
        Returns:
            dict: Performance analysis summary
        """
        if not data:
            return {}
            
        analysis = {}
        
        # Extract price changes if available
        changes = []
        for item in data:
            change_fields = [f"{price_field}_change_24h", "price_change_percentage_24h", "change_24h", "priceChangePercent"]
            for field in change_fields:
                if field in item and item[field] is not None:
                    changes.append(float(item[field]))
                    break
        
        if changes:
            analysis.update({
                "avg_change_24h": sum(changes) / len(changes),
                "positive_count": sum(1 for c in changes if c > 0),
                "negative_count": sum(1 for c in changes if c < 0),
                "neutral_count": sum(1 for c in changes if c == 0),
                "best_performer": max(data, key=lambda x: StatisticalAnalyzer._get_change_value(x), default={}),
                "worst_performer": min(data, key=lambda x: StatisticalAnalyzer._get_change_value(x), default={})
            })
        
        # Market cap analysis if available
        market_caps = []
        for item in data:
            cap_fields = ["market_cap", "market_cap_usd", "marketCap", f"{price_field}_market_cap"]
            for field in cap_fields:
                if field in item and item[field] is not None:
                    market_caps.append(float(item[field]))
                    break
        
        if market_caps:
            analysis.update({
                "total_market_cap": sum(market_caps),
                "avg_market_cap": sum(market_caps) / len(market_caps),
                "market_cap_distribution": StatisticalAnalyzer._classify_market_cap_distribution(market_caps)
            })
        
        return analysis

    @staticmethod
    def _get_change_value(item: Dict[str, Any]) -> float:
        """Extract change value from market data item."""
        change_fields = ["price_change_percentage_24h", "change_24h", "priceChangePercent", "usd_24h_change"]
        for field in change_fields:
            if field in item and item[field] is not None:
                return float(item[field])
        return 0.0

    @staticmethod
    def _classify_market_cap_distribution(market_caps: List[float]) -> Dict[str, int]:
        """Classify market cap distribution into tiers."""
        large_cap = sum(1 for cap in market_caps if cap > 10_000_000_000)  # >$10B
        mid_cap = sum(1 for cap in market_caps if 1_000_000_000 <= cap <= 10_000_000_000)  # $1B-$10B
        small_cap = sum(1 for cap in market_caps if cap < 1_000_000_000)  # <$1B
        
        return {
            "large_cap": large_cap,
            "mid_cap": mid_cap,
            "small_cap": small_cap
        }

    @staticmethod
    def classify_trend_from_change(change_pct: float) -> str:
        """Classify trend based on percentage change."""
        if change_pct > 0:
            return "bullish"
        elif change_pct < 0:
            return "bearish"
        else:
            return "neutral"

    @staticmethod
    def classify_volatility_from_change(change_pct: float) -> str:
        """Classify volatility based on percentage change."""
        abs_change = abs(change_pct)
        if abs_change > 10:
            return "high"
        elif abs_change > 3:
            return "moderate"
        else:
            return "low"
    
    @staticmethod
    def calculate_gini_coefficient(values: _np.ndarray) -> float:
        """Calculate Gini coefficient for wealth/asset distribution.
        
        The Gini coefficient is a measure of inequality within a distribution.
        It ranges from 0 (perfect equality) to 1 (perfect inequality).
        
        Args:
            values: Array of values (e.g., token balances, wealth amounts)
            
        Returns:
            float: Gini coefficient between 0 and 1
        """
        if len(values) == 0:
            return 0.0
        
        # Sort values
        sorted_values = _np.sort(values)
        n = len(sorted_values)
        
        # Calculate total sum
        total = _np.sum(sorted_values)
        if total == 0:
            return 0.0
        
        # Calculate cumulative sum weighted by index
        cumsum = _np.sum((2 * _np.arange(1, n + 1) - n - 1) * sorted_values)
        
        # Gini coefficient formula
        gini = cumsum / (n * total)
        
        return float(max(0.0, min(1.0, gini)))  # Clamp between 0 and 1
    
    @staticmethod
    def calculate_distribution_stats(values: _np.ndarray) -> Dict[str, float]:
        """Calculate distribution statistics for any array of values.
        
        Args:
            values: Array of numeric values
            
        Returns:
            dict: Distribution statistics including percentiles and spread
        """
        if len(values) == 0:
            return {}
        
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        stats = {}
        
        for p in percentiles:
            stats[f"p{p}"] = float(_np.percentile(values, p))
        
        stats.update({
            "mean": float(_np.mean(values)),
            "median": float(_np.median(values)),  # Added median field
            "std": float(_np.std(values)),
            "min": float(_np.min(values)),
            "max": float(_np.max(values)),
            "range": float(_np.max(values) - _np.min(values)),
            "iqr": float(_np.percentile(values, 75) - _np.percentile(values, 25)),
            "gini_coefficient": StatisticalAnalyzer.calculate_gini_coefficient(values)
        })
        
        return stats

    # =========================================================================
    # Generic Analysis Orchestration (leverages existing methods)
    # =========================================================================

    @staticmethod
    def build_analysis_report(
        prices: _np.ndarray,
        volumes: Optional[_np.ndarray] = None,
        timestamps: Optional[_np.ndarray] = None,
        analysis_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generic analysis report builder that orchestrates existing methods.
        
        Args:
            prices: Array of price values
            volumes: Optional array of volume values
            timestamps: Optional array of timestamps
            analysis_types: List of analysis types to include
                          Options: ["price_stats", "returns", "volatility", "technical", 
                                   "volume", "ohlcv", "trends", "market_performance"]
                          If None, includes all available analyses
            
        Returns:
            dict: Orchestrated analysis report using existing methods
        """
        if len(prices) == 0:
            return {"error": "No price data provided"}
        
        # Default to all analysis types if none specified
        if analysis_types is None:
            analysis_types = ["price_stats", "returns", "volatility", "technical", "volume", "ohlcv", "trends"]
        
        report = {}
        
        # Price statistics (always available)
        if "price_stats" in analysis_types:
            report["price_statistics"] = StatisticalAnalyzer.calculate_price_statistics(prices)
        
        # Returns analysis (requires >1 price point)
        if "returns" in analysis_types and len(prices) > 1:
            report["returns_analysis"] = StatisticalAnalyzer.calculate_returns_analysis(prices, timestamps)
        
        # Volatility metrics (requires >1 price point)
        if "volatility" in analysis_types and len(prices) > 1:
            report["volatility_metrics"] = StatisticalAnalyzer.calculate_volatility_metrics(prices)
        
        # Technical indicators (requires sufficient data)
        if "technical" in analysis_types and len(prices) >= 14:
            report["technical_indicators"] = StatisticalAnalyzer.calculate_technical_indicators(prices, volumes)
        
        # Volume analysis (requires volume data)
        if "volume" in analysis_types and volumes is not None and len(volumes) > 0:
            report["volume_statistics"] = StatisticalAnalyzer.calculate_volume_statistics(volumes, prices)
        
        # OHLCV summary
        if "ohlcv" in analysis_types:
            report["ohlcv_summary"] = StatisticalAnalyzer.calculate_ohlcv_summary(prices, volumes, timestamps)
        
        # Trend analysis (requires sufficient data)
        if "trends" in analysis_types and len(prices) >= 20:
            report["trend_analysis"] = StatisticalAnalyzer.analyze_price_trends(prices)
        
        # Add quick trend/volatility classifications for convenience
        if len(prices) > 1:
            price_change_pct = ((prices[-1] - prices[0]) / prices[0]) * 100
            cv = report.get("price_statistics", {}).get("coefficient_of_variation", 0) * 100
            
            report["quick_classifications"] = {
                "trend": StatisticalAnalyzer.classify_trend_from_change(price_change_pct),
                "volatility": StatisticalAnalyzer.classify_volatility_from_change(cv),
                "price_change_pct": float(price_change_pct)
            }
        
        # Meta information
        report["analysis_metadata"] = {
            "data_points": len(prices),
            "has_volume_data": volumes is not None and len(volumes) > 0,
            "has_timestamp_data": timestamps is not None and len(timestamps) > 0,
            "included_analyses": analysis_types,
            "analysis_timestamp": int(time.time())
        }
        
        return report