#!/usr/bin/env python3
"""
Force sell METIS/USDT and CKB/USDT positions
Uses MEXC API to close positions that are causing order errors
"""

import os
import sys
import ccxt
from dotenv import load_dotenv

# Load environment
load_dotenv('/etc/alpha-sniper/alpha-sniper-live.env')

# Get API credentials
api_key = os.getenv('MEXC_API_KEY')
secret_key = os.getenv('MEXC_SECRET_KEY')

if not api_key or not secret_key:
    print("❌ ERROR: MEXC_API_KEY or MEXC_SECRET_KEY not found in environment")
    print("Make sure /etc/alpha-sniper/alpha-sniper-live.env has the credentials")
    sys.exit(1)

# Initialize MEXC
print("🔄 Connecting to MEXC...")
exchange = ccxt.mexc({
    'apiKey': api_key,
    'secret': secret_key,
    'enableRateLimit': True,
})

# Symbols to force sell
SYMBOLS_TO_SELL = ['METIS/USDT', 'CKB/USDT']

print("")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("        FORCE SELL PROBLEMATIC POSITIONS")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("")

def get_balance(symbol):
    """Get balance for a symbol (base currency only)"""
    try:
        base = symbol.split('/')[0]  # METIS/USDT -> METIS
        balance = exchange.fetch_balance()

        if base in balance:
            total = balance[base].get('total', 0)
            free = balance[base].get('free', 0)
            return {'total': total, 'free': free}
        return {'total': 0, 'free': 0}
    except Exception as e:
        print(f"⚠️  Warning: Could not fetch balance for {symbol}: {e}")
        return {'total': 0, 'free': 0}

def sell_symbol(symbol):
    """Attempt to sell all balance of a symbol"""
    print(f"📊 Checking {symbol}...")

    try:
        # Get current balance
        bal = get_balance(symbol)
        base = symbol.split('/')[0]

        if bal['total'] <= 0:
            print(f"   ✅ No {base} balance to sell (balance: {bal['total']})")
            return True

        # Get market info for minimum order size
        markets = exchange.load_markets()
        market = markets.get(symbol)

        if not market:
            print(f"   ❌ Market {symbol} not found on MEXC")
            return False

        # Check minimum order size
        min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
        amount = bal['free']

        if amount < min_amount:
            print(f"   ⚠️  Balance {amount} {base} below minimum order size {min_amount}")
            print(f"   💡 Try selling manually on MEXC web interface")
            return False

        print(f"   💰 Balance: {amount} {base}")
        print(f"   📤 Creating MARKET SELL order...")

        # Create market sell order
        order = exchange.create_market_sell_order(symbol, amount)

        if order and order.get('id'):
            print(f"   ✅ SOLD {amount} {base} successfully!")
            print(f"      Order ID: {order['id']}")
            print(f"      Status: {order.get('status', 'unknown')}")
            return True
        else:
            print(f"   ❌ Order creation returned no ID")
            return False

    except ccxt.InsufficientBalance as e:
        print(f"   ⚠️  Insufficient balance: {e}")
        return False
    except ccxt.InvalidOrder as e:
        print(f"   ❌ Invalid order: {e}")
        print(f"   💡 Try reducing amount or check minimum order size")
        return False
    except Exception as e:
        print(f"   ❌ Error selling {symbol}: {e}")
        print(f"   💡 Try selling manually on MEXC web interface")
        return False

# Process each symbol
results = {}
for symbol in SYMBOLS_TO_SELL:
    success = sell_symbol(symbol)
    results[symbol] = success
    print("")

# Summary
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("SUMMARY")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("")

all_success = True
for symbol, success in results.items():
    status = "✅ SOLD" if success else "❌ FAILED"
    print(f"{status} {symbol}")
    if not success:
        all_success = False

print("")

if all_success:
    print("✅ All positions closed successfully!")
    print("")
    print("Next steps:")
    print("  1. Run cleanup script:")
    print("     sudo ./deployment/close_problematic_positions.sh")
    print("")
    print("  2. Apply blacklist:")
    print("     sudo ./deployment/fix_symbol_errors.sh")
    print("")
    print("  3. Restart service:")
    print("     sudo systemctl restart alpha-sniper-live.service")
else:
    print("⚠️  Some positions could not be closed automatically")
    print("")
    print("If script failed:")
    print("  1. Try selling manually on MEXC Spot trading page")
    print("  2. Check if symbols are suspended/delisted")
    print("  3. Verify API keys have trading permissions")

print("")
