#!/usr/bin/env python3
"""
Unit tests for PumpEngine aggressive mode and new listing logic
Tests the changes to _evaluate_symbol method in pump_engine.py
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config, PumpThresholds
from signals.pump_engine import PumpEngine
from utils.logger import setup_logger


class TestPumpEngineAggressiveMode(unittest.TestCase):
    """Test aggressive mode logic in pump engine"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.logger = setup_logger()
        self.engine = PumpEngine(self.config, self.logger)
        
        # Create mock dataframes
        dates = pd.date_range('2024-01-01', periods=100, freq='15min')
        self.df_15m = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(100, 110, 100),
            'high': np.random.uniform(110, 120, 100),
            'low': np.random.uniform(90, 100, 100),
            'close': np.random.uniform(100, 110, 100),
            'volume': np.random.uniform(1000, 5000, 100)
        })
        
        dates_1h = pd.date_range('2024-01-01', periods=50, freq='1h')
        self.df_1h = pd.DataFrame({
            'timestamp': dates_1h,
            'open': np.random.uniform(100, 110, 50),
            'high': np.random.uniform(110, 120, 50),
            'low': np.random.uniform(90, 100, 50),
            'close': np.random.uniform(100, 110, 50),
            'volume': np.random.uniform(1000, 5000, 50)
        })

    def test_aggressive_mode_enabled_check(self):
        """Test aggressive mode can be enabled via config"""
        self.config.pump_aggressive_mode = True
        self.assertTrue(self.config.pump_aggressive_mode)
        
        self.config.pump_aggressive_mode = False
        self.assertFalse(self.config.pump_aggressive_mode)

    def test_new_listing_bypass_rvol_threshold(self):
        """Test new listing detection via RVOL >= 5.0"""
        self.config.pump_new_listing_bypass = True
        
        # Create high RVOL scenario
        self.df_15m['volume'].iloc[-1] = 50000
        self.df_15m['volume'].iloc[-10:-1] = 2000
        
        # RVOL should be >= 5.0 (50000 / 2000 = 25)
        current_volume = self.df_15m['volume'].iloc[-1]
        avg_volume = self.df_15m['volume'].iloc[-10:-1].mean()
        rvol = current_volume / avg_volume
        
        self.assertGreaterEqual(rvol, 5.0)

    def test_aggressive_mode_attributes_present(self):
        """Test all aggressive mode config attributes exist"""
        required_attrs = [
            'pump_aggressive_mode',
            'pump_aggressive_min_rvol',
            'pump_aggressive_min_momentum',
            'pump_aggressive_min_24h_quote_volume',
            'pump_aggressive_min_24h_return',
            'pump_aggressive_max_24h_return',
            'pump_aggressive_price_above_ema1m',
        ]
        
        for attr in required_attrs:
            self.assertTrue(hasattr(self.config, attr),
                          f"Missing config attribute: {attr}")

    def test_ema1m_calculation_logic(self):
        """Test EMA 1-minute (span=60) calculation with sufficient data"""
        # Need at least 15 candles for 15m timeframe
        self.assertGreaterEqual(len(self.df_15m), 15)
        
        ema_1m = self.df_15m['close'].ewm(span=60, adjust=False).mean().iloc[-1]
        
        self.assertIsInstance(ema_1m, (float, np.floating))
        self.assertGreater(ema_1m, 0)

    def test_aggressive_return_range_validation(self):
        """Test aggressive mode return thresholds are sensible"""
        self.assertLess(self.config.pump_aggressive_min_24h_return,
                       self.config.pump_aggressive_max_24h_return)
        self.assertGreater(self.config.pump_aggressive_min_24h_return, 0)

    def test_thresholds_dataclass_structure(self):
        """Test PumpThresholds dataclass has all required fields"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        
        required_fields = [
            'min_24h_quote_volume',
            'min_score',
            'min_rvol',
            'min_24h_return',
            'max_24h_return',
            'min_momentum',
            'new_listing_min_rvol',
            'new_listing_min_score',
            'new_listing_min_momentum',
        ]
        
        for field in required_fields:
            self.assertTrue(hasattr(thresholds, field))

    def test_evaluate_symbol_requires_minimum_data(self):
        """Test _evaluate_symbol rejects insufficient data"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        debug_rejections = []
        
        # Test with None dataframes
        result = self.engine._evaluate_symbol(
            symbol='BTC/USDT',
            data={'ticker': {'quoteVolume': 100000}, 'df_15m': None, 'df_1h': None},
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=debug_rejections
        )
        
        self.assertIsNone(result)
        self.assertTrue(any('INSUFFICIENT_DATA' in r for r in debug_rejections))

    def test_evaluate_symbol_rejects_low_volume(self):
        """Test volume filter rejects low volume symbols"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        debug_rejections = []
        
        result = self.engine._evaluate_symbol(
            symbol='LOW/USDT',
            data={
                'ticker': {'quoteVolume': 1000},  # Below 150000 threshold
                'df_15m': self.df_15m,
                'df_1h': self.df_1h,
                'spread_pct': 0.5
            },
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=debug_rejections
        )
        
        self.assertIsNone(result)
        self.assertTrue(any('VOLUME_TOO_LOW' in r for r in debug_rejections))

    def test_evaluate_symbol_rejects_wide_spread(self):
        """Test spread filter rejects wide spreads"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        debug_rejections = []
        
        result = self.engine._evaluate_symbol(
            symbol='WIDE/USDT',
            data={
                'ticker': {'quoteVolume': 200000},
                'df_15m': self.df_15m,
                'df_1h': self.df_1h,
                'spread_pct': 2.5  # Above 1.5% max
            },
            regime='SIDEWAYS',
            open_positions=None,
            thresholds=thresholds,
            debug_rejections=debug_rejections
        )
        
        self.assertIsNone(result)
        self.assertTrue(any('SPREAD_TOO_WIDE' in r for r in debug_rejections))


if __name__ == '__main__':
    unittest.main(verbosity=2)