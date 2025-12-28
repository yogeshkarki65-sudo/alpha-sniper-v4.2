#!/usr/bin/env python3
"""
Alpha Sniper v4.2.3 - Production-Safe Market Data Smoke Test

Tests REAL exchange data WITHOUT placing orders:
- Market data fetching (ticker, orderbook, OHLCV)
- Depth and spread calculations
- Exchange limits validation (minQty, minNotional, precision)
- Viability gate checks (spread, depth, size)
- Order validation logic

Usage:
    python scripts/smoke_market_data.py

Environment:
    Reads from .env file (same as main bot)
    Uses SMOKE_TEST_SYMBOL (default: BTC/USDT)
    Uses SMOKE_TEST_USD (default: $10)

Exit codes:
    0 = All tests PASSED
    1 = One or more tests FAILED
    2 = Configuration error
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import bot modules
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

import config as config_module
import exchange as exchange_module
import logging

# Import classes
Config = config_module.Config
create_exchange = exchange_module.create_exchange

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_market_data(config, exchange):
    """Test market data fetching"""
    symbol = config.smoke_test_symbol
    logger.info(f"=" * 80)
    logger.info(f"TEST 1: Market Data Fetching ({symbol})")
    logger.info(f"=" * 80)

    try:
        # Test ticker
        logger.info("[1.1] Fetching ticker...")
        ticker = exchange.get_ticker(symbol)
        if not ticker:
            logger.error(f"✗ FAIL: No ticker data for {symbol}")
            return False

        last_price = ticker.get('last', ticker.get('close', 0))
        bid = ticker.get('bid', 0)
        ask = ticker.get('ask', 0)

        logger.info(f"✓ PASS: Ticker | last={last_price:.6f} | bid={bid:.6f} | ask={ask:.6f}")

        # Test orderbook
        logger.info("[1.2] Fetching orderbook...")
        orderbook = exchange.get_orderbook(symbol)
        if not orderbook:
            logger.error(f"✗ FAIL: No orderbook data for {symbol}")
            return False

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            logger.error(f"✗ FAIL: Empty orderbook for {symbol}")
            return False

        logger.info(f"✓ PASS: Orderbook | bids={len(bids)} levels | asks={len(asks)} levels")

        # Test OHLCV
        logger.info("[1.3] Fetching OHLCV (1h, 200 candles)...")
        klines = exchange.get_klines(symbol, '1h', limit=200)
        if not klines or len(klines) == 0:
            logger.error(f"✗ FAIL: No OHLCV data for {symbol}")
            return False

        logger.info(f"✓ PASS: OHLCV | {len(klines)} candles retrieved")

        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Market data test exception: {e}")
        return False


def test_liquidity_metrics(config, exchange):
    """Test liquidity calculations"""
    symbol = config.smoke_test_symbol
    logger.info("")
    logger.info(f"=" * 80)
    logger.info(f"TEST 2: Liquidity Metrics ({symbol})")
    logger.info(f"=" * 80)

    try:
        logger.info("[2.1] Calculating liquidity metrics...")
        liquidity = exchange.get_liquidity_metrics(symbol)

        if not liquidity:
            logger.error(f"✗ FAIL: No liquidity metrics for {symbol}")
            return False

        spread_pct = liquidity.get('spread_pct', 0)
        depth_usd = liquidity.get('depth_usd', 0)

        logger.info(f"  Spread: {spread_pct:.4f}%")
        logger.info(f"  Depth (top {config.orderbook_depth_levels} levels): ${depth_usd:,.0f}")

        # Check against config limits
        if spread_pct > config.max_spread_pct_order:
            logger.warning(f"⚠ WARNING: Spread {spread_pct:.4f}% > max {config.max_spread_pct_order:.2f}%")
        else:
            logger.info(f"✓ PASS: Spread within limits ({spread_pct:.4f}% ≤ {config.max_spread_pct_order:.2f}%)")

        test_size = config.smoke_test_usd
        required_depth = test_size * config.min_depth_multiple

        if depth_usd < required_depth:
            logger.warning(f"⚠ WARNING: Depth ${depth_usd:,.0f} < required ${required_depth:,.0f} (${test_size} * {config.min_depth_multiple}x)")
        else:
            logger.info(f"✓ PASS: Depth sufficient (${depth_usd:,.0f} ≥ ${required_depth:,.0f})")

        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Liquidity metrics test exception: {e}")
        return False


def test_exchange_validation(config, exchange):
    """Test exchange limits validation"""
    symbol = config.smoke_test_symbol
    logger.info("")
    logger.info(f"=" * 80)
    logger.info(f"TEST 3: Exchange Validation ({symbol})")
    logger.info(f"=" * 80)

    try:
        # Get current price
        ticker = exchange.get_ticker(symbol)
        if not ticker:
            logger.error(f"✗ FAIL: Cannot get ticker for validation test")
            return False

        price = ticker.get('last', ticker.get('close', 0))
        test_size = config.smoke_test_usd

        logger.info(f"[3.1] Testing validation with size=${test_size:.2f}, price={price:.6f}...")

        # Run validation
        valid, reason_code, details = exchange.validate_order(symbol, test_size, price)

        logger.info(f"  Result: {'✓ PASS' if valid else '✗ FAIL'}")
        logger.info(f"  Reason: {reason_code}")
        logger.info(f"  Details:")
        for key, value in details.items():
            if isinstance(value, float):
                logger.info(f"    {key}: {value:.6f}")
            else:
                logger.info(f"    {key}: {value}")

        if not valid:
            logger.warning(f"⚠ WARNING: Validation failed with reason: {reason_code}")
            logger.info(f"  This means a ${test_size:.2f} order would be REJECTED")
            logger.info(f"  Try increasing SMOKE_TEST_USD in your .env file")
            return False

        logger.info(f"✓ PASS: Order validation passed for ${test_size:.2f}")
        return True

    except Exception as e:
        logger.error(f"✗ FAIL: Exchange validation test exception: {e}")
        return False


def test_viability_gates(config, exchange):
    """Test viability gate logic"""
    symbol = config.smoke_test_symbol
    logger.info("")
    logger.info(f"=" * 80)
    logger.info(f"TEST 4: Viability Gates ({symbol})")
    logger.info(f"=" * 80)

    try:
        # Get liquidity metrics
        liquidity = exchange.get_liquidity_metrics(symbol)
        spread_pct = liquidity.get('spread_pct', 0)
        depth_usd = liquidity.get('depth_usd', 0)

        test_size = config.smoke_test_usd
        all_passed = True

        # Gate 1: Minimum viable size
        logger.info(f"[4.1] Gate 1: Minimum Viable Size")
        if test_size < config.min_viable_trade_usd:
            logger.error(f"✗ FAIL: Size ${test_size:.2f} < min ${config.min_viable_trade_usd:.2f}")
            logger.error(f"  Reason code: SKIP_TOO_SMALL_AFTER_VALIDATION")
            all_passed = False
        else:
            logger.info(f"✓ PASS: Size ${test_size:.2f} ≥ min ${config.min_viable_trade_usd:.2f}")

        # Gate 2: Spread check
        logger.info(f"[4.2] Gate 2: Spread Check")
        if spread_pct > config.max_spread_pct_order:
            logger.error(f"✗ FAIL: Spread {spread_pct:.4f}% > max {config.max_spread_pct_order:.2f}%")
            logger.error(f"  Reason code: SKIP_SPREAD_TOO_HIGH")
            all_passed = False
        else:
            logger.info(f"✓ PASS: Spread {spread_pct:.4f}% ≤ max {config.max_spread_pct_order:.2f}%")

        # Gate 3: Depth check
        logger.info(f"[4.3] Gate 3: Depth Check")
        required_depth = test_size * config.min_depth_multiple
        if depth_usd < required_depth:
            logger.error(f"✗ FAIL: Depth ${depth_usd:,.0f} < required ${required_depth:,.0f}")
            logger.error(f"  Reason code: SKIP_DEPTH_TOO_LOW")
            all_passed = False
        else:
            logger.info(f"✓ PASS: Depth ${depth_usd:,.0f} ≥ required ${required_depth:,.0f}")

        return all_passed

    except Exception as e:
        logger.error(f"✗ FAIL: Viability gates test exception: {e}")
        return False


def main():
    """Main smoke test runner"""
    logger.info("=" * 80)
    logger.info("ALPHA SNIPER v4.2.3 - MARKET DATA SMOKE TEST")
    logger.info("=" * 80)
    logger.info("Testing REAL exchange data WITHOUT placing orders")
    logger.info("")

    # Load config
    try:
        config = Config()
        logger.info(f"✓ Config loaded")
        logger.info(f"  SIM_MODE: {config.sim_mode}")
        logger.info(f"  SMOKE_TEST_SYMBOL: {config.smoke_test_symbol}")
        logger.info(f"  SMOKE_TEST_USD: ${config.smoke_test_usd:.2f}")
        logger.info("")
    except Exception as e:
        logger.error(f"✗ FAIL: Cannot load config: {e}")
        return 2

    # Create exchange (force LIVE_DATA mode for real market testing)
    try:
        # Override to use real data
        original_sim_mode = config.sim_mode
        original_data_source = config.sim_data_source

        config.sim_mode = True
        config.sim_data_source = "LIVE_DATA"

        exchange = create_exchange(config, logger)
        logger.info(f"✓ Exchange created for real market data testing")
        logger.info("")

        # Restore original settings
        config.sim_mode = original_sim_mode
        config.sim_data_source = original_data_source

    except Exception as e:
        logger.error(f"✗ FAIL: Cannot create exchange: {e}")
        return 2

    # Run tests
    results = []

    results.append(test_market_data(config, exchange))
    results.append(test_liquidity_metrics(config, exchange))
    results.append(test_exchange_validation(config, exchange))
    results.append(test_viability_gates(config, exchange))

    # Final summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("SMOKE TEST SUMMARY")
    logger.info("=" * 80)

    passed = sum(results)
    total = len(results)

    logger.info(f"Tests passed: {passed}/{total}")

    if all(results):
        logger.info("=" * 80)
        logger.info("✓ ALL TESTS PASSED - Market data system is HEALTHY")
        logger.info("=" * 80)
        return 0
    else:
        logger.info("=" * 80)
        logger.error("✗ SOME TESTS FAILED - Review errors above")
        logger.info("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
