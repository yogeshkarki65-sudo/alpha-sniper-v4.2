"""
Universe Selection Module for Alpha Sniper v4.2

Selects trading universe by 24h liquidity (quote volume).
Filters and sorts symbols to keep only the most liquid pairs.
"""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _is_tradable_symbol(sym: str, markets: Dict[str, Any]) -> bool:
    """
    Check if symbol is tradable based on exchange market metadata.

    Filters out:
    - Non-existent markets
    - Inactive or non-spot markets
    - Stock tokens (e.g., NVDAON/USDT)
    - Leveraged ETFs (3L, 3S, 5L, 5S)
    - Directional tokens (UP, DOWN)

    Args:
        sym: Symbol to check
        markets: Exchange markets dict

    Returns:
        True if symbol is tradable, False otherwise
    """
    m = markets.get(sym)
    if not m:
        return False

    # Reject inactive or non-spot markets
    if not m.get("active", True):
        return False
    if not m.get("spot", True):
        return False
    if m.get("type") not in (None, "spot"):
        return False

    # Regex guardrails for MEXC stock tokens, ETFs, and junk
    bad_patterns = [
        r".*ON/USDT$",        # tokenized stocks: NVDAON/USDT, etc.
        r".*3L/USDT$", r".*3S/USDT$",
        r".*5L/USDT$", r".*5S/USDT$",
        r".*UP/USDT$", r".*DOWN/USDT$",
    ]
    for pat in bad_patterns:
        if re.match(pat, sym):
            return False

    return True


def _apply_exclusions(symbols: List[str], settings) -> List[str]:
    """
    Apply universe quality filters: exclude stable/pegged pairs and user-defined patterns.

    Args:
        symbols: List of symbols to filter
        settings: Settings object with UNIVERSE_EXCLUDE_BASES and UNIVERSE_EXCLUDE_SYMBOL_PATTERNS

    Returns:
        Filtered list of symbols
    """
    bases = []
    patterns: List[re.Pattern] = []

    # Parse excluded base currencies (e.g., "USDC,USDT,FDUSD")
    if getattr(settings, 'UNIVERSE_EXCLUDE_BASES', None):
        bases = [b.strip().upper() for b in settings.UNIVERSE_EXCLUDE_BASES.split(',') if b.strip()]

    # Parse excluded symbol patterns (e.g., "^USDC/USDT$,^PAXG/USDT$")
    if getattr(settings, 'UNIVERSE_EXCLUDE_SYMBOL_PATTERNS', None):
        for raw in settings.UNIVERSE_EXCLUDE_SYMBOL_PATTERNS.split(','):
            raw = raw.strip()
            if not raw:
                continue
            try:
                patterns.append(re.compile(raw))
            except re.error:
                logger.warning(f"Invalid regex pattern: {raw}")
                continue

    # Apply filters
    out = []
    for sym in symbols:
        base, _, quote = sym.partition('/')

        # Exclude if base currency is in exclusion list
        if base.upper() in bases:
            continue

        # Exclude if symbol matches any exclusion pattern
        if any(p.search(sym) for p in patterns):
            continue

        out.append(sym)

    if len(out) != len(symbols):
        logger.info(
            f"Universe exclusions: {len(symbols)} → {len(out)} symbols | "
            f"excluded_bases={bases[:3]}{'...' if len(bases) > 3 else ''} | "
            f"patterns={len(patterns)}"
        )

    return out


async def select_top_liquid_symbols(
    exchange,
    base_quote: str = "USDT",
    max_symbols: int = 80,
    min_quote_volume: float = 50000.0,
    settings=None,
) -> List[str]:
    """
    Select top N most liquid symbols by 24h quote volume.

    Args:
        exchange: AsyncExchange instance
        base_quote: Quote currency to filter (e.g., 'USDT')
        max_symbols: Maximum number of symbols to return
        min_quote_volume: Minimum 24h quote volume threshold
        settings: Optional settings object for exclusion filters

    Returns:
        List of symbol strings sorted by liquidity (most liquid first)
    """
    try:
        # Fetch all tickers from exchange
        logger.info(f"Fetching tickers for universe selection...")
        tickers = await exchange.fetch_tickers()

        if not tickers:
            logger.error("No tickers received from exchange")
            return []

        # Get markets for tradability filtering
        markets = exchange.markets or {}

        # Filter and collect candidates
        candidates = []
        filtered_count = 0

        for symbol, ticker in tickers.items():
            # Filter by quote currency
            if not symbol.endswith(f"/{base_quote}"):
                continue

            # Filter non-tradable symbols (stock tokens, leveraged ETFs, inactive)
            if not _is_tradable_symbol(symbol, markets):
                filtered_count += 1
                continue

            # Get 24h quote volume
            quote_volume = ticker.get("quoteVolume", 0) or 0

            # Skip if below minimum threshold
            if quote_volume < min_quote_volume:
                continue

            # Get last price (for additional validation)
            last_price = ticker.get("last", 0) or ticker.get("close", 0) or 0

            if last_price <= 0:
                continue  # Invalid price

            candidates.append({
                "symbol": symbol,
                "quote_volume": quote_volume,
                "last_price": last_price,
            })

        if filtered_count > 0:
            logger.info(f"Universe tradability filter: removed {filtered_count} non-tradable symbols")

        # Sort by quote volume descending
        candidates.sort(key=lambda x: x["quote_volume"], reverse=True)

        # Collect all symbols before exclusions
        selected_symbols = [c["symbol"] for c in candidates]

        # Apply exclusions if settings provided
        if settings is not None:
            selected_symbols = _apply_exclusions(selected_symbols, settings)

        # Take top N after exclusions
        selected_symbols = selected_symbols[:max_symbols]
        selected = [c for c in candidates if c["symbol"] in selected_symbols]

        # Log selection summary
        if selected:
            top = selected[0]
            bottom = selected[-1]
            logger.info(
                f"Universe selected: {len(selected_symbols)} symbols | "
                f"base_quote={base_quote} | max={max_symbols} | "
                f"top={top['symbol']} (${top['quote_volume']:,.0f}) | "
                f"cutoff={bottom['symbol']} (${bottom['quote_volume']:,.0f})"
            )
        else:
            logger.warning(
                f"No symbols selected | base_quote={base_quote} | "
                f"min_volume=${min_quote_volume:,.0f}"
            )

        return selected_symbols

    except Exception as e:
        logger.error(f"Error selecting universe: {e}")
        return []


async def select_top_liquid_symbols_with_cache(
    exchange,
    base_quote: str = "USDT",
    max_symbols: int = 80,
    min_quote_volume: float = 50000.0,
    cache: Optional[Dict] = None,
    settings=None,
) -> List[str]:
    """
    Select top liquid symbols with optional caching.

    Cache structure: {
        'symbols': [...],
        'timestamp': float,
        'cutoff_volume': float,
    }

    Args:
        exchange: AsyncExchange instance
        base_quote: Quote currency
        max_symbols: Max symbols
        min_quote_volume: Min 24h quote volume
        cache: Optional dict to check/update
        settings: Optional settings object for exclusion filters

    Returns:
        List of symbols
    """
    import time

    # Check cache freshness (5 minute TTL)
    if cache is not None:
        cache_age = time.time() - cache.get("timestamp", 0)
        if cache_age < 300 and cache.get("symbols"):
            logger.info(
                f"Using cached universe: {len(cache['symbols'])} symbols | "
                f"age={cache_age:.0f}s"
            )
            return cache["symbols"]

    # Fetch fresh universe
    symbols = await select_top_liquid_symbols(
        exchange, base_quote, max_symbols, min_quote_volume, settings
    )

    # Update cache
    if cache is not None:
        cache["symbols"] = symbols
        cache["timestamp"] = time.time()
        cache["base_quote"] = base_quote
        cache["max_symbols"] = max_symbols

    return symbols


def filter_symbols_by_pattern(
    symbols: List[str],
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> List[str]:
    """
    Filter symbols by include/exclude patterns.

    Args:
        symbols: List of symbols
        include_patterns: Patterns to include (e.g., ['BTC', 'ETH'])
        exclude_patterns: Patterns to exclude (e.g., ['BEAR', 'BULL', 'UP', 'DOWN'])

    Returns:
        Filtered symbol list
    """
    filtered = symbols.copy()

    # Apply include patterns
    if include_patterns:
        filtered = [
            s for s in filtered
            if any(pattern in s for pattern in include_patterns)
        ]

    # Apply exclude patterns
    if exclude_patterns:
        filtered = [
            s for s in filtered
            if not any(pattern in s for pattern in exclude_patterns)
        ]

    if len(filtered) != len(symbols):
        logger.info(
            f"Symbol filtering: {len(symbols)} → {len(filtered)} symbols | "
            f"include={include_patterns} | exclude={exclude_patterns}"
        )

    return filtered


# Default exclude patterns (leveraged tokens, etc.)
DEFAULT_EXCLUDE_PATTERNS = [
    "BEAR", "BULL", "UP", "DOWN", "LEVERAGE",
    "3L", "3S", "5L", "5S",
]
