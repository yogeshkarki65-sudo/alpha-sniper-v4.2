#!/usr/bin/env python3
"""
Sell all altcoins to USDT on MEXC.

This script will:
1. Fetch all your spot wallet balances
2. For each altcoin, find the USDT pair
3. Sell at market price to convert to USDT
4. Show summary of conversions
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


async def sell_all_to_usdt(dry_run=True):
    """Sell all altcoins to USDT."""

    # Get API credentials
    api_key = os.getenv("ALPHA_API_KEY")
    api_secret = os.getenv("ALPHA_API_SECRET")

    if not api_key or not api_secret:
        print("❌ ERROR: API credentials not found!")
        print("Run: source .env && export $(cut -d= -f1 .env)")
        return

    print("=" * 80)
    print("SELL ALL ALTCOINS TO USDT")
    print("=" * 80)
    print()

    # Initialize exchange
    exchange = ccxt.mexc({
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'timeout': 30000,
    })

    try:
        # Fetch markets
        print("Loading markets...")
        await exchange.load_markets()
        print(f"✅ Loaded {len(exchange.markets)} markets")
        print()

        # Fetch balance
        print("Fetching balances...")
        balance = await exchange.fetch_balance()
        total_balances = balance.get('total', {})

        # Filter out USDT and zero balances
        altcoins = {
            coin: amount
            for coin, amount in total_balances.items()
            if coin != 'USDT' and amount > 0 and coin not in ['info', 'free', 'used', 'total']
        }

        if not altcoins:
            print("✅ No altcoins to sell!")
            return

        print(f"Found {len(altcoins)} altcoins to sell:")
        print()

        # Plan sales
        sell_orders = []
        total_estimated_usdt = 0.0

        for coin, amount in sorted(altcoins.items(), key=lambda x: x[1], reverse=True):
            symbol = f"{coin}/USDT"

            # Check if market exists
            if symbol not in exchange.markets:
                print(f"⚠️  {coin}: {amount} → No USDT market, skipping")
                continue

            market = exchange.markets[symbol]

            # Get current price
            try:
                ticker = await exchange.fetch_ticker(symbol)
                current_price = ticker.get('last', 0)
                estimated_usdt = amount * current_price

                # Check minimum order size
                min_cost = market.get('limits', {}).get('cost', {}).get('min', 0)

                if estimated_usdt < min_cost:
                    print(f"⚠️  {coin}: {amount} → ${estimated_usdt:.2f} (below min ${min_cost:.2f}), skipping")
                    continue

                sell_orders.append({
                    'coin': coin,
                    'symbol': symbol,
                    'amount': amount,
                    'price': current_price,
                    'estimated_usdt': estimated_usdt,
                    'market': market
                })

                total_estimated_usdt += estimated_usdt
                print(f"✅ {coin}: {amount:.2f} → ${estimated_usdt:.2f} USDT @ ${current_price:.6f}")

            except Exception as e:
                print(f"❌ {coin}: Error fetching price - {e}")

        print()
        print("-" * 80)
        print(f"TOTAL ESTIMATED: ${total_estimated_usdt:.2f} USDT")
        print(f"ORDERS TO PLACE: {len(sell_orders)}")
        print("-" * 80)
        print()

        if not sell_orders:
            print("❌ No valid sell orders to place!")
            return

        # Confirmation
        if dry_run:
            print("🔍 DRY RUN MODE - No orders will be placed")
            print()
            print("To execute these sales, run:")
            print("  python sell_all_to_usdt.py --execute")
            return

        print("⚠️  WARNING: This will sell ALL altcoins for USDT at MARKET PRICE!")
        print("This action CANNOT be undone!")
        print()
        response = input("Type 'YES' to confirm: ")

        if response != 'YES':
            print("❌ Cancelled")
            return

        print()
        print("=" * 80)
        print("EXECUTING MARKET SELL ORDERS...")
        print("=" * 80)
        print()

        successful = 0
        failed = 0
        total_usdt_received = 0.0

        for order in sell_orders:
            coin = order['coin']
            symbol = order['symbol']
            amount = order['amount']

            try:
                # Round amount to exchange precision
                amount_precision = order['market'].get('precision', {}).get('amount', 8)
                amount = float(exchange.amount_to_precision(symbol, amount))

                print(f"Selling {coin}: {amount} @ market price...")

                # Place market sell order
                result = await exchange.create_market_sell_order(symbol, amount)

                filled = result.get('filled', amount)
                cost = result.get('cost', 0)  # USDT received
                avg_price = result.get('average', order['price'])

                total_usdt_received += cost
                successful += 1

                print(f"  ✅ Sold {filled} {coin} → ${cost:.2f} USDT @ ${avg_price:.6f}")

            except Exception as e:
                failed += 1
                print(f"  ❌ Failed: {e}")

            # Small delay to respect rate limits
            await asyncio.sleep(0.5)

        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Successful: {successful}")
        print(f"Failed:     {failed}")
        print(f"USDT Received: ${total_usdt_received:.2f}")
        print()

        # Show final balance
        final_balance = await exchange.fetch_balance()
        final_usdt = final_balance.get('total', {}).get('USDT', 0)
        print(f"Final USDT Balance: ${final_usdt:.2f}")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await exchange.close()

    print("=" * 80)


if __name__ == "__main__":
    # Check for --execute flag
    execute = '--execute' in sys.argv or '--exec' in sys.argv

    asyncio.run(sell_all_to_usdt(dry_run=not execute))
