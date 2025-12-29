"""
Async Scanner Benchmark Script

Measures scan performance with configurable parameters.
Reports detailed timing metrics including p50/p90/p95 latencies.

Usage:
    python scripts/bench_scan_async.py [--symbols N] [--timeframe TF] [--concurrency C]

Example:
    python scripts/bench_scan_async.py --symbols 80 --timeframe 1m --concurrency 5
"""

import asyncio
import sys
import time
import argparse
from pathlib import Path
from typing import List

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

from config.settings import get_settings
from core.exchange_async import AsyncExchange
from scanner.runner import scan_symbols
from universe.select import select_top_liquid_symbols


async def bench_scan(
    symbol_count: int = 80,
    timeframe: str = "1m",
    concurrency: int = 5,
    runs: int = 3,
):
    """
    Benchmark scanner performance.

    Args:
        symbol_count: Number of symbols to scan
        timeframe: OHLCV timeframe
        concurrency: Max concurrent fetches
        runs: Number of benchmark runs
    """
    print("=" * 80)
    print("🔬 ALPHA SNIPER v4.2 - ASYNC SCANNER BENCHMARK")
    print("=" * 80)
    print(f"Target symbols: {symbol_count}")
    print(f"Timeframe: {timeframe}")
    print(f"Concurrency: {concurrency}")
    print(f"Benchmark runs: {runs}")
    print("=" * 80)
    print()

    # Load settings
    settings = get_settings()

    # Initialize exchange
    print("Initializing exchange...")
    exchange = AsyncExchange(
        exchange_id=settings.EXCHANGE_ID,
        api_key=settings.API_KEY,
        secret=settings.API_SECRET,
        testnet=settings.TESTNET,
    )

    # Load markets
    print("Loading markets...")
    await exchange.load_markets()
    print(f"✓ Markets loaded\n")

    # Select universe
    print(f"Selecting top {symbol_count} liquid symbols...")
    symbols = await select_top_liquid_symbols(
        exchange,
        base_quote="USDT",
        max_symbols=symbol_count,
        min_quote_volume=10000.0,  # Lower threshold for benchmark
    )

    if len(symbols) < symbol_count:
        print(f"⚠️  Warning: Only {len(symbols)} symbols available (target: {symbol_count})")

    print(f"✓ Selected {len(symbols)} symbols")
    print()

    # Run benchmarks
    total_times = []
    avg_fetch_times = []
    p50_fetch_times = []
    p90_fetch_times = []
    p95_fetch_times = []

    for run in range(1, runs + 1):
        print(f"{'=' * 80}")
        print(f"RUN {run}/{runs}")
        print(f"{'=' * 80}")

        start_time = time.time()

        # Run scan
        results = await scan_symbols(
            symbols=symbols,
            timeframe=timeframe,
            exchange=exchange,
            concurrency=concurrency,
            limit=500,
        )

        total_time = (time.time() - start_time) * 1000  # milliseconds

        # Collect fetch times
        fetch_times = [data["fetch_time_ms"] for data in results.values()]

        if fetch_times:
            avg_fetch = sum(fetch_times) / len(fetch_times)
            fetch_times_sorted = sorted(fetch_times)
            p50_fetch = fetch_times_sorted[len(fetch_times_sorted) // 2]
            p90_fetch = fetch_times_sorted[int(len(fetch_times_sorted) * 0.9)]
            p95_fetch = fetch_times_sorted[int(len(fetch_times_sorted) * 0.95)]
        else:
            avg_fetch = p50_fetch = p90_fetch = p95_fetch = 0

        total_times.append(total_time)
        avg_fetch_times.append(avg_fetch)
        p50_fetch_times.append(p50_fetch)
        p90_fetch_times.append(p90_fetch)
        p95_fetch_times.append(p95_fetch)

        print(f"\n📊 RUN {run} RESULTS:")
        print(f"  Total scan time:     {total_time:>10.0f} ms")
        print(f"  Symbols scanned:     {len(results):>10}")
        print(f"  Avg fetch time:      {avg_fetch:>10.0f} ms")
        print(f"  P50 fetch time:      {p50_fetch:>10.0f} ms")
        print(f"  P90 fetch time:      {p90_fetch:>10.0f} ms")
        print(f"  P95 fetch time:      {p95_fetch:>10.0f} ms")
        print()

        # Wait between runs
        if run < runs:
            print("Waiting 5s before next run...")
            await asyncio.sleep(5)
            print()

    # Summary statistics
    print("=" * 80)
    print("📈 BENCHMARK SUMMARY")
    print("=" * 80)

    def stats(values: List[float]) -> dict:
        """Calculate statistics."""
        sorted_vals = sorted(values)
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "median": sorted_vals[len(sorted_vals) // 2],
        }

    total_stats = stats(total_times)
    p50_stats = stats(p50_fetch_times)
    p90_stats = stats(p90_fetch_times)
    p95_stats = stats(p95_fetch_times)

    print(f"\n🎯 Total Scan Time (ms):")
    print(f"  Min:     {total_stats['min']:>10.0f}")
    print(f"  Max:     {total_stats['max']:>10.0f}")
    print(f"  Avg:     {total_stats['avg']:>10.0f}")
    print(f"  Median:  {total_stats['median']:>10.0f}")

    print(f"\n⚡ Per-Symbol Fetch Time P50 (ms):")
    print(f"  Min:     {p50_stats['min']:>10.0f}")
    print(f"  Max:     {p50_stats['max']:>10.0f}")
    print(f"  Avg:     {p50_stats['avg']:>10.0f}")
    print(f"  Median:  {p50_stats['median']:>10.0f}")

    print(f"\n⚡ Per-Symbol Fetch Time P90 (ms):")
    print(f"  Min:     {p90_stats['min']:>10.0f}")
    print(f"  Max:     {p90_stats['max']:>10.0f}")
    print(f"  Avg:     {p90_stats['avg']:>10.0f}")
    print(f"  Median:  {p90_stats['median']:>10.0f}")

    print(f"\n⚡ Per-Symbol Fetch Time P95 (ms):")
    print(f"  Min:     {p95_stats['min']:>10.0f}")
    print(f"  Max:     {p95_stats['max']:>10.0f}")
    print(f"  Avg:     {p95_stats['avg']:>10.0f}")
    print(f"  Median:  {p95_stats['median']:>10.0f}")

    # Performance goals check
    print("\n" + "=" * 80)
    print("✅ PERFORMANCE GOALS CHECK")
    print("=" * 80)

    goals_met = True

    # Goal 1: Total scan time ≤ 12s for 80 symbols @ 1m
    if symbol_count == 80 and timeframe == "1m":
        target_total = 12000  # 12 seconds
        actual_total = total_stats["median"]
        passed = actual_total <= target_total
        goals_met &= passed

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\nGoal 1: Total scan time ≤ 12s (80 symbols, 1m)")
        print(f"  Target:  {target_total:>10.0f} ms")
        print(f"  Actual:  {actual_total:>10.0f} ms")
        print(f"  Status:  {status}")

    # Goal 2: P50 fetch ≤ 250ms
    target_p50 = 250
    actual_p50 = p50_stats["median"]
    passed = actual_p50 <= target_p50
    goals_met &= passed

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\nGoal 2: P50 fetch time ≤ 250ms")
    print(f"  Target:  {target_p50:>10.0f} ms")
    print(f"  Actual:  {actual_p50:>10.0f} ms")
    print(f"  Status:  {status}")

    # Goal 3: P95 fetch ≤ 500ms
    target_p95 = 500
    actual_p95 = p95_stats["median"]
    passed = actual_p95 <= target_p95
    goals_met &= passed

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\nGoal 3: P95 fetch time ≤ 500ms")
    print(f"  Target:  {target_p95:>10.0f} ms")
    print(f"  Actual:  {actual_p95:>10.0f} ms")
    print(f"  Status:  {status}")

    print("\n" + "=" * 80)
    if goals_met:
        print("🎉 ALL PERFORMANCE GOALS MET!")
    else:
        print("⚠️  Some performance goals not met - see details above")
    print("=" * 80)

    # Cleanup
    await exchange.close()

    return 0 if goals_met else 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Benchmark async scanner performance")
    parser.add_argument("--symbols", type=int, default=80, help="Number of symbols to scan")
    parser.add_argument("--timeframe", type=str, default="1m", help="OHLCV timeframe")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent fetches")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs")

    args = parser.parse_args()

    try:
        exit_code = asyncio.run(bench_scan(
            symbol_count=args.symbols,
            timeframe=args.timeframe,
            concurrency=args.concurrency,
            runs=args.runs,
        ))
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
