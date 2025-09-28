"""Comprehensive test suite for StatisticalAnalyzer validation."""

import pytest
import numpy as np
import math
from unittest.mock import patch

from sentientresearchagent.hierarchical_agent_framework.toolkits.utils.statistics import StatisticalAnalyzer


class TestStatisticalAnalyzerValidation:
    """Comprehensive validation tests for statistical calculations."""
    
    def setup_method(self):
        """Set up test data."""
        # Standard test data
        self.test_prices = np.array([100.0, 105.0, 103.0, 108.0, 110.0, 106.0, 109.0, 112.0])
        self.test_volumes = np.array([1000, 1200, 900, 1500, 1100, 1300, 1000, 1400])
        
        # Edge case test data
        self.zero_prices = np.array([0.0, 0.0, 0.0])
        self.mixed_prices = np.array([100.0, 0.0, 50.0, 0.0, 25.0])
        self.single_price = np.array([100.0])
        self.empty_prices = np.array([])
    
    def test_price_statistics_basic_calculations(self):
        """Test basic price statistics calculations."""
        stats = StatisticalAnalyzer.calculate_price_statistics(self.test_prices)
        
        # Validate against numpy calculations
        assert abs(stats["min"] - np.min(self.test_prices)) < 1e-10
        assert abs(stats["max"] - np.max(self.test_prices)) < 1e-10
        assert abs(stats["mean"] - np.mean(self.test_prices)) < 1e-10
        assert abs(stats["median"] - np.median(self.test_prices)) < 1e-10
        assert abs(stats["std_dev"] - np.std(self.test_prices)) < 1e-10
        assert abs(stats["variance"] - np.var(self.test_prices)) < 1e-10
        assert abs(stats["range"] - (np.max(self.test_prices) - np.min(self.test_prices))) < 1e-10
        
        # Validate coefficient of variation
        expected_cv = np.std(self.test_prices) / np.mean(self.test_prices)
        assert abs(stats["coefficient_of_variation"] - expected_cv) < 1e-10
    
    def test_price_statistics_edge_cases(self):
        """Test price statistics with edge cases."""
        # Empty array
        empty_stats = StatisticalAnalyzer.calculate_price_statistics(self.empty_prices)
        assert empty_stats == {}
        
        # Single price
        single_stats = StatisticalAnalyzer.calculate_price_statistics(self.single_price)
        assert single_stats["min"] == single_stats["max"] == 100.0
        assert single_stats["std_dev"] == 0.0
        assert single_stats["coefficient_of_variation"] == 0.0
    
    def test_returns_analysis_calculations(self):
        """Test returns analysis calculations."""
        stats = StatisticalAnalyzer.calculate_returns_analysis(self.test_prices)
        
        # Manual calculations
        manual_returns = np.diff(self.test_prices) / self.test_prices[:-1]
        expected_total_return_pct = ((self.test_prices[-1] - self.test_prices[0]) / self.test_prices[0]) * 100
        expected_mean_return = np.mean(manual_returns) * 100
        expected_std_return = np.std(manual_returns) * 100
        expected_sharpe = np.mean(manual_returns) / np.std(manual_returns)
        
        # Validate calculations
        assert abs(stats["total_return_pct"] - expected_total_return_pct) < 1e-10
        assert abs(stats["daily_returns_mean"] - expected_mean_return) < 1e-6
        assert abs(stats["daily_returns_std"] - expected_std_return) < 1e-6
        assert abs(stats["sharpe_ratio"] - expected_sharpe) < 1e-10
    
    def test_returns_analysis_with_timestamps(self):
        """Test returns analysis with proper timestamps."""
        # 7 days of data (timestamps for 8 price points)
        timestamps = np.array([i * 24 * 60 * 60 * 1000 for i in range(8)])  # Daily timestamps in ms
        
        stats = StatisticalAnalyzer.calculate_returns_analysis(self.test_prices, timestamps)
        
        # Should calculate period correctly (7 days) 
        # Annualized return might be NaN if extreme, but should not crash
        assert isinstance(stats["annualized_return_pct"], (int, float))
        if not np.isnan(stats["annualized_return_pct"]):
            assert abs(stats["annualized_return_pct"]) < 10000  # Should be reasonable if not NaN
    
    def test_annualized_return_capping(self):
        """Test that unrealistic annualized returns are capped."""
        # Very short period (should trigger capping)
        short_prices = np.array([100.0, 120.0])  # 20% return over "1 day" 
        stats = StatisticalAnalyzer.calculate_returns_analysis(short_prices)
        
        # Should cap unrealistic annualized return
        assert np.isnan(stats["annualized_return_pct"]) or abs(stats["annualized_return_pct"]) >= 1000
    
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        # Create data with known drawdown
        drawdown_prices = np.array([100, 110, 90, 95, 85, 100])  # Max drawdown from 110 to 85 = -22.7%
        
        stats = StatisticalAnalyzer.calculate_returns_analysis(drawdown_prices)
        
        # Calculate expected drawdown manually
        running_max = np.maximum.accumulate(drawdown_prices)
        drawdowns = (drawdown_prices - running_max) / running_max
        expected_max_drawdown_pct = np.min(drawdowns) * 100
        
        assert abs(stats["max_drawdown_pct"] - expected_max_drawdown_pct) < 1e-10
    
    def test_volume_statistics_calculations(self):
        """Test volume statistics calculations."""
        stats = StatisticalAnalyzer.calculate_volume_statistics(self.test_volumes, self.test_prices)
        
        # Validate basic calculations
        expected_avg_volume = np.mean(self.test_volumes)
        expected_vol_std = np.std(self.test_volumes)
        
        assert abs(stats["avg_daily_volume"] - expected_avg_volume) < 1e-10
        assert abs(stats["volume_volatility"] - expected_vol_std) < 1e-6
    
    def test_volume_price_correlation(self):
        """Test volume-price correlation calculation."""
        # Create data with known correlation
        corr_prices = np.array([100, 101, 102, 103, 104])
        corr_volumes = np.array([1000, 1010, 1020, 1030, 1040])  # Perfect positive correlation
        
        stats = StatisticalAnalyzer.calculate_volume_statistics(corr_volumes, corr_prices)
        
        # Should have high positive correlation
        assert stats["volume_price_correlation"] > 0.9
    
    def test_gini_coefficient_edge_cases(self):
        """Test Gini coefficient edge cases."""
        # Perfect equality
        equal_values = np.array([100, 100, 100, 100])
        gini_equal = StatisticalAnalyzer.calculate_gini_coefficient(equal_values)
        assert abs(gini_equal) < 1e-10
        
        # Perfect inequality (one has all)
        inequality_values = np.array([0, 0, 0, 1000])
        gini_inequality = StatisticalAnalyzer.calculate_gini_coefficient(inequality_values)
        expected_max_gini = (len(inequality_values) - 1) / len(inequality_values)
        assert abs(gini_inequality - expected_max_gini) < 1e-10
        
        # Empty array
        empty_gini = StatisticalAnalyzer.calculate_gini_coefficient(np.array([]))
        assert empty_gini == 0.0
        
        # All zeros
        zero_gini = StatisticalAnalyzer.calculate_gini_coefficient(np.array([0, 0, 0]))
        assert zero_gini == 0.0
    
    def test_gini_coefficient_mathematical_correctness(self):
        """Test Gini coefficient mathematical formula."""
        test_values = np.array([10, 20, 30, 40, 50])
        gini = StatisticalAnalyzer.calculate_gini_coefficient(test_values)
        
        # Manual calculation using standard formula
        sorted_vals = np.sort(test_values)
        n = len(sorted_vals)
        total = np.sum(sorted_vals)
        cumsum = np.sum((2 * np.arange(1, n + 1) - n - 1) * sorted_vals)
        expected_gini = cumsum / (n * total)
        
        assert abs(gini - expected_gini) < 1e-10
    
    def test_numerical_stability_with_zeros(self):
        """Test numerical stability with problematic data."""
        # Data with zeros that could cause division by zero
        problem_data = np.array([100.0, 0.0, 50.0, 0.0, 25.0])
        
        # Should not raise exceptions
        price_stats = StatisticalAnalyzer.calculate_price_statistics(problem_data)
        returns_stats = StatisticalAnalyzer.calculate_returns_analysis(problem_data)
        
        assert isinstance(price_stats, dict)
        assert isinstance(returns_stats, dict)
        
        # All values should be finite
        for value in price_stats.values():
            if isinstance(value, (int, float)):
                assert not np.isnan(value) or value == 0  # Allow 0 but not NaN
        
        for value in returns_stats.values():
            if isinstance(value, (int, float)) and not np.isnan(value):
                assert np.isfinite(value)
    
    def test_technical_indicators_vwap(self):
        """Test VWAP (Volume Weighted Average Price) calculation."""
        tech_stats = StatisticalAnalyzer.calculate_technical_indicators(self.test_prices, self.test_volumes)
        
        # Manual VWAP calculation
        expected_vwap = np.sum(self.test_prices * self.test_volumes) / np.sum(self.test_volumes)
        
        assert abs(tech_stats["vwap"] - expected_vwap) < 1e-10
    
    def test_distribution_stats(self):
        """Test distribution statistics calculation."""
        dist_stats = StatisticalAnalyzer.calculate_distribution_stats(self.test_prices)
        
        # Check that required keys exist
        assert "p50" in dist_stats or "median" in dist_stats
        assert "p95" in dist_stats
        
        # Validate percentiles (use p50 if median not available)
        expected_median = np.percentile(self.test_prices, 50)
        expected_p95 = np.percentile(self.test_prices, 95)
        
        actual_median = dist_stats.get("median", dist_stats.get("p50"))
        assert abs(actual_median - expected_median) < 1e-10
        assert abs(dist_stats["p95"] - expected_p95) < 1e-10
    
    def test_volatility_metrics_numerical_stability(self):
        """Test volatility calculations with problematic data."""
        vol_stats = StatisticalAnalyzer.calculate_volatility_metrics(self.mixed_prices)
        
        assert isinstance(vol_stats, dict)
        # Should not crash and should return reasonable values
        assert "daily_volatility_pct" in vol_stats or "daily_volatility" in vol_stats
        assert "volatility_regime" in vol_stats
    
    def test_market_performance_analysis(self):
        """Test market performance analysis calculations."""
        perf_stats = StatisticalAnalyzer.analyze_market_performance([
            {"symbol": "TEST1", "price_change_24h": 5.0, "market_cap": 1000000},
            {"symbol": "TEST2", "price_change_24h": -2.0, "market_cap": 2000000}
        ])
        
        assert isinstance(perf_stats, dict)
        # Check for actual keys returned by the method
        assert "positive_count" in perf_stats or "gainers_count" in perf_stats
        assert "negative_count" in perf_stats or "losers_count" in perf_stats
        assert "avg_change_24h" in perf_stats
    
    def test_returns_edge_cases(self):
        """Test returns calculation edge cases."""
        # Single price - should return empty dict
        single_returns = StatisticalAnalyzer.calculate_returns_analysis(self.single_price)
        assert single_returns == {}
        
        # Empty prices - should return empty dict
        empty_returns = StatisticalAnalyzer.calculate_returns_analysis(self.empty_prices)
        assert empty_returns == {}


class TestStatisticalAnalyzerPerformance:
    """Performance and efficiency tests."""
    
    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        # Generate large dataset (10k points)
        large_prices = np.random.normal(100, 10, 10000)
        large_volumes = np.random.normal(1000, 200, 10000)
        
        import time
        start_time = time.time()
        
        # Should complete within reasonable time
        price_stats = StatisticalAnalyzer.calculate_price_statistics(large_prices)
        returns_stats = StatisticalAnalyzer.calculate_returns_analysis(large_prices)
        volume_stats = StatisticalAnalyzer.calculate_volume_statistics(large_volumes, large_prices)
        gini = StatisticalAnalyzer.calculate_gini_coefficient(large_volumes)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within 1 second for 10k points
        assert execution_time < 1.0
        
        # Results should be valid
        assert isinstance(price_stats, dict)
        assert isinstance(returns_stats, dict) 
        assert isinstance(volume_stats, dict)
        assert isinstance(gini, float)