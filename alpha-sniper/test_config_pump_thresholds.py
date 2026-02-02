#!/usr/bin/env python3
"""
Unit tests for Config.get_pump_thresholds() method
Tests the regime-based pump threshold logic added in the current branch.
"""
import unittest
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config, PumpThresholds


class TestConfigPumpThresholds(unittest.TestCase):
    """Test suite for Config pump threshold retrieval"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()

    def test_strong_bull_thresholds(self):
        """Test STRONG_BULL regime returns correct thresholds"""
        thresholds = self.config.get_pump_thresholds('STRONG_BULL')
        
        self.assertIsInstance(thresholds, PumpThresholds)
        self.assertEqual(thresholds.min_24h_quote_volume, 100000)
        self.assertEqual(thresholds.min_score, 20)
        self.assertEqual(thresholds.min_rvol, 1.5)
        self.assertEqual(thresholds.min_24h_return, 5.0)
        self.assertEqual(thresholds.max_24h_return, 1500.0)

    def test_sideways_thresholds(self):
        """Test SIDEWAYS regime returns stricter thresholds"""
        thresholds = self.config.get_pump_thresholds('SIDEWAYS')
        
        self.assertEqual(thresholds.min_24h_quote_volume, 150000)
        self.assertEqual(thresholds.min_score, 35)
        self.assertEqual(thresholds.min_rvol, 1.8)
        self.assertEqual(thresholds.min_24h_return, 5.0)
        self.assertEqual(thresholds.max_24h_return, 400.0)

    def test_threshold_progression(self):
        """Test that thresholds become progressively stricter"""
        bull = self.config.get_pump_thresholds('STRONG_BULL')
        sideways = self.config.get_pump_thresholds('SIDEWAYS')
        mild_bear = self.config.get_pump_thresholds('MILD_BEAR')
        full_bear = self.config.get_pump_thresholds('FULL_BEAR')
        
        self.assertLess(bull.min_score, sideways.min_score)
        self.assertLess(sideways.min_score, mild_bear.min_score)
        self.assertLess(mild_bear.min_score, full_bear.min_score)


if __name__ == '__main__':
    unittest.main(verbosity=2)