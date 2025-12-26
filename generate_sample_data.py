#!/usr/bin/env python3
"""
Sample Data Generator for Backtesting

Generates synthetic OHLCV data for testing the backtester without
needing to download real data from MEXC.

Usage:
    python generate_sample_data.py --output-dir sample_data
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_pump_scenario(
    start_price: float,
    num_candles: int,
    pump_at: int,
    pump_magnitude: float = 0.50,
    volume_base: float = 1000000
) -> pd.DataFrame:
    """
    Generate OHLCV data with a simulated pump

    Args:
        start_price: Starting price
        num_candles: Number of candles to generate
        pump_at: Candle index where pump starts
        pump_magnitude: Pump size (0.50 = 50% pump)
        volume_base: Base volume

    Returns:
        DataFrame with OHLCV data
    """
    np.random.seed(42)

    prices = [start_price]
    volumes = []

    for i in range(num_candles):
        # Generate realistic price movement
        if i < pump_at:
            # Pre-pump: sideways with low volatility
            change = np.random.normal(0, 0.005)
        elif pump_at <= i < pump_at + 20:
            # Pump phase: strong upward momentum
            change = np.random.normal(0.03, 0.01)  # 3% average move up
        else:
            # Post-pump: consolidation
            change = np.random.normal(-0.005, 0.01)

        new_price = prices[-1] * (1 + change)
        prices.append(new_price)

        # Volume spike during pump
        if pump_at <= i < pump_at + 20:
            vol = volume_base * np.random.uniform(3, 5)  # 3-5x volume spike
        else:
            vol = volume_base * np.random.uniform(0.8, 1.2)

        volumes.append(vol)

    # Generate OHLC from close prices
    data = []
    for i in range(len(prices) - 1):
        close = prices[i + 1]
        open_price = prices[i]
        high = max(open_price, close) * np.random.uniform(1.001, 1.01)
        low = min(open_price, close) * np.random.uniform(0.99, 0.999)

        data.append({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volumes[i]
        })

    return pd.DataFrame(data)


def resample_to_timeframe(df_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample 1m data to higher timeframe

    Args:
        df_1m: 1m OHLCV DataFrame (with timestamp index)
        timeframe: Target timeframe (15m or 1h)

    Returns:
        Resampled DataFrame
    """
    timeframe_map = {
        '15m': '15T',
        '1h': '1H'
    }

    rule = timeframe_map.get(timeframe, '15T')

    resampled = df_1m.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })

    return resampled.dropna()


def main():
    parser = argparse.ArgumentParser(
        description='Generate sample OHLCV data for backtesting'
    )

    parser.add_argument(
        '--output-dir',
        default='sample_data',
        help='Output directory (default: sample_data/)'
    )
    parser.add_argument(
        '--symbols',
        default='TESTUSDT',
        help='Comma-separated symbols to generate (default: TESTUSDT)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Days of data to generate (default: 30)'
    )
    parser.add_argument(
        '--pumps',
        type=int,
        default=5,
        help='Number of pumps to simulate (default: 5)'
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    symbols = [s.strip() for s in args.symbols.split(',')]

    print("\n📊 Sample Data Generator")
    print("=" * 70)
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Duration: {args.days} days")
    print(f"Pumps: {args.pumps}")
    print(f"Output: {output_dir}/")
    print("=" * 70)
    print()

    for symbol in symbols:
        print(f"Generating {symbol}...")

        # Calculate timestamps
        end_time = datetime.now()
        start_time = end_time - timedelta(days=args.days)

        # Number of 1m candles
        num_candles = args.days * 24 * 60

        # Generate timestamps
        timestamps = pd.date_range(
            start=start_time,
            end=end_time,
            periods=num_candles,
            tz='UTC'
        )

        # Generate base price action
        start_price = np.random.uniform(10, 100)
        df_1m = generate_pump_scenario(
            start_price,
            num_candles,
            pump_at=int(num_candles * 0.3),  # First pump at 30%
            pump_magnitude=0.50
        )

        # Add multiple pumps
        for pump_idx in range(1, args.pumps):
            pump_location = int(num_candles * (0.3 + (pump_idx * 0.15)))
            if pump_location < num_candles:
                pump_data = generate_pump_scenario(
                    df_1m.iloc[pump_location - 1]['close'],
                    num_candles - pump_location,
                    pump_at=10,
                    pump_magnitude=np.random.uniform(0.30, 0.80)
                )
                df_1m.iloc[pump_location:] = pump_data.iloc[:len(df_1m) - pump_location].values

        # Add timestamps
        df_1m.index = timestamps

        # Convert timestamp to milliseconds
        df_1m['timestamp'] = (df_1m.index.astype(int) // 10**6).astype(int)

        # Reorder columns
        df_1m = df_1m[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        # Save 1m data
        symbol_clean = symbol.replace('/', '')
        filepath_1m = output_dir / f"{symbol_clean}_1m.csv"
        df_1m.to_csv(filepath_1m, index=False)
        print(f"  ✅ {filepath_1m.name}: {len(df_1m)} candles")

        # Resample to 15m
        df_1m_indexed = df_1m.set_index(pd.to_datetime(df_1m['timestamp'], unit='ms', utc=True))
        df_15m = resample_to_timeframe(df_1m_indexed, '15m')
        df_15m['timestamp'] = (df_15m.index.astype(int) // 10**6).astype(int)
        df_15m = df_15m[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        filepath_15m = output_dir / f"{symbol_clean}_15m.csv"
        df_15m.to_csv(filepath_15m, index=False)
        print(f"  ✅ {filepath_15m.name}: {len(df_15m)} candles")

        # Resample to 1h
        df_1h = resample_to_timeframe(df_1m_indexed, '1h')
        df_1h['timestamp'] = (df_1h.index.astype(int) // 10**6).astype(int)
        df_1h = df_1h[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

        filepath_1h = output_dir / f"{symbol_clean}_1h.csv"
        df_1h.to_csv(filepath_1h, index=False)
        print(f"  ✅ {filepath_1h.name}: {len(df_1h)} candles")

        print()

    print("=" * 70)
    print(f"✅ Sample data generated in: {output_dir}/")
    print()
    print("Test with:")
    print("  python backtest_pump.py \\")
    print(f"    --symbols {','.join(symbols)} \\")
    print(f"    --start {(end_time - timedelta(days=args.days)).strftime('%Y-%m-%d')} \\")
    print(f"    --end {end_time.strftime('%Y-%m-%d')} \\")
    print(f"    --data-dir {output_dir}")
    print()


if __name__ == '__main__':
    import sys
    sys.exit(main())
