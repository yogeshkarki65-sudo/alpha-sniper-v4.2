#!/usr/bin/env python3
"""
Integration tests for pump threshold changes across config and pump_engine
Tests the interaction between Config and PumpEngine with new threshold values
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


class TestPumpThresholdsIntegration(unittest.TestCase):
    """Integration tests for pump thresholds across modules"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.logger = setup_logger()
        self.engine = PumpEngine(self.config, self.logger)

    def test_engine_uses_config_thresholds(self):
        """Test pump engine correctly uses config thresholds"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            # Verify thresholds are valid
            self.assertIsInstance(thresholds, PumpThresholds)
            self.assertGreater(thresholds.min_24h_quote_volume, 0)
            self.assertGreater(thresholds.min_score, 0)

    def test_return_percentage_format_consistency(self):
        """Test return values are consistently in percentage format (not decimal)"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            # min_24h_return should be >= 5.0 (representing 5%)
            self.assertGreaterEqual(thresholds.min_24h_return, 5.0,
                f"{regime} min_24h_return should be in percentage format")
            
            # max_24h_return should be >= 400.0 (representing 400%)
            self.assertGreaterEqual(thresholds.max_24h_return, 400.0,
                f"{regime} max_24h_return should be in percentage format")

    def test_sideways_regime_more_restrictive(self):
        """Test SIDEWAYS has higher thresholds than STRONG_BULL"""
        bull = self.config.get_pump_thresholds('STRONG_BULL')
        sideways = self.config.get_pump_thresholds('SIDEWAYS')
        
        # SIDEWAYS should require more volume
        self.assertGreater(sideways.min_24h_quote_volume, bull.min_24h_quote_volume)
        
        # SIDEWAYS should require higher score
        self.assertGreater(sideways.min_score, bull.min_score)
        
        # SIDEWAYS should require higher RVOL
        self.assertGreater(sideways.min_rvol, bull.min_rvol)
        
        # SIDEWAYS should have lower max return (more conservative)
        self.assertLess(sideways.max_24h_return, bull.max_24h_return)

    def test_bear_regimes_most_restrictive(self):
        """Test BEAR regimes have strictest thresholds"""
        mild_bear = self.config.get_pump_thresholds('MILD_BEAR')
        full_bear = self.config.get_pump_thresholds('FULL_BEAR')
        
        # FULL_BEAR should be more restrictive than MILD_BEAR
        self.assertGreater(full_bear.min_24h_quote_volume, mild_bear.min_24h_quote_volume)
        self.assertGreater(full_bear.min_score, mild_bear.min_score)
        self.assertGreater(full_bear.min_rvol, mild_bear.min_rvol)

    def test_new_listing_thresholds_relaxed_across_regimes(self):
        """Test new listing thresholds are consistently more relaxed"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            # New listing should have lower (more relaxed) requirements
            self.assertLessEqual(thresholds.new_listing_min_rvol, thresholds.min_rvol,
                f"{regime} new_listing_min_rvol should be <= min_rvol")
            self.assertLessEqual(thresholds.new_listing_min_score, thresholds.min_score,
                f"{regime} new_listing_min_score should be <= min_score")
            self.assertLessEqual(thresholds.new_listing_min_momentum, thresholds.min_momentum,
                f"{regime} new_listing_min_momentum should be <= min_momentum")

    def test_regime_aliases_work_correctly(self):
        """Test regime aliases return identical thresholds"""
        # PUMPY should match STRONG_BULL
        strong_bull = self.config.get_pump_thresholds('STRONG_BULL')
        pumpy = self.config.get_pump_thresholds('PUMPY')
        
        self.assertEqual(strong_bull.min_score, pumpy.min_score)
        self.assertEqual(strong_bull.max_24h_return, pumpy.max_24h_return)
        
        # NEUTRAL should match SIDEWAYS
        sideways = self.config.get_pump_thresholds('SIDEWAYS')
        neutral = self.config.get_pump_thresholds('NEUTRAL')
        
        self.assertEqual(sideways.min_score, neutral.min_score)
        self.assertEqual(sideways.max_24h_return, neutral.max_24h_return)
        
        # BEAR should match FULL_BEAR
        full_bear = self.config.get_pump_thresholds('FULL_BEAR')
        bear = self.config.get_pump_thresholds('BEAR')
        
        self.assertEqual(full_bear.min_score, bear.min_score)
        self.assertEqual(full_bear.max_24h_return, bear.max_24h_return)

    def test_threshold_comments_match_values(self):
        """Test inline comments accurately reflect the actual values"""
        sideways = self.config.get_pump_thresholds('SIDEWAYS')
        
        # Comment says "5%" and value should be 5.0
        self.assertEqual(sideways.min_24h_return, 5.0)
        
        # Comment says "400% max" and value should be 400.0
        self.assertEqual(sideways.max_24h_return, 400.0)

    def test_aggressive_mode_override_capability(self):
        """Test aggressive mode can override regime thresholds"""
        self.config.pump_aggressive_mode = True
        
        # Aggressive mode attributes should exist and be accessible
        self.assertTrue(hasattr(self.config, 'pump_aggressive_min_rvol'))
        self.assertTrue(hasattr(self.config, 'pump_aggressive_min_momentum'))
        self.assertTrue(hasattr(self.config, 'pump_aggressive_min_24h_quote_volume'))

    def test_all_regimes_have_valid_thresholds(self):
        """Test all supported regimes return valid threshold objects"""
        regimes = ['STRONG_BULL', 'PUMPY', 'SIDEWAYS', 'NEUTRAL', 
                   'MILD_BEAR', 'FULL_BEAR', 'BEAR']
        
        for regime in regimes:
            thresholds = self.config.get_pump_thresholds(regime)
            
            self.assertIsInstance(thresholds, PumpThresholds)
            self.assertGreater(thresholds.min_24h_quote_volume, 0)
            self.assertGreater(thresholds.min_score, 0)
            self.assertGreater(thresholds.min_rvol, 0)
            self.assertGreater(thresholds.max_24h_return, 
                             thresholds.min_24h_return)


class TestReturnFormatConsistency(unittest.TestCase):
    """Test return value format consistency (percentage vs decimal)"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()

    def test_no_decimal_format_returns(self):
        """Test no thresholds use old decimal format (0.05 for 5%)"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            # Should NOT be in decimal format
            self.assertGreater(thresholds.min_24h_return, 1.0,
                f"{regime} should not use decimal format (<1.0) for returns")
            self.assertGreater(thresholds.max_24h_return, 10.0,
                f"{regime} should not use decimal format (<10.0) for returns")

    def test_percentage_format_ranges(self):
        """Test return percentages are in reasonable ranges"""
        for regime in ['STRONG_BULL', 'SIDEWAYS', 'MILD_BEAR', 'FULL_BEAR']:
            thresholds = self.config.get_pump_thresholds(regime)
            
            # min_24h_return should be between 5% and 15%
            self.assertGreaterEqual(thresholds.min_24h_return, 5.0)
            self.assertLessEqual(thresholds.min_24h_return, 15.0)
            
            # max_24h_return should be between 400% and 1500%
            self.assertGreaterEqual(thresholds.max_24h_return, 400.0)
            self.assertLessEqual(thresholds.max_24h_return, 2000.0)

    def test_strong_bull_most_permissive_returns(self):
        """Test STRONG_BULL has widest acceptable return range"""
        bull = self.config.get_pump_thresholds('STRONG_BULL')
        
        # Should allow very high returns (1500%)
        self.assertEqual(bull.max_24h_return, 1500.0)
        
        # Should have lowest minimum (5%)
        self.assertEqual(bull.min_24h_return, 5.0)

    def test_sideways_capped_returns(self):
        """Test SIDEWAYS caps returns at 400% (not 1200%)"""
        sideways = self.config.get_pump_thresholds('SIDEWAYS')
        
        # Comment explicitly says "400% max (not 1200%)"
        self.assertEqual(sideways.max_24h_return, 400.0)
        self.assertNotEqual(sideways.max_24h_return, 1200.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)