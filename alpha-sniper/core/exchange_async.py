"""
Async Exchange Wrapper for Alpha Sniper v4.2

Uses ccxt.async_support to provide non-blocking exchange operations with:
- Built-in rate limiting via CCXT
- Automatic retry with exponential backoff for transient errors
- Graceful fallback for any sync operations via asyncio.to_thread
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from math import floor
from typing import Any, Dict, List, Optional

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

try:
    import ccxt.async_support as ccxt
except ImportError:
    raise ImportError(
        "ccxt.async_support not available. Install with: pip install ccxt>=4.0"
    )

logger = logging.getLogger(__name__)

# Retryable exceptions (transient network/server errors)
RETRYABLE_EXCEPTIONS = (
    ccxt.NetworkError,
    ccxt.ExchangeNotAvailable,
    ccxt.RequestTimeout,
    ccxt.DDoSProtection,
)


class AsyncExchange:
    """
    Async wrapper around CCXT exchange with retry logic and rate limiting.

    All methods are async and respect exchange rate limits automatically.
    Transient errors (network, timeouts, 429) are retried with exponential backoff.
    """

    def __init__(
        self,
        exchange_id: str = "mexc",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        testnet: bool = False,
        settings: Optional[Any] = None,
        **opts: Any,
    ):
        """
        Initialize async exchange client.

        Args:
            exchange_id: Exchange name (e.g., 'mexc', 'binance')
            api_key: API key (optional for public endpoints)
            secret: API secret
            testnet: Use testnet/sandbox mode
            settings: Optional settings object for auto-bump and other features
            **opts: Additional CCXT options
        """
        self.exchange_id = exchange_id
        self.settings = settings

        try:
            exchange_class = getattr(ccxt, exchange_id)
        except AttributeError:
            raise ValueError(f"Exchange '{exchange_id}' not found in CCXT")

        config = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,  # Built-in rate limiting
            "timeout": 30000,  # 30s timeout
            **opts,
        }

        if testnet:
            config["sandbox"] = True

        self.client: ccxt.Exchange = exchange_class(config)
        self._markets_loaded = False
        self._markets_cache: Dict[str, Any] = {}
        self._balance_cache: Dict[str, Any] = {}
        self._balance_cache_time: float = 0.0
        self._balance_cache_ttl: float = 10.0  # 10 second cache

        logger.info(
            f"AsyncExchange initialized: {exchange_id} | "
            f"rateLimit={self.client.rateLimit}ms | testnet={testnet}"
        )

    @property
    def markets(self) -> Dict[str, Any]:
        """Get cached markets dict."""
        return self._markets_cache

    async def _retry(self, coro_factory, operation_name: str = "exchange_op"):
        """
        Execute an async operation with retry logic for transient errors.

        Args:
            coro_factory: Callable that returns a coroutine
            operation_name: Name for logging

        Returns:
            Result from the coroutine

        Raises:
            RetryError: If all retries exhausted
            Exception: Non-retryable exceptions are re-raised immediately
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=0.5, max=8.0, jitter=2.0),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                try:
                    result = await coro_factory()
                    if attempt.retry_state.attempt_number > 1:
                        logger.info(
                            f"[{operation_name}] Succeeded after "
                            f"{attempt.retry_state.attempt_number} attempts"
                        )
                    return result
                except RETRYABLE_EXCEPTIONS as e:
                    logger.warning(
                        f"[{operation_name}] Retry {attempt.retry_state.attempt_number}/5 "
                        f"after {type(e).__name__}: {e}"
                    )
                    raise  # Let tenacity handle retry
                except Exception as e:
                    # Non-retryable error - log and re-raise immediately
                    logger.error(
                        f"[{operation_name}] Non-retryable error: {type(e).__name__}: {e}"
                    )
                    raise

    async def load_markets(self, reload: bool = False) -> Dict[str, Any]:
        """
        Load market metadata from exchange.

        Results are cached after first load unless reload=True.

        Args:
            reload: Force reload from exchange

        Returns:
            Dict of market metadata keyed by symbol
        """
        if self._markets_loaded and not reload:
            return self._markets_cache

        result = await self._retry(
            lambda: self.client.load_markets(reload=reload),
            "load_markets",
        )

        self._markets_cache = result
        self._markets_loaded = True

        logger.info(f"Markets loaded: {len(result)} symbols")
        return result

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch ticker data for a symbol.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')

        Returns:
            Ticker dict with bid, ask, last, volume, etc.
        """
        return await self._retry(
            lambda: self.client.fetch_ticker(symbol),
            f"fetch_ticker({symbol})",
        )

    async def fetch_tickers(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fetch tickers for multiple symbols (or all).

        Args:
            symbols: List of symbols (None = all)

        Returns:
            Dict of tickers keyed by symbol
        """
        return await self._retry(
            lambda: self.client.fetch_tickers(symbols),
            "fetch_tickers",
        )

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        since: Optional[int] = None,
        limit: int = 500,
    ) -> List[List]:
        """
        Fetch OHLCV candlestick data.

        Args:
            symbol: Trading pair
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, etc.)
            since: Start timestamp in ms (None = recent)
            limit: Max number of candles

        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        return await self._retry(
            lambda: self.client.fetch_ohlcv(symbol, timeframe, since, limit),
            f"fetch_ohlcv({symbol}, {timeframe}, limit={limit})",
        )

    async def fetch_order_book(
        self, symbol: str, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch order book (bids/asks).

        Args:
            symbol: Trading pair
            limit: Depth limit (None = exchange default)

        Returns:
            Dict with 'bids' and 'asks' arrays
        """
        return await self._retry(
            lambda: self.client.fetch_order_book(symbol, limit),
            f"fetch_order_book({symbol})",
        )

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance.

        Requires API key/secret.

        Returns:
            Balance dict with 'free', 'used', 'total' per currency
        """
        return await self._retry(
            lambda: self.client.fetch_balance(),
            "fetch_balance",
        )

    async def fetch_balance_cached(self) -> Dict[str, Any]:
        """
        Fetch balance with TTL cache to reduce API calls.

        Returns cached balance if fresher than TTL, otherwise fetches new.

        Returns:
            Balance dict with 'free', 'used', 'total' per currency
        """
        now = time.time()
        if now - self._balance_cache_time < self._balance_cache_ttl:
            return self._balance_cache

        self._balance_cache = await self.fetch_balance()
        self._balance_cache_time = now
        return self._balance_cache

    async def _get_free_usdt(self) -> float:
        """
        Get free USDT balance with caching.

        Returns:
            Free USDT balance
        """
        try:
            bal = await self.fetch_balance_cached()
            free = bal.get("free", {}) or bal.get("total", {})
            return float(free.get("USDT", 0.0))
        except Exception:
            return 0.0

    def _get_symbol_limits(self, symbol: str) -> tuple[float, float, Any, Any]:
        """
        Get exchange limits and precision for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            (min_cost, min_amt, amt_prec, price_prec)
        """
        m = self.markets.get(symbol)
        if not m:
            # Try to load markets if not loaded
            if not self._markets_loaded:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self.load_markets())
                except Exception:
                    pass
            m = self.markets.get(symbol, {})

        limits = m.get("limits", {}) or {}
        prec = m.get("precision", {}) or {}
        min_cost = (limits.get("cost") or {}).get("min") or 0.0
        min_amt = (limits.get("amount") or {}).get("min") or 0.0
        amt_prec = prec.get("amount")
        price_prec = prec.get("price")
        return float(min_cost), float(min_amt), amt_prec, price_prec

    def _autobump_size_usd(
        self,
        symbol: str,
        price: float,
        requested_usd: float,
        free_usdt: float,
    ) -> tuple[float, str]:
        """
        Auto-bump order size to meet exchange minimums with safety caps.

        Args:
            symbol: Trading pair
            price: Entry price
            requested_usd: Risk-based order size in USD
            free_usdt: Available USDT balance

        Returns:
            (final_usd, action_str) where action is one of:
            - "disabled": Auto-bump is disabled
            - "no_price": Price is zero or invalid
            - "ok": Already meets minimums
            - "no_balance": Insufficient balance
            - "cap": Would exceed safety caps
            - "bumped": Successfully bumped to meet minimums
        """
        # Check if auto-bump is enabled
        if not self.settings or not getattr(self.settings, "AUTO_BUMP_ENABLE", True):
            return requested_usd, "disabled"

        price = float(price or 0.0)
        if price <= 0:
            return requested_usd, "no_price"

        # Get exchange limits
        min_cost, min_amt, _, _ = self._get_symbol_limits(symbol)
        head = 1.0 + float(getattr(self.settings, "AUTO_BUMP_HEADROOM_PCT", 0.02))
        need_usd = requested_usd

        # Calculate required size based on minimums
        if min_cost and min_cost > 0:
            need_usd = max(need_usd, float(min_cost) * head)
        if min_amt and min_amt > 0:
            need_usd = max(need_usd, float(min_amt) * price * head)

        # Apply safety caps
        cap_by_mult = requested_usd * float(getattr(self.settings, "AUTO_BUMP_MAX_MULT", 2.5))
        cap_by_abs = float(getattr(self.settings, "AUTO_BUMP_MAX_ABS_USD", 100.0))
        cap_by_bal = max(0.0, float(free_usdt) * 0.98)

        cap = min(cap_by_mult, cap_by_abs, cap_by_bal)

        if need_usd <= requested_usd:
            return requested_usd, "ok"  # Already meets minimums
        if cap <= 0:
            return requested_usd, "no_balance"
        if need_usd > cap:
            return requested_usd, "cap"  # Would exceed caps

        return need_usd, "bumped"

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Create an order (market/limit).

        Args:
            symbol: Trading pair
            order_type: 'market' or 'limit'
            side: 'buy' or 'sell'
            amount: Order quantity
            price: Limit price (required for limit orders)
            params: Additional exchange-specific params

        Returns:
            Order dict with id, status, filled, etc.
        """
        return await self._retry(
            lambda: self.client.create_order(
                symbol, order_type, side, amount, price, params or {}
            ),
            f"create_order({symbol}, {side}, {amount})",
        )

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Cancel an open order.

        Args:
            order_id: Order ID from create_order
            symbol: Trading pair

        Returns:
            Canceled order info
        """
        return await self._retry(
            lambda: self.client.cancel_order(order_id, symbol),
            f"cancel_order({order_id}, {symbol})",
        )

    async def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        Fetch order status.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            Order dict with current status
        """
        return await self._retry(
            lambda: self.client.fetch_order(order_id, symbol),
            f"fetch_order({order_id}, {symbol})",
        )

    async def fetch_open_orders(
        self, symbol: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all open orders (optionally filtered by symbol).

        Args:
            symbol: Trading pair (None = all pairs)

        Returns:
            List of open orders
        """
        return await self._retry(
            lambda: self.client.fetch_open_orders(symbol),
            f"fetch_open_orders({symbol or 'all'})",
        )

    async def fetch_orders(
        self,
        symbol: Optional[str] = None,
        since: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch order history.

        Args:
            symbol: Trading pair (None = all pairs)
            since: Start timestamp in ms
            limit: Max number of orders

        Returns:
            List of orders
        """
        return await self._retry(
            lambda: self.client.fetch_orders(symbol, since, limit),
            f"fetch_orders({symbol or 'all'})",
        )

    def market(self, symbol: str) -> Dict[str, Any]:
        """
        Get market metadata for a symbol (synchronous).

        Args:
            symbol: Trading pair

        Returns:
            Market dict with limits, precision, etc.
        """
        return self.client.market(symbol)

    def quantize_amount_price(
        self, symbol: str, amount: float, price: float
    ) -> tuple[float, float]:
        """
        Quantize amount and price to exchange precision limits.

        Args:
            symbol: Trading pair
            amount: Order quantity
            price: Order price

        Returns:
            (quantized_amount, quantized_price)
        """
        m = self.market(symbol)
        prec = m.get('precision', {})

        # Round to exchange precision
        amt = (
            round(amount, int(prec.get('amount', 8)))
            if prec.get('amount') is not None
            else amount
        )
        prc = (
            round(price, int(prec.get('price', 8)))
            if prec.get('price') is not None
            else price
        )

        # Enforce minimum amounts if present
        limits = m.get('limits', {})
        amt_min = (limits.get('amount') or {}).get('min')
        if amt_min and amt < amt_min:
            amt = amt_min

        return amt, prc

    async def validate_order(
        self, symbol: str, size_usd: float, price: float
    ) -> tuple[bool, str, Dict[str, Any]]:
        """
        Validate order against exchange limits before submission.

        Hardened validation includes:
        - Market type checks (active, spot-only)
        - Symbol pattern filters (stock tokens, leveraged ETFs)
        - Correct notional calculation in quote terms
        - Balance checks against free quote currency
        - Precision rounding with floor logic

        Args:
            symbol: Trading pair
            size_usd: Order size in USD
            price: Entry price

        Returns:
            (is_valid, reason, details_dict)
            If valid, details contains validated 'px' and 'qty' to use in order
        """
        # --- Market metadata validation ---
        m = self.markets.get(symbol)
        if not m:
            return False, "no_market", {"symbol": symbol}

        # Reject anything not plain spot or inactive
        if not m.get("active", True) or not m.get("spot", True) or m.get("type") not in (None, "spot"):
            return False, "unsupported_market_type", {
                "type": m.get("type"),
                "spot": m.get("spot"),
                "active": m.get("active")
            }

        # Regex guardrails for MEXC stock tokens, ETFs, and junk
        bad_patterns = [
            r".*ON/USDT$",        # tokenized stocks: NVDAON/USDT, etc.
            r".*3L/USDT$", r".*3S/USDT$",
            r".*5L/USDT$", r".*5S/USDT$",
            r".*UP/USDT$", r".*DOWN/USDT$",
        ]
        for pat in bad_patterns:
            if re.match(pat, symbol):
                return False, "unsupported_symbol_pattern", {"pattern": pat}

        # --- Get raw values and limits ---
        px_raw = float(price)
        qty_raw = float(size_usd) / max(px_raw, 1e-12)
        notional_raw = px_raw * qty_raw

        limits = m.get("limits") or {}
        min_cost = limits.get("cost", {}).get("min")
        min_amt = limits.get("amount", {}).get("min")

        # Fallbacks for min_cost and min_amt
        if min_cost is None:
            min_cost = 1.0
        if min_amt is None:
            prec_amt = m.get("precision", {}).get("amount")
            if isinstance(prec_amt, (int, float)):
                # If precision=0 => step=1 (whole units); else use 10^-precision
                min_amt = 1.0 if int(prec_amt or 0) == 0 else 10 ** (-int(prec_amt))
            else:
                min_amt = 0.0

        # --- Use ccxt's precision helpers ---
        try:
            px_str = self.client.price_to_precision(symbol, px_raw)
            qty_str = self.client.amount_to_precision(symbol, qty_raw)
            px = float(px_str)
            qty = float(qty_str)
        except Exception as e:
            return False, "precision_error", {"err": str(e)}

        # --- Check for zero/underflow after precision ---
        if qty <= 0:
            return False, "amount<min_amount", {
                "qty": qty_raw,
                "min_amount": float(min_amt),
                "symbol": symbol
            }

        # --- Notional calculation in quote terms ---
        notional = px * qty

        if notional < float(min_cost):
            return False, "notional<min_cost", {
                "notional": notional,
                "min_cost": float(min_cost),
                "px": px,
                "qty": qty,
                "symbol": symbol
            }

        # --- Balance check (quote currency) ---
        try:
            bal = await self.fetch_balance_cached()
            free_quote = float(bal.get("free", {}).get("USDT", 0.0))
            if notional > free_quote * 0.98:  # leave 2% headroom
                return False, "insufficient_quote_balance", {
                    "notional": notional,
                    "free": free_quote
                }
        except Exception as e:
            # Don't block order if balance fetch fails - log and continue
            logger.warning(f"validate_order: balance check failed: {e}")

        # Pass rounded values back via details so caller uses them
        return True, "ok", {
            "px": px,
            "qty": qty,
            "notional": notional,
            "min_cost": float(min_cost),
            "min_amount": float(min_amt),
            "symbol": symbol
        }

    async def get_liquidity_metrics(
        self, symbol: str, required_usd: float, max_levels: int = 20
    ) -> Dict[str, Any]:
        """
        Calculate liquidity metrics from order book.

        Args:
            symbol: Trading pair
            required_usd: Required order size in USD
            max_levels: Order book depth to fetch

        Returns:
            Dict with spread_pct, depth_usd, best_bid, best_ask
        """
        ob = await self.fetch_order_book(symbol, limit=max_levels)
        bids = ob.get('bids') or []
        asks = ob.get('asks') or []

        if not bids or not asks:
            return {"spread_pct": 999.0, "depth_usd": 0.0, "best_bid": 0.0, "best_ask": 0.0}

        best_bid, best_ask = bids[0][0], asks[0][0]
        mid = (best_bid + best_ask) / 2.0
        spread_pct = (best_ask - best_bid) / mid * 100.0

        # Calculate depth on the taking side (buying consumes asks)
        needed = required_usd
        depth_usd = 0.0

        for p, q in asks:
            take = min(needed, p * q)
            depth_usd += take
            needed -= take
            if needed <= 0:
                break

        return {
            "spread_pct": spread_pct,
            "depth_usd": depth_usd,
            "best_bid": best_bid,
            "best_ask": best_ask,
        }

    async def create_order_idempotent(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        client_oid: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an order with idempotency via clientOrderId.

        Automatically bumps order size to meet exchange minimums (if enabled).
        If order creation fails, attempts to find the order by clientOrderId
        to prevent duplicate submissions.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            amount: Order quantity
            price: Limit price (required for limit orders)
            client_oid: Client-side order ID for idempotency
            params: Additional exchange-specific params

        Returns:
            Order dict with id, status, filled, etc.
        """
        params = dict(params or {})

        if client_oid:
            # Common key for idempotency; may fall back into info for some venues
            params.setdefault('clientOrderId', client_oid)

        # Auto-bump logic (if enabled and we have price)
        if price is not None and price > 0:
            requested_usd = float(amount) * float(price)
            free_usdt = await self._get_free_usdt()
            final_usd, action = self._autobump_size_usd(symbol, price, requested_usd, free_usdt)

            if action == "bumped":
                # Recalculate amount with bumped size
                amount = final_usd / float(price)
                logger.info(
                    f"[AUTO_BUMP] {symbol} size ${requested_usd:.2f} → ${final_usd:.2f} (reason={action})"
                )
            elif action in ("cap", "no_balance"):
                logger.info(
                    f"[AUTO_BUMP] {symbol} size ${requested_usd:.2f} not bumped (reason={action})"
                )

        # Apply precision rounding using ccxt helpers
        try:
            if price is not None:
                price_str = self.client.price_to_precision(symbol, price)
                price = float(price_str)
            amount_str = self.client.amount_to_precision(symbol, amount)
            amount = float(amount_str)

            # Check if amount rounded to zero
            if amount <= 0.0:
                # Try to set to minimum amount if available
                min_cost, min_amt, _, _ = self._get_symbol_limits(symbol)
                if min_amt and min_amt > 0:
                    amount_str = self.client.amount_to_precision(symbol, min_amt)
                    amount = float(amount_str)
                if amount <= 0.0:
                    raise ValueError(f"Amount rounded to zero for {symbol} (precision issue)")
        except Exception as e:
            logger.error(f"[AUTO_BUMP] Precision error for {symbol}: {e}")
            # Continue with original values

        try:
            if order_type == 'market':
                return await self._retry(
                    lambda: self.client.create_order(
                        symbol, order_type, side, amount, None, params
                    ),
                    f"create_order_idempotent({symbol}, {side}, {amount})",
                )
            else:
                return await self._retry(
                    lambda: self.client.create_order(
                        symbol, order_type, side, amount, price, params
                    ),
                    f"create_order_idempotent({symbol}, {side}, {amount})",
                )
        except Exception as e:
            # Best-effort: try to find by client OID if exchange supports it
            if client_oid:
                try:
                    orders = await self.fetch_orders(symbol)
                    for o in orders or []:
                        info = o.get('info') or {}
                        if (o.get('clientOrderId') == client_oid) or (
                            info.get('clientOrderId') == client_oid
                        ):
                            logger.warning(
                                f"Order with clientOrderId={client_oid} already exists, returning existing order"
                            )
                            return o
                except Exception as lookup_error:
                    logger.warning(
                        f"Failed to lookup existing order by clientOrderId: {lookup_error}"
                    )
            # Re-raise original exception if we couldn't find the order
            raise e

    async def create_aggressive_limit_ioc(
        self,
        symbol: str,
        side: str,
        size_usd: float,
        max_slip_pct: float,
        client_oid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Place a limit order with IOC (Immediate-Or-Cancel) to reduce slippage.

        Places limit order slightly beyond best price with max slippage tolerance.
        Falls back to market order if IOC is unsupported or rejected.

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            size_usd: Desired notional in quote currency
            max_slip_pct: Max slippage tolerance (e.g., 0.0015 = 0.15%)
            client_oid: Client order ID for idempotency

        Returns:
            Order dict
        """
        try:
            # Fetch order book
            ob = await self.fetch_order_book(symbol, limit=5)
            bids = ob.get('bids') or []
            asks = ob.get('asks') or []

            # Fallback to market if book is empty
            if not bids or not asks:
                amt = (
                    size_usd / (asks[0][0] if side == 'buy' and asks else bids[0][0])
                    if (bids or asks)
                    else size_usd
                )
                return await self.create_order_idempotent(
                    symbol, side, 'market', amt, client_oid=client_oid
                )

            best_bid, best_ask = bids[0][0], asks[0][0]

            # Set limit price with slippage tolerance
            if side == 'buy':
                px = best_ask * (1 + max_slip_pct)
            else:
                px = best_bid * (1 - max_slip_pct)

            # Calculate amount
            amount = size_usd / max(px, 1e-12)

            # Quantize to exchange precision
            amount, px = self.quantize_amount_price(symbol, amount, px)

            # Place limit IOC order
            params = {'timeInForce': 'IOC'}
            try:
                return await self.create_order_idempotent(
                    symbol, side, 'limit', amount, price=px,
                    client_oid=client_oid, params=params
                )
            except Exception:
                # Fallback to market if IOC unsupported or rejected
                logger.warning(
                    f"IOC order failed for {symbol}, falling back to market"
                )
                return await self.create_order_idempotent(
                    symbol, side, 'market', amount, client_oid=client_oid
                )

        except Exception as e:
            logger.error(f"Aggressive limit IOC failed for {symbol}: {e}")
            # Final fallback to market
            amt = size_usd / (asks[0][0] if side == 'buy' and asks and len(asks) > 0 else 1.0)
            return await self.create_order_idempotent(
                symbol, side, 'market', amt, client_oid=client_oid
            )

    async def close(self):
        """
        Close exchange connection and cleanup resources.

        Call this on shutdown to release HTTP sessions properly.
        """
        try:
            await self.client.close()
            logger.info(f"AsyncExchange closed: {self.exchange_id}")
        except Exception as e:
            logger.error(f"Error closing exchange: {e}")

    def __repr__(self) -> str:
        return (
            f"AsyncExchange(id={self.exchange_id}, "
            f"markets_loaded={self._markets_loaded}, "
            f"rate_limit={self.client.rateLimit}ms)"
        )


# Convenience factory function
def create_async_exchange(
    exchange_id: str = "mexc",
    api_key: Optional[str] = None,
    secret: Optional[str] = None,
    testnet: bool = False,
    settings: Optional[Any] = None,
    **opts: Any,
) -> AsyncExchange:
    """
    Factory function to create an AsyncExchange instance.

    Args:
        exchange_id: Exchange name
        api_key: API key
        secret: API secret
        testnet: Use sandbox mode
        settings: Optional settings object for auto-bump
        **opts: Additional CCXT options

    Returns:
        AsyncExchange instance
    """
    return AsyncExchange(
        exchange_id=exchange_id,
        api_key=api_key,
        secret=secret,
        testnet=testnet,
        settings=settings,
        **opts,
    )
