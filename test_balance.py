#!/usr/bin/env python3
"""
Quick script to test MEXC API credentials and fetch balance.
This will help diagnose if API keys are configured correctly.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent / "alpha-sniper"))

try:
    import ccxt.async_support as ccxt
except ImportError:
    print("ERROR: ccxt not installed. Run: pip install ccxt")
    sys.exit(1)


async def test_balance():
    """Test API credentials and fetch balance from all MEXC account types."""

    # Get API credentials from environment
    api_key = os.getenv("ALPHA_API_KEY")
    api_secret = os.getenv("ALPHA_API_SECRET")

    print("=" * 80)
    print("MEXC API BALANCE TEST")
    print("=" * 80)
    print()

    # Check if credentials are set
    if not api_key or not api_secret:
        print("❌ ERROR: API credentials not found!")
        print()
        print("Missing environment variables:")
        if not api_key:
            print("  - ALPHA_API_KEY")
        if not api_secret:
            print("  - ALPHA_API_SECRET")
        print()
        print("Set them with:")
        print('  export ALPHA_API_KEY="your_key_here"')
        print('  export ALPHA_API_SECRET="your_secret_here"')
        return

    print(f"✅ API Key found: {api_key[:8]}...{api_key[-4:]}")
    print(f"✅ API Secret found: {'*' * len(api_secret)}")
    print()

    # Initialize MEXC exchange
    exchange = ccxt.mexc({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'timeout': 30000,
    })

    try:
        # Test 1: Fetch SPOT balance (default)
        print("-" * 80)
        print("TEST 1: SPOT WALLET BALANCE")
        print("-" * 80)

        exchange.options['defaultType'] = 'spot'
        balance = await exchange.fetch_balance()

        print(f"Response keys: {list(balance.keys())}")
        print()

        # Show USDT balance
        usdt_free = balance.get('free', {}).get('USDT', 0.0)
        usdt_used = balance.get('used', {}).get('USDT', 0.0)
        usdt_total = balance.get('total', {}).get('USDT', 0.0)

        print(f"USDT Balance:")
        print(f"  Free:  ${usdt_free:.8f}")
        print(f"  Used:  ${usdt_used:.8f}")
        print(f"  Total: ${usdt_total:.8f}")
        print()

        # Show all non-zero balances
        print("All non-zero balances:")
        total_dict = balance.get('total', {})
        non_zero = {k: v for k, v in total_dict.items() if v > 0 and k not in ['info', 'free', 'used', 'total']}

        if non_zero:
            for currency, amount in sorted(non_zero.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {currency}: {amount}")
        else:
            print("  (no balances)")
        print()

        # Test 2: Try fetching FUTURES balance
        print("-" * 80)
        print("TEST 2: FUTURES WALLET BALANCE (if supported)")
        print("-" * 80)

        try:
            exchange.options['defaultType'] = 'swap'
            futures_balance = await exchange.fetch_balance()

            futures_usdt = futures_balance.get('total', {}).get('USDT', 0.0)
            print(f"✅ Futures USDT Balance: ${futures_usdt:.8f}")
            print()
        except Exception as e:
            print(f"⚠️  Futures balance fetch failed: {e}")
            print()

        # Summary
        print("-" * 80)
        print("SUMMARY")
        print("-" * 80)
        print(f"Spot USDT:    ${usdt_total:.8f}")
        print(f"API Status:   ✅ Connected")
        print()

        if usdt_total < 1.0:
            print("⚠️  WARNING: Very low USDT balance in SPOT wallet!")
            print("   The bot needs USDT to trade spot pairs (BTC/USDT, ETH/USDT, etc.)")
            print()
            print("   If you have USDT elsewhere:")
            print("   1. Check your MEXC Futures wallet")
            print("   2. Transfer USDT from Futures → Spot")
            print("   3. Or deposit USDT to your Spot wallet")

    except ccxt.AuthenticationError as e:
        print(f"❌ AUTHENTICATION ERROR: {e}")
        print()
        print("This means your API key/secret is invalid or:")
        print("  1. API key is incorrect")
        print("  2. API secret is incorrect")
        print("  3. API key doesn't have trading permissions")
        print("  4. IP whitelist is blocking your server")

    except ccxt.ExchangeError as e:
        print(f"❌ EXCHANGE ERROR: {e}")

    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await exchange.close()

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_balance())
