#!/usr/bin/env python3
"""
Test script for MEXC futures funding rate fetching

Usage:
    cd alpha-sniper
    python test_funding.py

Expected output (when network allows):
    ✅ BTC/USDT     | funding_8h = 0.000100 (0.0100%)
    ✅ ETH/USDT     | funding_8h = 0.000050 (0.0050%)
    ✅ SOL/USDT     | funding_8h = 0.000200 (0.0200%)

If you get all 0.0 values, the API may be blocked by network/firewall.
The bot will handle this gracefully - shorts will not be filtered by funding.
"""

from config import Config
from exchange import DataOnlyMexcExchange
from utils.logger import setup_logger


def test_funding_rate():
    """Test fetching real MEXC futures funding rates"""
    print("=" * 70)
    print("Testing MEXC Futures Funding Rate Fetching")
    print("=" * 70)

    cfg = Config()
    logger = setup_logger()
    ex = DataOnlyMexcExchange(cfg, logger)

    # Test multiple symbols
    test_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ARB/USDT"]

    print("\nFetching funding rates for test symbols...\n")

    non_zero_count = 0
    for symbol in test_symbols:
        funding = ex.get_funding_rate(symbol)
        if funding != 0:
            non_zero_count += 1
        status = "✅" if funding != 0 else "⚠️"
        print(f"{status} {symbol:12s} | funding_8h = {funding:.6f} ({funding*100:.4f}%)")

    print("\n" + "=" * 70)
    if non_zero_count > 0:
        print(f"✅ SUCCESS! Fetched {non_zero_count}/{len(test_symbols)} non-zero funding rates")
        print("\nThe bot will now use REAL MEXC funding rates in LIVE_DATA SIM mode!")
    else:
        print("⚠️  All funding rates are 0.0")
        print("\nPossible reasons:")
        print("  1. Network/firewall blocking MEXC API (contract.mexc.com)")
        print("  2. MEXC API is down or changed")
        print("  3. Running in restricted environment")
        print("\nThe bot will continue to work - it defaults to 0.0 on fetch failure.")
        print("This means short signals won't be filtered by funding overlay.")
    print("=" * 70)

if __name__ == "__main__":
    test_funding_rate()
