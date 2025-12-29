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
        **opts: Any,
    ):
        """
        Initialize async exchange client.

        Args:
            exchange_id: Exchange name (e.g., 'mexc', 'binance')
            api_key: API key (optional for public endpoints)
            secret: API secret
            testnet: Use testnet/sandbox mode
            **opts: Additional CCXT options
        """
        self.exchange_id = exchange_id

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

        logger.info(
            f"AsyncExchange initialized: {exchange_id} | "
            f"rateLimit={self.client.rateLimit}ms | testnet={testnet}"
        )

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
            round(amount, prec.get('amount', 8))
            if prec.get('amount') is not None
            else amount
        )
        prc = (
            round(price, prec.get('price', 8))
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

        Args:
            symbol: Trading pair
            size_usd: Order size in USD
            price: Entry price

        Returns:
            (is_valid, reason, details_dict)
        """
        m = self.market(symbol)
        amount = size_usd / max(price, 1e-12)
        amount, price = self.quantize_amount_price(symbol, amount, price)

        limits = m.get('limits', {})
        min_notional = (limits.get('cost') or {}).get('min')
        min_amount = (limits.get('amount') or {}).get('min')

        if min_amount and amount < min_amount:
            return (
                False,
                f"amount<{min_amount}",
                {"amount": amount, "price": price, "symbol": symbol},
            )

        if min_notional and amount * price < min_notional:
            return (
                False,
                f"notional<{min_notional}",
                {"amount": amount, "price": price, "symbol": symbol, "notional": amount * price},
            )

        return True, "OK", {"amount": amount, "price": price, "symbol": symbol}

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
            Dict with spread_pct and depth_usd
        """
        ob = await self.fetch_order_book(symbol, limit=max_levels)
        bids = ob.get('bids') or []
        asks = ob.get('asks') or []

        if not bids or not asks:
            return {"spread_pct": 999.0, "depth_usd": 0.0}

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

        return {"spread_pct": spread_pct, "depth_usd": depth_usd}

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
    **opts: Any,
) -> AsyncExchange:
    """
    Factory function to create an AsyncExchange instance.

    Args:
        exchange_id: Exchange name
        api_key: API key
        secret: API secret
        testnet: Use sandbox mode
        **opts: Additional CCXT options

    Returns:
        AsyncExchange instance
    """
    return AsyncExchange(
        exchange_id=exchange_id,
        api_key=api_key,
        secret=secret,
        testnet=testnet,
        **opts,
    )
