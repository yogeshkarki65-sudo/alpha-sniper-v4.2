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
