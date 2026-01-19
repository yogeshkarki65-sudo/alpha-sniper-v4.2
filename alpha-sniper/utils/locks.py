"""
Per-symbol locks for serialized order execution.

Prevents double-entry on the same symbol by ensuring
only one order operation can execute at a time per symbol.
"""
from collections import defaultdict
import asyncio

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def symbol_lock(symbol: str) -> asyncio.Lock:
    """
    Get an asyncio.Lock for a specific symbol.

    Args:
        symbol: Trading symbol (e.g., "BTC/USDT")

    Returns:
        asyncio.Lock for the symbol

    Usage:
        async with symbol_lock("BTC/USDT"):
            # Only one order operation at a time for BTC/USDT
            order = await exchange.create_order(...)
    """
    return _locks[symbol]
