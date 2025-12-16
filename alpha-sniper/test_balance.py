#!/usr/bin/env python3
"""
Test MEXC Balance Fetching

This script tests if the bot can fetch your real USDT balance from MEXC.
"""
import sys
import os
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import get_config
from utils import setup_logger
from exchange import create_exchange

def test_balance_fetch():
    """Test fetching MEXC balance"""
    print("=" * 70)
    print("Testing MEXC Balance Fetch")
    print("=" * 70)
    print()

    # Load config
    try:
        config = get_config()
        logger = setup_logger()
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return False

    # Check if API keys are configured
    if not config.mexc_api_key or config.mexc_api_key == "your_real_key_here":
        print("❌ MEXC API keys not configured")
        print()
        print("To test balance fetching, you need to:")
        print("1. Set MEXC_API_KEY in .env")
        print("2. Set MEXC_SECRET_KEY in .env")
        print()
        print("Get your API keys from: https://www.mexc.com/user/openapi")
        print()
        return False

    print(f"✓ API keys configured")
    print(f"  Key: {config.mexc_api_key[:8]}...{config.mexc_api_key[-4:]}")
    print()

    # Create exchange
    try:
        print("Creating exchange connection...")
        exchange = create_exchange(config, logger)
        print("✓ Exchange created")
        print()
    except Exception as e:
        print(f"❌ Error creating exchange: {e}")
        return False

    # Test balance fetch
    try:
        print("Fetching USDT balance from MEXC...")
        balance = exchange.get_total_usdt_balance()

        if balance is None:
            print("❌ Failed to fetch balance (returned None)")
            print()
            print("Possible issues:")
            print("- Invalid API keys")
            print("- API key doesn't have spot trading permissions")
            print("- Network connectivity issues")
            print("- MEXC API temporarily unavailable")
            return False

        print()
        print("=" * 70)
        print("✅ SUCCESS - Balance Fetched!")
        print("=" * 70)
        print()
        print(f"💰 Total USDT Balance: ${balance:.2f}")
        print()

        # Show more detail if available
        try:
            full_balance = exchange.fetch_balance()
            if full_balance and 'USDT' in full_balance:
                usdt_info = full_balance['USDT']
                free = usdt_info.get('free', 0) or 0
                used = usdt_info.get('used', 0) or 0

                print("Breakdown:")
                print(f"  Free:  ${free:.2f}")
                print(f"  Used:  ${used:.2f}")
                print(f"  Total: ${free + used:.2f}")
                print()
        except:
            pass

        return True

    except Exception as e:
        print(f"❌ Error fetching balance: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_balance_fetch()
    sys.exit(0 if success else 1)
