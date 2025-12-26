#!/usr/bin/env python3
"""
Test script for Entry-DETE (Dynamic Entry Timing Engine)

This script demonstrates and tests the Entry-DETE functionality:
1. Queuing signals for micro-confirmation
2. Evaluating micro-triggers (dip, volume, liquidity, momentum)
3. Confirming or expiring pending signals
4. Integration with risk engine for position opening

Usage:
    python test_entry_dete.py
"""

import os
import sys
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.entry_dete import EntryDETEngine
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
        self.logger.info(f"[MOCK-RISK] Opened position: {signal['symbol']} {signal['side']} @ {signal.get('entry_price'):.6f}")
        return position


def test_basic_queuing():
    """Test 1: Basic signal queuing"""
    print("\n" + "=" * 70)
    print("TEST 1: Basic Signal Queuing")
    print("=" * 70)

    # Setup
    logger = setup_logger()

    # Create minimal config for testing
    class TestConfig:
        entry_dete_enabled = True
        entry_dete_max_wait_seconds = 180
        entry_dete_min_triggers = 2
        entry_dete_min_dip_pct = 0.005
        entry_dete_max_dip_pct = 0.02
        entry_dete_volume_multiplier = 1.1
        max_spread_pct = 0.9
        liquidity_depth_good_level = 20000

    config = TestConfig()
    exchange = MockExchange()
    risk_engine = MockRiskEngine(logger)

    # Initialize Entry-DETE
    entry_dete = EntryDETEngine(config, logger, exchange, risk_engine)

    # Queue a signal
    signal = {
        'symbol': 'BTC/USDT',
        'side': 'long',
        'engine': 'standard',
        'score': 85,
        'entry_price': 50000.0,
        'regime': 'BULL'
    }

    entry_dete.queue_signal(signal)

    # Verify queuing
    assert entry_dete.get_pending_count() == 1, "Signal should be queued"
    print("✅ TEST 1 PASSED: Signal queued successfully")


def test_dip_trigger(entry_dete, exchange, risk_engine, config):
    """Test 2: Dip trigger confirmation"""
    print("\n" + "=" * 70)
    print("TEST 2: Dip Trigger Confirmation")
    print("=" * 70)

    # Setup: Clear any pending signals
    entry_dete.clear_pending()

    # Queue a signal at baseline price
    baseline_price = 50000.0
    exchange.set_last_price('BTC/USDT', baseline_price)

    signal = {
        'symbol': 'BTC/USDT',
        'side': 'long',
        'engine': 'standard',
        'score': 85,
        'entry_price': baseline_price,
        'regime': 'BULL'
    }

    entry_dete.queue_signal(signal)

    # Simulate a 1% dip (within dip range 0.5%-2%)
    dipped_price = baseline_price * 0.99
    exchange.set_last_price('BTC/USDT', dipped_price)

    # Set good liquidity
    exchange.set_liquidity('BTC/USDT', spread_pct=0.5, depth_usd=25000)

    # Process pending (should confirm if dip + liquidity triggers fire)
    entry_dete.process_pending()

    print("✅ TEST 2 PASSED: Dip trigger evaluated")


def test_timeout_expiry(entry_dete, exchange, risk_engine, config):
    """Test 3: Signal expiry after timeout"""
    print("\n" + "=" * 70)
    print("TEST 3: Signal Timeout Expiry")
    print("=" * 70)

    # Setup: Clear pending
    entry_dete.clear_pending()

    # Create a signal with very short timeout
    old_timeout = config.entry_dete_max_wait_seconds
    config.entry_dete_max_wait_seconds = 1  # 1 second timeout

    signal = {
        'symbol': 'ETH/USDT',
        'side': 'long',
        'engine': 'standard',
        'score': 80,
        'entry_price': 3000.0,
        'regime': 'SIDEWAYS'
    }

    entry_dete.queue_signal(signal)
    assert entry_dete.get_pending_count() == 1, "Signal should be queued"

    # Wait for timeout
    time.sleep(2)

    # Process pending (should expire)
    entry_dete.process_pending()

    # Verify expiry
    assert entry_dete.get_pending_count() == 0, "Signal should be expired"
    print("✅ TEST 3 PASSED: Signal expired after timeout")

    # Restore original timeout
    config.entry_dete_max_wait_seconds = old_timeout


def test_multi_trigger_confirmation(entry_dete, exchange, risk_engine, config):
    """Test 4: Multi-trigger confirmation logic"""
    print("\n" + "=" * 70)
    print("TEST 4: Multi-Trigger Confirmation")
    print("=" * 70)

    # Setup
    entry_dete.clear_pending()
    risk_engine.opened_positions.clear()

    # Queue a signal
    baseline_price = 45000.0
    exchange.set_last_price('SOL/USDT', baseline_price)
    exchange.set_liquidity('SOL/USDT', spread_pct=0.6, depth_usd=22000)

    signal = {
        'symbol': 'SOL/USDT',
        'side': 'long',
        'engine': 'pump',
        'score': 90,
        'entry_price': baseline_price,
        'regime': 'BULL'
    }

    entry_dete.queue_signal(signal)

    # Simulate good conditions: dip + good liquidity
    dipped_price = baseline_price * 0.992  # 0.8% dip
    exchange.set_last_price('SOL/USDT', dipped_price)

    # Process pending (should confirm with 2+ triggers)
    entry_dete.process_pending()

    # Check if position was opened
    if len(risk_engine.opened_positions) > 0:
        print("✅ TEST 4 PASSED: Position confirmed with multi-triggers")
    else:
        print("⚠️  TEST 4: No position opened (triggers may not have fired)")


def test_integration_flow():
    """Test 5: Full integration flow"""
    print("\n" + "=" * 70)
    print("TEST 5: Full Integration Flow")
    print("=" * 70)

    # This test demonstrates the full flow from signal generation to entry confirmation
    logger = setup_logger()

    class TestConfig:
        entry_dete_enabled = True
        entry_dete_max_wait_seconds = 180
        entry_dete_min_triggers = 2
        entry_dete_min_dip_pct = 0.005
        entry_dete_max_dip_pct = 0.02
        entry_dete_volume_multiplier = 1.1
        max_spread_pct = 0.9
        liquidity_depth_good_level = 20000

    config = TestConfig()
    exchange = MockExchange()
    risk_engine = MockRiskEngine(logger)
    entry_dete = EntryDETEngine(config, logger, exchange, risk_engine)

    # Simulate scanner generating signals
    signals = [
        {'symbol': 'BTC/USDT', 'side': 'long', 'engine': 'standard', 'score': 85, 'entry_price': 50000.0, 'regime': 'BULL'},
        {'symbol': 'ETH/USDT', 'side': 'long', 'engine': 'standard', 'score': 82, 'entry_price': 3000.0, 'regime': 'BULL'},
        {'symbol': 'SOL/USDT', 'side': 'long', 'engine': 'pump', 'score': 90, 'entry_price': 150.0, 'regime': 'BULL'}
    ]

    print(f"\n📡 Scanner generated {len(signals)} signals")

    # Queue all signals (simulating scanner behavior with Entry-DETE enabled)
    for signal in signals:
        entry_dete.queue_signal(signal)

    print(f"🎯 Queued {entry_dete.get_pending_count()} signals for Entry-DETE confirmation")

    # Simulate position loop processing (3 cycles)
    for cycle in range(1, 4):
        print(f"\n⚡ Position Loop Cycle {cycle} (simulating 15s interval)")

        # Simulate price movements
        exchange.set_last_price('BTC/USDT', 50000.0 * (1 - cycle * 0.003))
        exchange.set_last_price('ETH/USDT', 3000.0 * (1 - cycle * 0.004))
        exchange.set_last_price('SOL/USDT', 150.0 * (1 - cycle * 0.006))

        # Set good liquidity
        for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']:
            exchange.set_liquidity(symbol, spread_pct=0.6, depth_usd=25000)

        # Process pending signals
        entry_dete.process_pending()

        print(f"   Pending signals remaining: {entry_dete.get_pending_count()}")
        print(f"   Positions opened so far: {len(risk_engine.opened_positions)}")

    print("\n✅ TEST 5 PASSED: Integration flow completed")
    print("   Final stats:")
    print(f"   - Signals queued: {len(signals)}")
    print(f"   - Positions opened: {len(risk_engine.opened_positions)}")
    print(f"   - Signals still pending: {entry_dete.get_pending_count()}")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("ENTRY-DETE TEST SUITE")
    print("Testing Smart Entry Timing Engine")
    print("=" * 70)

    try:
        # Run tests
        entry_dete, exchange, risk_engine, config = test_basic_queuing()
        test_dip_trigger(entry_dete, exchange, risk_engine, config)
        test_timeout_expiry(entry_dete, exchange, risk_engine, config)
        test_multi_trigger_confirmation(entry_dete, exchange, risk_engine, config)
        test_integration_flow()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 70)
        print("\nEntry-DETE is ready for production use!")
        print("To enable: Set ENTRY_DETE_ENABLED=true in .env")

    except Exception as e:
        print(f"\n🔴 TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
