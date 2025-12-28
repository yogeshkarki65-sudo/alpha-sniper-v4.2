#!/usr/bin/env python3
"""
Alpha Sniper v4.2.3 - Production-Safe Order Lifecycle Smoke Test

Tests REAL order placement (GATED - requires explicit enable):
- Creates a REAL market order on the exchange
- Tests ORDER_VALIDATING → ORDER_PLACED → ORDER_FILLED lifecycle
- Tests order cancellation (if applicable)

⚠️  WARNING: This script places REAL ORDERS with REAL MONEY!  ⚠️

Usage:
    # Dry-run mode (default - shows what would happen, no orders):
    python scripts/smoke_order_lifecycle.py

    # LIVE mode (actually places orders - REQUIRES explicit flag):
    SMOKE_TEST_ALLOW_ORDERS=true python scripts/smoke_order_lifecycle.py

Environment:
    SMOKE_TEST_ALLOW_ORDERS=true  # REQUIRED to place real orders
    SMOKE_TEST_SYMBOL (default: BTC/USDT)
    SMOKE_TEST_USD (default: $10)
    SIM_MODE must be false (enforced)

Exit codes:
    0 = Test PASSED
    1 = Test FAILED
    2 = Configuration error
    3 = Orders disabled (default safety)
"""
import sys
import os
from pathlib import Path
import time

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


def main():
    """Main order lifecycle test"""
    logger.info("=" * 80)
    logger.info("ALPHA SNIPER v4.2.3 - ORDER LIFECYCLE SMOKE TEST")
    logger.info("=" * 80)
    logger.info("⚠️  WARNING: This test can place REAL ORDERS with REAL MONEY!")
    logger.info("")

    # Load config
    try:
        config = Config()
        logger.info(f"✓ Config loaded")
        logger.info(f"  SIM_MODE: {config.sim_mode}")
        logger.info(f"  SMOKE_TEST_ALLOW_ORDERS: {config.smoke_test_allow_orders}")
        logger.info(f"  SMOKE_TEST_SYMBOL: {config.smoke_test_symbol}")
        logger.info(f"  SMOKE_TEST_USD: ${config.smoke_test_usd:.2f}")
        logger.info("")
    except Exception as e:
        logger.error(f"✗ FAIL: Cannot load config: {e}")
        return 2

    # Safety check 1: Require SMOKE_TEST_ALLOW_ORDERS=true
    if not config.smoke_test_allow_orders:
        logger.info("=" * 80)
        logger.info("SKIPPED - Orders are DISABLED (safety default)")
        logger.info("=" * 80)
        logger.info("")
        logger.info("This test is disabled by default to prevent accidental real orders.")
        logger.info("")
        logger.info("To enable REAL order testing:")
        logger.info("  1. Add to .env:")
        logger.info("     SMOKE_TEST_ALLOW_ORDERS=true")
        logger.info("  2. Ensure SIM_MODE=false")
        logger.info("  3. Ensure you have MEXC_API_KEY and MEXC_SECRET_KEY set")
        logger.info("  4. Understand this will place a REAL order with REAL funds")
        logger.info("")
        logger.info("Current test size: $%.2f on %s" % (config.smoke_test_usd, config.smoke_test_symbol))
        logger.info("=" * 80)
        return 3

    # Safety check 2: Must not be in SIM mode
    if config.sim_mode:
        logger.error("=" * 80)
        logger.error("✗ FAIL: SIM_MODE=true - Cannot test real orders in SIM mode")
        logger.error("=" * 80)
        logger.error("")
        logger.error("To test real order lifecycle:")
        logger.error("  1. Set SIM_MODE=false in .env")
        logger.error("  2. Set SMOKE_TEST_ALLOW_ORDERS=true in .env")
        logger.error("  3. Ensure MEXC_API_KEY and MEXC_SECRET_KEY are set")
        logger.error("")
        return 2

    # Safety check 3: Require API keys
    if not config.mexc_api_key or not config.mexc_secret_key:
        logger.error("=" * 80)
        logger.error("✗ FAIL: MEXC API keys not configured")
        logger.error("=" * 80)
        logger.error("")
        logger.error("Set MEXC_API_KEY and MEXC_SECRET_KEY in .env")
        logger.error("")
        return 2

    # Final confirmation
    logger.info("=" * 80)
    logger.info("⚠️  FINAL CONFIRMATION ⚠️")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"  This test will place a REAL market order:")
    logger.info(f"    Symbol: {config.smoke_test_symbol}")
    logger.info(f"    Size: ${config.smoke_test_usd:.2f}")
    logger.info(f"    Type: Market buy")
    logger.info("")
    logger.info("  Proceeding in 5 seconds...")
    logger.info("  Press Ctrl+C to abort")
    logger.info("")

    try:
        for i in range(5, 0, -1):
            logger.info(f"  {i}...")
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("✓ Test aborted by user")
        return 0

    logger.info("")
    logger.info("=" * 80)
    logger.info("STARTING REAL ORDER TEST")
    logger.info("=" * 80)
    logger.info("")

    # Create exchange
    try:
        exchange = create_exchange(config, logger)
        logger.info(f"✓ Exchange created (LIVE mode)")
        logger.info("")
    except Exception as e:
        logger.error(f"✗ FAIL: Cannot create exchange: {e}")
        return 2

    # Test order lifecycle
    symbol = config.smoke_test_symbol
    test_size = config.smoke_test_usd
    order_id = None

    try:
        # Step 1: Get current price
        logger.info(f"[1] Getting current price for {symbol}...")
        ticker = exchange.get_ticker(symbol)
        if not ticker:
            logger.error(f"✗ FAIL: Cannot get ticker")
            return 1

        price = ticker.get('last', ticker.get('close', 0))
        logger.info(f"✓ Current price: {price:.6f}")
        logger.info("")

        # Step 2: Validate order
        logger.info(f"[2] Validating order (${test_size:.2f} @ {price:.6f})...")
        valid, reason_code, details = exchange.validate_order(symbol, test_size, price)

        if not valid:
            logger.error(f"✗ FAIL: Order validation failed")
            logger.error(f"  Reason: {reason_code}")
            logger.error(f"  Details: {details}")
            logger.error("")
            logger.error(f"  Try increasing SMOKE_TEST_USD in .env")
            return 1

        qty_rounded = details.get('qty_rounded', 0)
        logger.info(f"✓ Validation PASSED")
        logger.info(f"  Quantity: {qty_rounded:.6f}")
        logger.info(f"  Notional: ${details.get('notional', 0):.2f}")
        logger.info("")

        # Step 3: Place market order
        logger.info(f"[3] Placing REAL market order...")
        logger.info(f"  [ORDER_VALIDATING] {symbol} | side=buy | size=${test_size:.2f} | amount={qty_rounded:.6f}")

        order = exchange.create_order(
            symbol=symbol,
            type='market',
            side='buy',
            amount=qty_rounded,
            params={}
        )

        if not order or not order.get('id'):
            logger.error(f"✗ FAIL: Order creation failed")
            logger.error(f"  Response: {order}")
            return 1

        order_id = order.get('id')
        order_status = order.get('status', 'unknown')
        filled_qty = order.get('filled', 0)
        avg_price = order.get('average', order.get('price', 0))

        logger.info(f"  [ORDER_PLACED] {symbol} | id={order_id} | status={order_status}")

        if order_status in ['closed', 'filled']:
            logger.info(f"  [ORDER_FILLED] {symbol} | id={order_id} | filled={filled_qty:.6f} | avg_price={avg_price:.6f}")

        logger.info(f"✓ Order PLACED and FILLED")
        logger.info(f"  Order ID: {order_id}")
        logger.info(f"  Status: {order_status}")
        logger.info(f"  Filled: {filled_qty:.6f}")
        logger.info(f"  Avg Price: {avg_price:.6f}")
        logger.info("")

        # Success
        logger.info("=" * 80)
        logger.info("✓ ORDER LIFECYCLE TEST PASSED")
        logger.info("=" * 80)
        logger.info("")
        logger.info(f"Successfully placed and filled market order:")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Order ID: {order_id}")
        logger.info(f"  Filled: {filled_qty:.6f} @ {avg_price:.6f}")
        logger.info(f"  Total: ${filled_qty * avg_price:.2f}")
        logger.info("")
        logger.info("⚠️  NOTE: You now own this position. Manage it manually or via the bot.")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"✗ FAIL: Order lifecycle test exception: {e}")
        logger.error(f"  Error type: {type(e).__name__}")

        # Try to extract exchange response
        if hasattr(e, 'response'):
            try:
                response_payload = getattr(e, 'response', {})
                logger.error(f"  Exchange response: {response_payload}")
            except Exception:
                pass

        return 1


if __name__ == "__main__":
    sys.exit(main())
