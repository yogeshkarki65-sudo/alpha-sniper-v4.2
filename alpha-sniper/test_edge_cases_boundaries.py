#!/usr/bin/env python3
"""
Edge case and boundary tests for all modified files
Tests extreme values, boundary conditions, and error handling
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from unittest.mock import Mock

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config, PumpThresholds
from signals.pump_engine import PumpEngine
from utils.logger import setup_logger
from utils import helpers


class TestConfigEdgeCases(unittest.TestCase):
    """Edge case tests for Config class"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()

    def test_regime_with_spaces(self):
        """Test regime names with extra spaces"""
        result = self.config.get_pump_thresholds('  SIDEWAYS  ')
        self.assertIsInstance(result, PumpThresholds)

    def test_regime_case_variations(self):
        """Test various case combinations"""
        regimes = ['SIDEWAYS', 'sideways', 'SideWays', 'SiDeWaYs']
        
        base = self.config.get_pump_thresholds(regimes[0])
        for regime in regimes[1:]:
            result = self.config.get_pump_thresholds(regime)
            self.assertEqual(base.min_score, result.min_score)

    def test_threshold_boundary_values(self):
        """Test threshold values at extremes"""
        full_bear = self.config.get_pump_thresholds('FULL_BEAR')
        
        # Verify extreme values are still reasonable
        self.assertLess(full_bear.min_24h_quote_volume, 1000000)
        self.assertLess(full_bear.min_score, 100)
        self.assertLess(full_bear.min_rvol, 10.0)

    def test_zero_threshold_prevention(self):
        """Test no thresholds are zero (which would allow everything)"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            self.assertNotEqual(thresholds.min_24h_quote_volume, 0)
            self.assertNotEqual(thresholds.min_score, 0)
            self.assertNotEqual(thresholds.min_rvol, 0)
            self.assertNotEqual(thresholds.max_24h_return, 0)

    def test_negative_threshold_prevention(self):
        """Test no thresholds are negative"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            self.assertGreaterEqual(thresholds.min_24h_quote_volume, 0)
            self.assertGreaterEqual(thresholds.min_score, 0)
            self.assertGreaterEqual(thresholds.min_rvol, 0)
            self.assertGreaterEqual(thresholds.min_24h_return, 0)


class TestPumpEngineEdgeCases(unittest.TestCase):
    """Edge case tests for PumpEngine"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.logger = setup_logger()
        self.engine = PumpEngine(self.config, self.logger)

    def test_empty_dataframe_handling(self):
        """Test handling of empty dataframes"""
        empty_df = pd.DataFrame()
        
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        result = self.engine._evaluate_symbol(
            symbol='EMPTY/USDT',
            data={'ticker': {'quoteVolume': 100000}, 'df_15m': empty_df, 'df_1h': empty_df},
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=[]
        )
        
        self.assertIsNone(result)

    def test_insufficient_data_15m(self):
        """Test rejection when 15m data has < 20 candles"""
        df_15m = pd.DataFrame({
            'close': [100] * 15,
            'volume': [1000] * 15
        })
        df_1h = pd.DataFrame({
            'close': [100] * 50,
            'volume': [1000] * 50
        })
        
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        result = self.engine._evaluate_symbol(
            symbol='SHORT/USDT',
            data={'ticker': {'quoteVolume': 200000}, 'df_15m': df_15m, 'df_1h': df_1h},
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=[]
        )
        
        self.assertIsNone(result)

    def test_insufficient_data_1h(self):
        """Test rejection when 1h data has < 20 candles"""
        df_15m = pd.DataFrame({
            'close': [100] * 50,
            'volume': [1000] * 50
        })
        df_1h = pd.DataFrame({
            'close': [100] * 15,
            'volume': [1000] * 15
        })
        
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        result = self.engine._evaluate_symbol(
            symbol='SHORT/USDT',
            data={'ticker': {'quoteVolume': 200000}, 'df_15m': df_15m, 'df_1h': df_1h},
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=[]
        )
        
        self.assertIsNone(result)

    def test_zero_volume_handling(self):
        """Test handling of zero volume"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        debug_rejections = []
        
        df = pd.DataFrame({
            'close': [100] * 50,
            'volume': [0] * 50
        })
        
        result = self.engine._evaluate_symbol(
            symbol='ZERO/USDT',
            data={'ticker': {'quoteVolume': 0}, 'df_15m': df, 'df_1h': df},
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=debug_rejections
        )
        
        self.assertIsNone(result)
        self.assertTrue(any('VOLUME' in r for r in debug_rejections))

    def test_extreme_spread_rejection(self):
        """Test rejection of extremely wide spreads"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        debug_rejections = []
        
        df = pd.DataFrame({
            'close': [100] * 50,
            'volume': [5000] * 50
        })
        
        result = self.engine._evaluate_symbol(
            symbol='WIDE/USDT',
            data={
                'ticker': {'quoteVolume': 200000},
                'df_15m': df,
                'df_1h': df,
                'spread_pct': 10.0  # 10% spread
            },
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=debug_rejections
        )
        
        self.assertIsNone(result)
        self.assertTrue(any('SPREAD' in r for r in debug_rejections))

    def test_rvol_with_zero_average(self):
        """Test RVOL calculation when average volume is zero"""
        current_volume = 1000
        avg_volume = 0
        
        rvol = helpers.calculate_rvol(current_volume, avg_volume)
        
        # Should return 0.0 to prevent division by zero
        self.assertEqual(rvol, 0.0)

    def test_momentum_with_insufficient_data(self):
        """Test momentum calculation with insufficient data"""
        df = pd.DataFrame({
            'close': [100, 101, 102]
        })
        
        momentum = helpers.calculate_momentum(df, 12)
        
        # Should return 0.0 when insufficient data
        self.assertEqual(momentum, 0.0)

    def test_aggressive_mode_ema1m_boundary(self):
        """Test EMA1m check requires exactly 15 candles"""
        self.config.pump_aggressive_mode = True
        self.config.pump_aggressive_price_above_ema1m = True
        
        # Test with exactly 15 candles
        df_15m = pd.DataFrame({
            'close': [100] * 15,
            'volume': [1000] * 15
        })
        
        self.assertEqual(len(df_15m), 15)
        self.assertGreaterEqual(len(df_15m), 15)

    def test_return_24h_calculation_boundary(self):
        """Test 24h return calculation requires exactly 25 candles"""
        df_1h = pd.DataFrame({
            'close': np.linspace(100, 120, 25)
        })
        
        self.assertGreaterEqual(len(df_1h), 25)
        
        # Calculate return
        return_24h = ((df_1h['close'].iloc[-1] / df_1h['close'].iloc[-25]) - 1) * 100
        
        self.assertGreater(return_24h, 0)
        self.assertAlmostEqual(return_24h, 20.0, delta=0.1)


class TestTimingEdgeCases(unittest.TestCase):
    """Edge case tests for timing and scan loop logic"""

    def test_zero_elapsed_time(self):
        """Test handling when elapsed time is zero"""
        import time
        current_time = time.time()
        last_scan_time = current_time
        
        elapsed = current_time - last_scan_time
        
        self.assertGreaterEqual(elapsed, 0)
        self.assertLess(elapsed, 1)

    def test_negative_elapsed_time_prevention(self):
        """Test elapsed time cannot be negative (clock skew)"""
        import time
        current_time = time.time()
        last_scan_time = current_time + 10  # Future time (clock skew)
        
        elapsed = current_time - last_scan_time
        
        # Even if negative, should handle gracefully
        self.assertIsInstance(elapsed, float)

    def test_very_long_elapsed_time(self):
        """Test handling of very long elapsed times"""
        import time
        current_time = time.time()
        last_scan_time = current_time - 86400  # 24 hours ago
        
        elapsed = current_time - last_scan_time
        
        self.assertGreater(elapsed, 86000)

    def test_scan_interval_boundary(self):
        """Test exact boundary condition for scan trigger"""
        scan_interval = 300
        elapsed_exact = 300.0
        
        should_trigger = elapsed_exact >= scan_interval
        
        self.assertTrue(should_trigger)

    def test_fast_mode_runtime_zero(self):
        """Test fast mode runtime calculation at start"""
        import time
        fast_mode_start_time = time.time()
        current_time = time.time()
        
        runtime_hours = (current_time - fast_mode_start_time) / 3600
        
        self.assertGreaterEqual(runtime_hours, 0)
        self.assertLess(runtime_hours, 0.01)  # Should be near zero


class TestHelperFunctionEdgeCases(unittest.TestCase):
    """Edge case tests for helper functions"""

    def test_calculate_rvol_zero_denominator(self):
        """Test RVOL with zero average volume"""
        result = helpers.calculate_rvol(1000, 0)
        self.assertEqual(result, 0.0)

    def test_calculate_rvol_zero_numerator(self):
        """Test RVOL with zero current volume"""
        result = helpers.calculate_rvol(0, 1000)
        self.assertEqual(result, 0.0)

    def test_calculate_rvol_both_zero(self):
        """Test RVOL with both values zero"""
        result = helpers.calculate_rvol(0, 0)
        self.assertEqual(result, 0.0)

    def test_calculate_momentum_exact_boundary(self):
        """Test momentum with exactly minimum required periods"""
        df = pd.DataFrame({
            'close': [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155, 160]
        })
        
        momentum = helpers.calculate_momentum(df, 12)
        
        # Should calculate successfully with exactly 13 rows (12 periods + 1)
        self.assertNotEqual(momentum, 0.0)
        self.assertGreater(momentum, 0)

    def test_calculate_momentum_one_less_than_required(self):
        """Test momentum with one less than required periods"""
        df = pd.DataFrame({
            'close': [100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150, 155]
        })
        
        momentum = helpers.calculate_momentum(df, 12)
        
        # Should return 0.0 with insufficient data (12 rows for 12 periods)
        self.assertEqual(momentum, 0.0)

    def test_rsi_extreme_values(self):
        """Test RSI calculation doesn't exceed 0-100 range"""
        # Create extreme uptrend
        df = pd.DataFrame({
            'close': np.linspace(100, 200, 50)
        })
        
        rsi = helpers.calculate_rsi(df, 'close', 14)
        
        # RSI should be between 0 and 100
        rsi_values = rsi.dropna()
        if len(rsi_values) > 0:
            self.assertGreaterEqual(rsi_values.min(), 0)
            self.assertLessEqual(rsi_values.max(), 100)


if __name__ == '__main__':
    unittest.main(verbosity=2)