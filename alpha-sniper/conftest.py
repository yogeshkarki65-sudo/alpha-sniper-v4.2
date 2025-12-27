"""
Pytest configuration and fixtures for alpha-sniper tests
"""
import time

import pytest
from utils.logger import setup_logger


class MockExchange:
    """Mock exchange for testing Entry-DETE without real API calls"""

    def __init__(self):
        self.last_prices = {}
        self.klines_data = {}
        self.liquidity_data = {}

    def get_last_price(self, symbol):
        """Return mock price for testing"""
        return self.last_prices.get(symbol, 100.0)

    def set_last_price(self, symbol, price):
        """Set mock price for testing"""
        self.last_prices[symbol] = price

    def get_klines(self, symbol, interval, limit=100):
        """Return mock klines for testing"""
        # Return mock klines: [timestamp, open, high, low, close, volume]
        base_price = self.last_prices.get(symbol, 100.0)
        klines = []
        for i in range(limit):
            klines.append([
                int(time.time() * 1000) - (limit - i) * 60000,  # timestamp
                base_price * (1 + (i % 3) * 0.001),  # open
                base_price * 1.002,  # high
                base_price * 0.998,  # low
                base_price * (1 + (i % 2) * 0.001),  # close
                1000 * (1 + i * 0.1)  # volume
            ])
        return klines

    def get_liquidity_metrics(self, symbol):
        """Return mock liquidity metrics for testing"""
        return self.liquidity_data.get(symbol, {
            'spread_pct': 0.5,
            'depth_usd': 25000
        })

    def set_liquidity(self, symbol, spread_pct, depth_usd):
        """Set mock liquidity for testing"""
        self.liquidity_data[symbol] = {
            'spread_pct': spread_pct,
            'depth_usd': depth_usd
        }


class MockRiskEngine:
    """Mock risk engine for testing Entry-DETE"""

    def __init__(self, logger):
        self.logger = logger
        self.opened_positions = []

    def open_position(self, signal):
        """Mock opening a position"""
        position = {
            'symbol': signal['symbol'],
            'side': signal['side'],
            'engine': signal.get('engine'),
            'entry_price': signal.get('entry_price'),
            'timestamp': time.time()
        }
        self.opened_positions.append(position)
        self.logger.info(
            f"[MOCK-RISK] Opened position: {signal['symbol']} {signal['side']} "
            f"@ {signal.get('entry_price'):.6f}"
        )
        return position


class TestConfig:
    """Test configuration for Entry-DETE tests"""
    entry_dete_enabled = True
    entry_dete_max_wait_seconds = 180
    entry_dete_min_triggers = 2
    entry_dete_min_dip_pct = 0.005
    entry_dete_max_dip_pct = 0.02
    entry_dete_volume_multiplier = 1.1
    max_spread_pct = 0.9
    liquidity_depth_good_level = 20000


@pytest.fixture
def config():
    """Pytest fixture for test configuration"""
    return TestConfig()


@pytest.fixture
def exchange():
    """Pytest fixture for mock exchange"""
    return MockExchange()


@pytest.fixture
def risk_engine():
    """Pytest fixture for mock risk engine"""
    logger = setup_logger()
    return MockRiskEngine(logger)


@pytest.fixture
def entry_dete(config, exchange, risk_engine):
    """Pytest fixture for Entry-DETE engine"""
    from utils.entry_dete import EntryDETEngine
    logger = setup_logger()
    return EntryDETEngine(config, logger, exchange, risk_engine)
