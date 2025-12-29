#!/usr/bin/env python3
"""
Production Smoke Test for Alpha Sniper v4.2

Tests LIVE mode infrastructure without placing real orders:
- Config loads with valid API keys
- MEXC connection works
- Database connection works
- Telegram connection works (if configured)
- Universe selection works
- Market data fetch works

Usage:
    python scripts/smoke_test_live.py

Exit codes:
    0: All tests passed
    1: One or more tests failed
"""

import sys
import os
from pathlib import Path

# Add alpha-sniper to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "alpha-sniper"))

def test_config():
    """Test config loads with API keys."""
    print("=" * 70)
    print("TEST 1: Configuration Loading")
    print("=" * 70)

    try:
        from config import Config
        config = Config()

        print(f"✓ Config loaded successfully")
        print(f"  Exchange: {config.mexc_api_key[:8]}..." if config.mexc_api_key else "  ⚠ No API key")
        print(f"  Secret: {config.mexc_secret_key[:8]}..." if config.mexc_secret_key else "  ⚠ No secret")
        print(f"  Telegram: {config.telegram_bot_token[:10]}..." if config.telegram_bot_token else "  ⚠ No telegram")
        print(f"  Starting equity: ${config.starting_equity:.2f}")

        if not config.mexc_api_key or not config.mexc_secret_key:
            print("❌ FAIL: Missing required MEXC API keys")
            return False

        print("✅ PASS: Config loaded with API keys")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


def test_mexc_connection():
    """Test MEXC exchange connection."""
    print("\n" + "=" * 70)
    print("TEST 2: MEXC Exchange Connection")
    print("=" * 70)

    try:
        from config import Config
        from exchange import create_exchange
        from utils import setup_logger

        config = Config()
        logger = setup_logger()
        exchange = create_exchange(config, logger)

        # Test: Load markets
        print("Loading markets...")
        markets = exchange.exchange_instance.load_markets()
        print(f"✓ Loaded {len(markets)} markets")

        # Test: Get balance
        print("Fetching balance...")
        balance = exchange.get_total_usdt_balance()
        print(f"✓ USDT balance: ${balance:.2f}")

        # Test: Fetch ticker for BTC/USDT
        print("Fetching BTC/USDT ticker...")
        ticker = exchange.fetch_ticker("BTC/USDT")
        print(f"✓ BTC/USDT price: ${ticker['last']:.2f}")

        print("✅ PASS: MEXC connection working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test database connection."""
    print("\n" + "=" * 70)
    print("TEST 3: Database Connection")
    print("=" * 70)

    try:
        import sqlite3
        from pathlib import Path

        db_path = Path(project_root) / "data" / "alpha.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Test: Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"✓ Connected to database: {db_path}")
        print(f"✓ Found {len(tables)} tables: {[t[0] for t in tables]}")

        conn.close()

        print("✅ PASS: Database connection working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        return False


def test_telegram():
    """Test Telegram connection (optional)."""
    print("\n" + "=" * 70)
    print("TEST 4: Telegram Connection (Optional)")
    print("=" * 70)

    try:
        from config import Config
        config = Config()

        if not config.telegram_bot_token or not config.telegram_chat_id:
            print("⚠ Telegram not configured (optional) - SKIP")
            return True

        from notify.telegram import TelegramNotifier
        telegram = TelegramNotifier(
            config.telegram_bot_token,
            config.telegram_chat_id
        )

        # Test: Send test message
        print("Sending test message...")
        telegram.send("✅ Alpha Sniper v4.2 smoke test - Telegram working!", "SmokeTest")
        print("✓ Test message sent successfully")

        print("✅ PASS: Telegram connection working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_universe_selection():
    """Test universe selection."""
    print("\n" + "=" * 70)
    print("TEST 5: Universe Selection")
    print("=" * 70)

    try:
        from config import Config
        from exchange import create_exchange
        from utils import setup_logger

        config = Config()
        logger = setup_logger()
        exchange = create_exchange(config, logger)

        # Load markets first
        exchange.exchange_instance.load_markets()

        # Get all USDT pairs
        print("Fetching USDT pairs...")
        all_symbols = exchange.exchange_instance.symbols
        usdt_pairs = [s for s in all_symbols if '/USDT' in s]
        print(f"✓ Found {len(usdt_pairs)} USDT pairs")

        # Fetch tickers (with limit for smoke test)
        print("Fetching tickers for top 50 pairs...")
        tickers = {}
        for symbol in usdt_pairs[:50]:
            try:
                ticker = exchange.fetch_ticker(symbol)
                if ticker and 'quoteVolume' in ticker:
                    tickers[symbol] = ticker
            except Exception:
                pass  # Skip problematic symbols

        # Sort by volume
        sorted_symbols = sorted(
            tickers.items(),
            key=lambda x: x[1].get('quoteVolume', 0),
            reverse=True
        )

        top_10 = sorted_symbols[:10]
        print(f"✓ Top 10 by volume:")
        for symbol, ticker in top_10:
            vol = ticker.get('quoteVolume', 0)
            print(f"    {symbol}: ${vol:,.0f} 24h volume")

        print("✅ PASS: Universe selection working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_market_data_fetch():
    """Test OHLCV data fetch."""
    print("\n" + "=" * 70)
    print("TEST 6: Market Data Fetch")
    print("=" * 70)

    try:
        from config import Config
        from exchange import create_exchange
        from utils import setup_logger

        config = Config()
        logger = setup_logger()
        exchange = create_exchange(config, logger)

        # Load markets
        exchange.exchange_instance.load_markets()

        # Fetch OHLCV for BTC/USDT
        print("Fetching OHLCV for BTC/USDT (1m, 100 candles)...")
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1m", limit=100)
        print(f"✓ Fetched {len(ohlcv)} candles")

        if len(ohlcv) > 0:
            latest = ohlcv[-1]
            print(f"✓ Latest candle: O={latest[1]:.2f} H={latest[2]:.2f} L={latest[3]:.2f} C={latest[4]:.2f}")

        print("✅ PASS: Market data fetch working")
        return True

    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all smoke tests."""
    print("\n" + "🚀" * 35)
    print("Alpha Sniper v4.2 - Production Smoke Test")
    print("🚀" * 35)
    print()

    results = []

    # Run all tests
    results.append(("Config", test_config()))
    results.append(("MEXC Connection", test_mexc_connection()))
    results.append(("Database", test_database()))
    results.append(("Telegram", test_telegram()))
    results.append(("Universe Selection", test_universe_selection()))
    results.append(("Market Data", test_market_data_fetch()))

    # Print summary
    print("\n" + "=" * 70)
    print("SMOKE TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")

    print("=" * 70)
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 70)

    if passed == total:
        print("\n🎉 All smoke tests passed! System is ready for production.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Fix issues before deploying.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nSmoke test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
