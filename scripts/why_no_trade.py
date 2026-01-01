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
import logging
import inspect
import contextlib
from pathlib import Path
from collections import defaultdict

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

from config.settings import get_settings
from core.exchange_async import AsyncExchange
from risk.async_risk_engine import AsyncRiskEngine
from signals.pump_engine import PumpEngine

# Try to import universe selectors (with fallback) - cleaner with contextlib
_universe_candidates = []
for _name in (
    "select_top_liquid_symbols_with_cache",
    "select_top_liquid_symbols",
    "select_top_symbols",
):
    with contextlib.suppress(Exception):
        from universe import select as _selmod
        fn = getattr(_selmod, _name, None)
        if fn:
            _universe_candidates.append(fn)

# Try to import scanner
try:
    from scanner.runner import scan_symbols as _scan_symbols
except Exception:
    _scan_symbols = None

# Setup simple logger for diagnostics
logging.basicConfig(level=logging.WARNING, format='%(message)s')
diag_logger = logging.getLogger('diagnostic')


async def _fallback_select_universe(exchange, size: int = 40, quote: str = "USDT", min_quote_volume: float = 50000.0):
    """
    Fallback universe selector using fetch_tickers (rate-safe for one-shot diagnostic).

    Returns top N symbols by 24h quote volume.
    """
    await exchange.load_markets()
    symbols = []

    try:
        tickers = await exchange.fetch_tickers()
        ranked = []

        for sym, tk in (tickers or {}).items():
            # Check if symbol is in the desired quote currency
            if not sym.endswith(f"/{quote}"):
                continue

            # Get quote volume
            vol_q = tk.get('quoteVolume') or tk.get('baseVolume') or 0

            if float(vol_q) >= float(min_quote_volume):
                ranked.append((float(vol_q), sym))

        # Sort by volume descending
        ranked.sort(reverse=True)
        symbols = [sym for _, sym in ranked[:size]]

    except Exception as e:
        diag_logger.warning(f"Fallback universe selector failed: {e}")
        # Ultimate fallback: use markets listing
        markets = exchange.client.markets or {}
        for m in markets.values():
            if m.get('quote') == quote and m.get('active', True):
                symbols.append(m['symbol'])
        symbols = symbols[:size]

    return symbols


async def _fallback_scan_symbols(exchange, symbols, timeframe: str = "1m", concurrency: int = 5):
    """
    Fallback market data fetcher with concurrency limiting.

    Returns dict of {symbol: {df: dict-like, indicators: {}, ohlcv: [...]}}
    Creates minimal DF-like structure to satisfy pump engine analysis.
    """
    market_data = {}
    sem = asyncio.Semaphore(concurrency)

    async def fetch_one(sym):
        async with sem:
            try:
                ohlcv = await exchange.fetch_ohlcv(sym, timeframe, limit=26)

                # OHLCV structure: [[ts, open, high, low, close, volume], ...]
                # Create dict-like DF structure for basic analysis
                if ohlcv:
                    closes = [row[4] for row in ohlcv]
                    highs = [row[2] for row in ohlcv]
                    lows = [row[3] for row in ohlcv]
                    vols = [row[5] for row in ohlcv]

                    # Simple dict that mimics pandas DataFrame API
                    class DictFrame:
                        def __init__(self, data):
                            self.data = data
                            self.columns = list(data.keys())

                        def __len__(self):
                            return len(self.data.get('close', []))

                        def __getitem__(self, key):
                            return self.data.get(key, [])

                    df = DictFrame({
                        "close": closes,
                        "high": highs,
                        "low": lows,
                        "volume": vols,
                    })
                else:
                    df = None

                market_data[sym] = {
                    "df": df,
                    "indicators": {},
                    "ohlcv": ohlcv or []
                }
            except Exception as e:
                diag_logger.warning(f"Failed to fetch {sym}: {e}")

    await asyncio.gather(*[fetch_one(s) for s in symbols], return_exceptions=True)
    return market_data


async def _select_universe_robust(exchange, settings):
    """
    Try available universe selection functions with signature-aware kwargs.
    Falls back to simple ticker-based selection if all fail.
    """
    # Build parameter mapping with all possible names
    param_mapping = {
        'exchange': exchange,
        'ex': exchange,
        'size': settings.UNIVERSE_SIZE,
        'max_symbols': settings.UNIVERSE_SIZE,
        'limit': settings.UNIVERSE_SIZE,
        'quote': settings.UNIVERSE_BASE_QUOTE,
        'base_quote': settings.UNIVERSE_BASE_QUOTE,
        'min_quote_volume': settings.UNIVERSE_MIN_QUOTE_VOLUME,
        'min_volume': settings.UNIVERSE_MIN_QUOTE_VOLUME,
        'cache': None,  # For cached version
        'cache_ttl': settings.UNIVERSE_CACHE_TTL if hasattr(settings, 'UNIVERSE_CACHE_TTL') else 300,
    }

    # Try each candidate function
    for fn in _universe_candidates:
        try:
            sig = inspect.signature(fn)
            # Build kwargs with only supported parameters
            kwargs = {k: v for k, v in param_mapping.items() if k in sig.parameters}

            result = fn(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            if result:  # Non-empty list
                return result

        except Exception as e:
            diag_logger.warning(f"Universe selector {fn.__name__} failed: {e}")
            continue

    # All candidates failed - use fallback
    diag_logger.info("Using fallback universe selector")
    return await _fallback_select_universe(
        exchange,
        size=settings.UNIVERSE_SIZE,
        quote=settings.UNIVERSE_BASE_QUOTE,
        min_quote_volume=settings.UNIVERSE_MIN_QUOTE_VOLUME
    )


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

    risk = AsyncRiskEngine(settings.DB_PATH, settings, diag_logger)

    try:
        # Connect components
        await exchange.load_markets()
        await risk.connect()

        pump_engine = PumpEngine(settings, diag_logger)

        # Inject risk engine for diagnostics
        if hasattr(pump_engine, 'set_risk'):
            pump_engine.set_risk(risk)
        else:
            pump_engine.risk = risk

        # Reset audit counters
        await risk.audit_reset()

        # Step 1: Select universe (signature-aware with fallback)
        print(f"📊 Selecting top {settings.UNIVERSE_SIZE} symbols...", file=sys.stderr)
        universe = await _select_universe_robust(exchange, settings)
        print(f"✓ Selected {len(universe)} symbols\n", file=sys.stderr)

        # Step 2: Fetch market data (signature-aware with fallback)
        print(f"📈 Fetching market data (concurrency={getattr(settings, 'SCAN_CONCURRENCY', 5)})...", file=sys.stderr)

        if _scan_symbols is not None:
            try:
                # Signature-safe call to scanner
                sig = inspect.signature(_scan_symbols)
                kwargs = {}
                if "exchange" in sig.parameters:
                    kwargs["exchange"] = exchange
                if "ex" in sig.parameters:
                    kwargs["ex"] = exchange
                if "symbols" in sig.parameters:
                    kwargs["symbols"] = universe
                if "timeframe" in sig.parameters:
                    kwargs["timeframe"] = settings.TIMEFRAME
                if "concurrency" in sig.parameters:
                    kwargs["concurrency"] = getattr(settings, 'SCAN_CONCURRENCY', 5)
                if "candles" in sig.parameters:
                    kwargs["candles"] = 26

                market_data = await _scan_symbols(**kwargs)
            except Exception as e:
                diag_logger.warning(f"Scanner failed, using fallback: {e}")
                market_data = await _fallback_scan_symbols(
                    exchange,
                    universe,
                    timeframe=settings.TIMEFRAME,
                    concurrency=getattr(settings, 'SCAN_CONCURRENCY', 5)
                )
        else:
            market_data = await _fallback_scan_symbols(
                exchange,
                universe,
                timeframe=settings.TIMEFRAME,
                concurrency=getattr(settings, 'SCAN_CONCURRENCY', 5)
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

    finally:
        # Always cleanup exchange connection
        try:
            await exchange.close()
        except Exception as e:
            diag_logger.warning(f"Error closing exchange: {e}")

        try:
            await risk.close()
        except Exception as e:
            diag_logger.warning(f"Error closing risk engine: {e}")


if __name__ == "__main__":
    asyncio.run(main())
