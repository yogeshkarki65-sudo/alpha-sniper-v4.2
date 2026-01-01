#!/usr/bin/env python3
"""
Why No Trade? - One-shot diagnostic for alpha-sniper

Runs a single scan cycle and reports why symbols are failing filters.
Does NOT place any orders - purely diagnostic.

Usage: python scripts/why_no_trade.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from collections import defaultdict

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

from config.settings import get_settings
from core.exchange_async import AsyncExchange
from risk.async_risk_engine import AsyncRiskEngine
from signals.pump_engine import PumpEngine
from universe.select import select_top_liquid_symbols_with_cache
from scanner.runner import scan_symbols


async def main():
    """Run diagnostic scan and report filter failures."""
    print("🔍 Running Why-No-Trade Diagnostic...\n", file=sys.stderr)

    # Load settings
    settings = get_settings()

    # Initialize components
    exchange = AsyncExchange(
        exchange_id=settings.EXCHANGE_ID,
        api_key=settings.API_KEY,
        secret=settings.API_SECRET,
        testnet=settings.TESTNET
    )
    await exchange.initialize()

    risk = AsyncRiskEngine(settings.DB_PATH, settings, None)
    await risk.connect()

    pump_engine = PumpEngine(settings, None)

    # Reset audit counters
    await risk.audit_reset()

    # Step 1: Select universe
    print(f"📊 Selecting top {settings.UNIVERSE_SIZE} symbols...", file=sys.stderr)
    universe = await select_top_liquid_symbols_with_cache(
        exchange,
        max_symbols=settings.UNIVERSE_SIZE,
        base_quote=settings.UNIVERSE_BASE_QUOTE,
        min_volume=settings.UNIVERSE_MIN_QUOTE_VOLUME,
        cache_ttl=60
    )
    print(f"✓ Selected {len(universe)} symbols\n", file=sys.stderr)

    # Step 2: Fetch market data
    print(f"📈 Fetching market data (concurrency={settings.SCAN_CONCURRENCY})...", file=sys.stderr)
    market_data = await scan_symbols(
        exchange,
        universe,
        timeframe=settings.TIMEFRAME,
        concurrency=settings.SCAN_CONCURRENCY
    )
    print(f"✓ Fetched data for {len(market_data)} symbols\n", file=sys.stderr)

    # Step 3: Analyze why symbols fail
    print("🔬 Analyzing filter failures...\n", file=sys.stderr)

    failures = defaultdict(int)
    failure_examples = defaultdict(list)

    for symbol, md in market_data.items():
        df = md.get('df')

        if df is None or len(df) < 25:
            failures['nodata'] += 1
            failure_examples['nodata'].append(symbol)
            continue

        # Check early pump detection criteria
        close_col = 'close' if 'close' in df.columns else 'c'
        vol_col = 'volume' if 'volume' in df.columns else 'v'

        if close_col not in df.columns or vol_col not in df.columns:
            failures['badframe'] += 1
            failure_examples['badframe'].append(symbol)
            continue

        close = df[close_col]
        vol = df[vol_col]

        # Calculate metrics
        c_now = float(close.iloc[-1])
        c_5m_ago = float(close.iloc[-6]) if len(close) >= 6 else float(close.iloc[0])
        ret_5m = (c_now / c_5m_ago) - 1.0 if c_5m_ago > 0 else 0.0

        v_last = float(vol.iloc[-1])
        v_avg20 = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())
        vol_spike = (v_last / v_avg20) if v_avg20 > 0 else 0.0

        accelerating = float(close.iloc[-1]) > float(close.iloc[-2]) if len(close) >= 2 else False

        # Check thresholds
        early_ret_5m_min = getattr(settings, 'EARLY_RET_5M_MIN', 0.03)
        early_vol_spike_min = getattr(settings, 'EARLY_VOL_SPIKE_MIN', 3.0)
        early_accel_required = getattr(settings, 'EARLY_ACCEL_REQUIRED', True)
        min_score = getattr(settings, 'MIN_SCORE', 28)

        failed = False

        if ret_5m < early_ret_5m_min:
            failures['ret5m_low'] += 1
            if len(failure_examples['ret5m_low']) < 3:
                failure_examples['ret5m_low'].append(f"{symbol} (ret={ret_5m*100:.2f}%)")
            failed = True

        if vol_spike < early_vol_spike_min:
            failures['volspike_low'] += 1
            if len(failure_examples['volspike_low']) < 3:
                failure_examples['volspike_low'].append(f"{symbol} (spike={vol_spike:.2f}x)")
            failed = True

        if early_accel_required and not accelerating:
            failures['no_accel'] += 1
            if len(failure_examples['no_accel']) < 3:
                failure_examples['no_accel'].append(symbol)
            failed = True

        indicators = md.get('indicators', {})
        score = indicators.get('score', 0)
        if score < min_score:
            failures['score_low'] += 1
            if len(failure_examples['score_low']) < 3:
                failure_examples['score_low'].append(f"{symbol} (score={score})")
            failed = True

        if not failed:
            failures['passed_early'] += 1
            if len(failure_examples['passed_early']) < 3:
                failure_examples['passed_early'].append(symbol)

    # Generate signals to see what passes
    signals = pump_engine.generate_signals(market_data, regime='BULL')

    # Build result
    result = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "settings": {
            "UNIVERSE_SIZE": settings.UNIVERSE_SIZE,
            "EARLY_RET_5M_MIN": getattr(settings, 'EARLY_RET_5M_MIN', 0.03),
            "EARLY_VOL_SPIKE_MIN": getattr(settings, 'EARLY_VOL_SPIKE_MIN', 3.0),
            "EARLY_ACCEL_REQUIRED": getattr(settings, 'EARLY_ACCEL_REQUIRED', True),
            "MIN_SCORE": getattr(settings, 'MIN_SCORE', 28),
            "WICK_FILTER_ENABLE": getattr(settings, 'WICK_FILTER_ENABLE', True),
        },
        "scanned": len(market_data),
        "signals_generated": len(signals),
        "failure_counts": dict(failures),
        "failure_examples": {k: v[:3] for k, v in failure_examples.items()},
        "sample_signals": [
            {
                "symbol": sig.get('symbol'),
                "ret_5m": sig.get('ret_5m'),
                "vol_spike": sig.get('vol_spike'),
            }
            for sig in signals[:5]
        ]
    }

    # Cleanup
    await exchange.close()
    await risk.close()

    # Output JSON
    print(json.dumps(result, indent=2))

    # Print human-readable summary to stderr
    print("\n" + "="*60, file=sys.stderr)
    print("📊 SUMMARY", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"Symbols scanned: {len(market_data)}", file=sys.stderr)
    print(f"Signals generated: {len(signals)}", file=sys.stderr)
    print(f"\nFilter Failures:", file=sys.stderr)
    for reason, count in sorted(failures.items(), key=lambda x: -x[1]):
        pct = (count / len(market_data) * 100) if len(market_data) > 0 else 0
        print(f"  {reason:20s}: {count:4d} ({pct:5.1f}%)", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
