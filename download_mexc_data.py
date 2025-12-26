#!/usr/bin/env python3
"""
MEXC Data Downloader

Downloads historical OHLCV data from MEXC exchange for backtesting.
Saves data in CSV format compatible with backtest_pump.py.

Usage:
    python download_mexc_data.py --symbols BTCUSDT,ETHUSDT --days 60

Requirements:
    pip install ccxt pandas
"""
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import ccxt
import pandas as pd


def download_symbol(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    since: int,
    output_dir: Path
):
    """
    Download OHLCV data for a symbol and timeframe

    Args:
        exchange: CCXT exchange instance
        symbol: Trading pair (e.g., 'BTC/USDT')
        timeframe: Timeframe (1m, 15m, 1h)
        since: Start timestamp in milliseconds
        output_dir: Output directory
    """
    print(f"  Downloading {symbol} {timeframe}...")

    all_candles = []
    current_since = since
    limit = 1000  # MEXC limit per request

    while True:
        try:
            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=current_since,
                limit=limit
            )

            if not candles:
                break

            all_candles.extend(candles)

            # Update since for next batch
            current_since = candles[-1][0] + 1

            # Check if we've reached current time
            now = exchange.milliseconds()
            if current_since >= now:
                break

            # Rate limiting
            time.sleep(exchange.rateLimit / 1000)

            print(f"    Downloaded {len(all_candles)} candles...", end='\r')

        except Exception as e:
            print(f"\n    Error: {e}")
            break

    if not all_candles:
        print("    ⚠️ No data downloaded")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(
        all_candles,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )

    # Save to CSV
    symbol_clean = symbol.replace('/', '')
    filename = f"{symbol_clean}_{timeframe}.csv"
    filepath = output_dir / filename

    df.to_csv(filepath, index=False)

    print(f"    ✅ Saved {len(df)} candles to {filename}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Download historical OHLCV data from MEXC'
    )

    parser.add_argument(
        '--symbols',
        required=True,
        help='Comma-separated list of symbols (e.g., BTCUSDT,ETHUSDT)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=60,
        help='Number of days of historical data (default: 60)'
    )
    parser.add_argument(
        '--output-dir',
        default='data',
        help='Output directory (default: data/)'
    )
    parser.add_argument(
        '--timeframes',
        default='1m,15m,1h',
        help='Comma-separated timeframes (default: 1m,15m,1h)'
    )

    args = parser.parse_args()

    # Parse inputs
    symbols = [s.strip() + '/USDT' if '/' not in s else s.strip() for s in args.symbols.split(',')]
    timeframes = [tf.strip() for tf in args.timeframes.split(',')]

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Calculate start time
    end_time = datetime.now()
    start_time = end_time - timedelta(days=args.days)
    since = int(start_time.timestamp() * 1000)

    print("\n📥 MEXC Data Downloader")
    print("=" * 70)
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Period: {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')} ({args.days} days)")
    print(f"Output: {output_dir}/")
    print("=" * 70)
    print()

    # Initialize MEXC exchange
    try:
        exchange = ccxt.mexc({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        exchange.load_markets()
        print("✅ Connected to MEXC")
        print()
    except Exception as e:
        print(f"❌ Failed to connect to MEXC: {e}")
        return 1

    # Download data
    success_count = 0
    total_count = len(symbols) * len(timeframes)

    for symbol in symbols:
        # Verify symbol exists
        if symbol not in exchange.markets:
            print(f"⚠️ Symbol {symbol} not found on MEXC, skipping")
            continue

        print(f"📊 {symbol}")

        for timeframe in timeframes:
            if download_symbol(exchange, symbol, timeframe, since, output_dir):
                success_count += 1

        print()

    print("=" * 70)
    print(f"✅ Downloaded {success_count}/{total_count} datasets")
    print(f"📁 Data saved to: {output_dir}/")
    print()

    if success_count < total_count:
        print("⚠️ Some downloads failed. Check symbols and try again.")
        return 1

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
