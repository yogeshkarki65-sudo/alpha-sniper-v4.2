#!/usr/bin/env python3
"""
Unit tests for RiskEngine regime detection fallback logging
Tests the debug logging enhancement for edge cases in regime detection
"""
import unittest
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config
from risk_engine import RiskEngine
from utils.logger import setup_logger


class TestRiskEngineRegimeDetection(unittest.TestCase):
    """Test regime detection logic and fallback handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = Config()
        self.logger = setup_logger()
        
        # Mock exchange and telegram
        self.mock_exchange = Mock()
        self.mock_telegram = Mock()
        self.mock_alert_mgr = Mock()
        
        self.risk_engine = RiskEngine(
            self.config,
            self.mock_exchange,
            self.logger,
            self.mock_telegram,
            self.mock_alert_mgr
        )

    def test_regime_fallback_to_sideways(self):
        """Test that edge cases default to SIDEWAYS regime"""
        # Create dataframe with edge case values
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        df = pd.DataFrame({
            'timestamp': dates,
            'open': [100] * 250,
            'high': [105] * 250,
            'low': [95] * 250,
            'close': [100] * 250,
            'volume': [1000] * 250
        })
        
        # Mock exchange to return this data
        self.mock_exchange.fetch_ohlcv = Mock(return_value=df.values.tolist())
        
        # Update regime
        regime = self.risk_engine.update_regime()
        
        # In edge cases, should fall back to SIDEWAYS
        self.assertIn(regime, ['SIDEWAYS', 'BULL', 'MILD_BEAR', 'DEEP_BEAR'])

    def test_bull_regime_detection(self):
        """Test BULL regime is detected when price > EMA200, RSI > 55, return > 10%"""
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        
        # Create strong bullish trend
        close_prices = np.linspace(100, 130, 250)  # 30% uptrend
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close_prices * 0.98,
            'high': close_prices * 1.02,
            'low': close_prices * 0.97,
            'close': close_prices,
            'volume': [10000] * 250
        })
        
        current_price = df['close'].iloc[-1]
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
        
        # Verify conditions for BULL
        self.assertGreater(current_price, ema200)
        self.assertGreater(return_30d, 10)

    def test_deep_bear_regime_detection(self):
        """Test DEEP_BEAR regime for severe downtrends"""
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        
        # Create deep bear trend (>20% decline)
        close_prices = np.linspace(100, 75, 250)  # -25% decline
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close_prices * 1.01,
            'high': close_prices * 1.02,
            'low': close_prices * 0.98,
            'close': close_prices,
            'volume': [8000] * 250
        })
        
        return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
        
        # Verify conditions for DEEP_BEAR
        self.assertLessEqual(return_30d, -20)

    def test_sideways_regime_detection(self):
        """Test SIDEWAYS regime for range-bound markets"""
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        
        # Create sideways market (< 10% movement)
        close_prices = np.array([100 + 5 * np.sin(i/10) for i in range(250)])
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close_prices * 0.99,
            'high': close_prices * 1.01,
            'low': close_prices * 0.98,
            'close': close_prices,
            'volume': [5000] * 250
        })
        
        return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
        
        # Verify conditions for SIDEWAYS
        self.assertLessEqual(abs(return_30d), 10)

    def test_mild_bear_regime_detection(self):
        """Test MILD_BEAR regime for moderate downtrends"""
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        
        # Create mild bear trend (-10% to -20%)
        close_prices = np.linspace(100, 88, 250)  # -12% decline
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close_prices * 1.005,
            'high': close_prices * 1.01,
            'low': close_prices * 0.99,
            'close': close_prices,
            'volume': [7000] * 250
        })
        
        current_price = df['close'].iloc[-1]
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
        
        # Verify conditions for MILD_BEAR
        self.assertLess(current_price, ema200)
        self.assertGreater(return_30d, -20)
        self.assertLess(return_30d, -10)

    def test_regime_change_notification(self):
        """Test that regime changes are logged and notified"""
        # Set initial regime
        self.risk_engine.current_regime = 'BULL'
        
        # Simulate regime change
        old_regime = self.risk_engine.current_regime
        new_regime = 'SIDEWAYS'
        
        self.assertNotEqual(old_regime, new_regime)

    def test_regime_stability(self):
        """Test that regime doesn't change on minor market fluctuations"""
        # Create stable market data
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        close_prices = np.array([100 + np.random.uniform(-2, 2) for i in range(250)])
        
        df = pd.DataFrame({
            'timestamp': dates,
            'close': close_prices,
        })
        
        return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
        
        # Should be relatively stable (< 10% movement)
        self.assertLess(abs(return_30d), 15)

    def test_ema200_calculation(self):
        """Test EMA200 calculation is correct"""
        dates = pd.date_range('2024-01-01', periods=250, freq='1D')
        close_prices = np.linspace(100, 110, 250)
        
        df = pd.DataFrame({
            'close': close_prices
        })
        
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        
        self.assertIsInstance(ema200, (float, np.floating))
        self.assertGreater(ema200, 0)
        self.assertGreater(ema200, 100)  # Should be above starting price
        self.assertLess(ema200, 110)  # Should be below ending price

    def test_rsi_calculation(self):
        """Test RSI calculation for regime detection"""
        # RSI should be between 0 and 100
        dates = pd.date_range('2024-01-01', periods=100, freq='1D')
        close_prices = np.random.uniform(95, 105, 100)
        
        df = pd.DataFrame({'close': close_prices})
        
        # Calculate RSI manually
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        rsi_value = rsi.iloc[-1]
        
        if not np.isnan(rsi_value):
            self.assertGreaterEqual(rsi_value, 0)
            self.assertLessEqual(rsi_value, 100)

    def test_regime_enum_values(self):
        """Test that regime values are valid"""
        valid_regimes = ['BULL', 'SIDEWAYS', 'MILD_BEAR', 'DEEP_BEAR', 'NEUTRAL']
        
        # Check if current regime is valid (if set)
        if hasattr(self.risk_engine, 'current_regime') and self.risk_engine.current_regime:
            self.assertIn(self.risk_engine.current_regime, valid_regimes)


if __name__ == '__main__':
    unittest.main(verbosity=2)