"""
Async Scanner for Alpha Sniper v4.2

Bounded-concurrency scanner that fetches OHLCV data and computes indicators.
Uses asyncio.Semaphore to limit concurrent requests and respect rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional

import pandas as pd

from analytics import indicators

logger = logging.getLogger(__name__)


def ohlcv_to_dataframe(ohlcv: List[List]) -> pd.DataFrame:
    """
    Convert CCXT OHLCV data to pandas DataFrame.

    Args:
        ohlcv: List of [timestamp, open, high, low, close, volume]

    Returns:
        DataFrame with OHLCV data
    """
    if not ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )

    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    return df


async def fetch_symbol_data(
    symbol: str,
    timeframe: str,
    exchange,
    semaphore: asyncio.Semaphore,
    limit: int = 500,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Fetch OHLCV data and compute indicators for a single symbol.

    Args:
        symbol: Trading pair symbol
        timeframe: OHLCV timeframe (1m, 5m, 15m, etc.)
        exchange: AsyncExchange instance
        semaphore: Semaphore for bounded concurrency
        limit: Number of candles to fetch

    Returns:
        Tuple of (symbol, data_dict) where data_dict contains:
        - df: OHLCV dataframe
        - indicators: Computed indicators dict
        - fetch_time_ms: Time taken to fetch (milliseconds)
    """
    start_time = time.time()

    try:
        # Acquire semaphore (blocks if too many concurrent fetches)
        async with semaphore:
            # Fetch OHLCV data from exchange
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to dataframe
        df = ohlcv_to_dataframe(ohlcv)

        if df.empty:
            logger.warning(f"[{symbol}] Empty OHLCV data")
            return symbol, None

        # Compute indicators
        indicator_dict = indicators.compute_indicators(df, symbol=symbol)

        fetch_time_ms = (time.time() - start_time) * 1000

        return symbol, {
            "df": df,
            "ohlcv": ohlcv,  # Store raw OHLCV for EAGER breakout logic
            "indicators": indicator_dict,
            "fetch_time_ms": fetch_time_ms,
            "timeframe": timeframe,
            "candle_count": len(df),
        }

    except Exception as e:
        logger.error(f"[{symbol}] Error fetching data: {e}")
        return symbol, None


async def scan_symbols(
    *,
    symbols: List[str],
    timeframe: str,
    exchange,
    concurrency: int = 5,
    limit: int = 500,
) -> Dict[str, Dict[str, Any]]:
    """
    Scan multiple symbols concurrently with bounded concurrency.

    Args:
        symbols: List of symbols to scan
        timeframe: OHLCV timeframe
        exchange: AsyncExchange instance
        concurrency: Max concurrent fetches (via Semaphore)
        limit: Number of candles per symbol

    Returns:
        Dict mapping symbol -> data_dict
        Only successful fetches are included
    """
    scan_start = time.time()

    # Create semaphore for bounded concurrency
    semaphore = asyncio.Semaphore(concurrency)

    logger.info(
        f"Starting scan: {len(symbols)} symbols | "
        f"timeframe={timeframe} | concurrency={concurrency}"
    )

    # Create tasks for all symbols
    tasks = [
        fetch_symbol_data(symbol, timeframe, exchange, semaphore, limit)
        for symbol in symbols
    ]

    # Process results as they complete (early processing)
    results = {}
    fetch_times = []

    for future in asyncio.as_completed(tasks):
        symbol, data = await future

        if data is not None:
            results[symbol] = data
            fetch_times.append(data["fetch_time_ms"])

            # Log progress every 10 symbols
            if len(results) % 10 == 0:
                logger.debug(
                    f"Scan progress: {len(results)}/{len(symbols)} symbols processed"
                )

    # Calculate stats
    scan_duration = (time.time() - scan_start) * 1000  # milliseconds
    success_count = len(results)
    failure_count = len(symbols) - success_count

    if fetch_times:
        avg_fetch = sum(fetch_times) / len(fetch_times)
        p50_fetch = sorted(fetch_times)[len(fetch_times) // 2]
        p90_fetch = sorted(fetch_times)[int(len(fetch_times) * 0.9)]
        p95_fetch = sorted(fetch_times)[int(len(fetch_times) * 0.95)]
    else:
        avg_fetch = p50_fetch = p90_fetch = p95_fetch = 0

    logger.info(
        f"Scan completed: {success_count}/{len(symbols)} symbols | "
        f"total={scan_duration:.0f}ms | "
        f"fetch: avg={avg_fetch:.0f}ms p50={p50_fetch:.0f}ms "
        f"p90={p90_fetch:.0f}ms p95={p95_fetch:.0f}ms | "
        f"failures={failure_count}"
    )

    return results


async def scan_symbols_multi_timeframe(
    symbols: List[str],
    timeframes: List[str],
    exchange,
    concurrency: int = 5,
    limit: int = 500,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Scan multiple symbols across multiple timeframes.

    Args:
        symbols: List of symbols
        timeframes: List of timeframes (e.g., ['1m', '5m', '15m'])
        exchange: AsyncExchange instance
        concurrency: Max concurrent fetches
        limit: Candles per fetch

    Returns:
        Nested dict: symbol -> timeframe -> data_dict
    """
    logger.info(
        f"Multi-timeframe scan: {len(symbols)} symbols × {len(timeframes)} timeframes"
    )

    results = {}

    for timeframe in timeframes:
        tf_results = await scan_symbols(symbols, timeframe, exchange, concurrency, limit)

        for symbol, data in tf_results.items():
            if symbol not in results:
                results[symbol] = {}
            results[symbol][timeframe] = data

    logger.info(
        f"Multi-timeframe scan completed: {len(results)} symbols × "
        f"{len(timeframes)} timeframes"
    )

    return results


class MarketDataCache:
    """
    Cache for market data to avoid redundant fetches.

    Stores (symbol, timeframe) -> data with TTL.
    """

    def __init__(self, ttl_seconds: int = 60):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time-to-live for cached data
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[tuple, Dict[str, Any]] = {}
        self._timestamps: Dict[tuple, float] = {}

    def get(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """
        Get cached data if fresh.

        Args:
            symbol: Trading pair
            timeframe: OHLCV timeframe

        Returns:
            Cached data or None if expired/missing
        """
        key = (symbol, timeframe)

        if key not in self._cache:
            return None

        # Check if expired
        age = time.time() - self._timestamps.get(key, 0)
        if age > self.ttl_seconds:
            # Expired - remove from cache
            del self._cache[key]
            del self._timestamps[key]
            return None

        return self._cache[key]

    def set(self, symbol: str, timeframe: str, data: Dict[str, Any]):
        """
        Cache data.

        Args:
            symbol: Trading pair
            timeframe: OHLCV timeframe
            data: Data to cache
        """
        key = (symbol, timeframe)
        self._cache[key] = data
        self._timestamps[key] = time.time()

    def clear(self):
        """Clear all cached data."""
        self._cache.clear()
        self._timestamps.clear()

    def size(self) -> int:
        """Get number of cached items."""
        return len(self._cache)
