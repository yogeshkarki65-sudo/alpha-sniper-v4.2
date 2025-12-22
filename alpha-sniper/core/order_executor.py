"""
Robust order execution wrapper with validation, retries, and quarantine.
"""

import time
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderFailureReason(Enum):
    """Structured failure reasons for debugging."""
    API_RETURNED_NONE = "api_returned_none"
    INVALID_RESPONSE_TYPE = "invalid_response_type"
    NONE_TYPE_ITERATION = "none_type_iteration"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INVALID_ORDER_SIZE = "invalid_order_size"
    EXCHANGE_ERROR = "exchange_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class OrderExecutor:
    """
    Centralized order execution with:
    - Input validation
    - Response validation
    - Retry logic
    - Quarantine integration
    """

    def __init__(self, exchange, quarantine_manager, logger):
        self.exchange = exchange
        self.quarantine = quarantine_manager
        self.logger = logger

        # Retry config
        self.max_retries = 2
        self.initial_backoff = 1.0  # seconds

        # Cache market limits for validation
        self.market_limits_cache = {}  # {symbol: {minNotional, minAmount, precision}}

    def execute_order(
        self,
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None
    ) -> Tuple[Optional[Dict], Optional[OrderFailureReason]]:
        """
        Execute order with full validation and retry logic.

        Returns: (order_dict, failure_reason)
        - Success: (order_dict, None)
        - Failure: (None, failure_reason)
        """

        # Pre-flight validation (with price for notional check)
        if not self._validate_inputs(symbol, amount, price):
            return None, OrderFailureReason.INVALID_ORDER_SIZE

        # Check quarantine
        if self.quarantine.is_quarantined(symbol):
            self.logger.debug(f"[ORDER_SKIP] {symbol} is quarantined")
            return None, OrderFailureReason.EXCHANGE_ERROR

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = self.exchange.create_order_raw(
                    symbol, type, side, amount, price, params
                )

                # Validate response
                validated, reason = self._validate_response(result, symbol, side)

                if validated:
                    self.logger.info(
                        f"[ORDER_OK] {symbol} {side} {amount} | "
                        f"order_id={result.get('id')} | attempt={attempt+1}"
                    )
                    # Reset quarantine on success
                    self.quarantine.record_success(symbol)
                    return result, None
                else:
                    last_error = reason
                    self.logger.warning(
                        f"[ORDER_INVALID] {symbol} | reason={reason.value} | "
                        f"attempt={attempt+1}/{self.max_retries}"
                    )

            except TypeError as e:
                if "'NoneType' object is not iterable" in str(e):
                    last_error = OrderFailureReason.NONE_TYPE_ITERATION
                else:
                    last_error = OrderFailureReason.EXCHANGE_ERROR
                self.logger.error(
                    f"[ORDER_ERROR] {symbol} | {e} | attempt={attempt+1}"
                )

            except Exception as e:
                last_error = OrderFailureReason.UNKNOWN
                self.logger.error(
                    f"[ORDER_ERROR] {symbol} | {e} | attempt={attempt+1}"
                )

            # Backoff before retry
            if attempt < self.max_retries - 1:
                backoff = self.initial_backoff * (2 ** attempt)
                time.sleep(backoff)

        # All retries exhausted - record failure
        self.quarantine.record_failure(symbol, last_error or OrderFailureReason.UNKNOWN)

        self.logger.error(
            f"[ORDER_FAILED] {symbol} | reason={last_error.value if last_error else 'unknown'} | "
            f"retries_exhausted={self.max_retries}"
        )

        return None, last_error or OrderFailureReason.UNKNOWN

    def _get_market_limits(self, symbol: str) -> Dict[str, Any]:
        """Get market limits for symbol (cached)."""
        if symbol in self.market_limits_cache:
            return self.market_limits_cache[symbol]

        try:
            markets = self.exchange.get_markets()
            if markets and symbol in markets:
                market = markets[symbol]
                limits = {
                    'min_notional': market.get('limits', {}).get('cost', {}).get('min', 0) or 5.0,  # Default $5
                    'min_amount': market.get('limits', {}).get('amount', {}).get('min', 0) or 0.0001,
                    'precision_amount': market.get('precision', {}).get('amount', 8),
                    'precision_price': market.get('precision', {}).get('price', 8),
                }
                self.market_limits_cache[symbol] = limits
                return limits
        except Exception as e:
            self.logger.debug(f"[ORDER_LIMITS] Could not fetch limits for {symbol}: {e}")

        # Return conservative defaults
        return {
            'min_notional': 5.0,  # $5 minimum
            'min_amount': 0.0001,
            'precision_amount': 8,
            'precision_price': 8,
        }

    def _validate_inputs(self, symbol: str, amount: float, price: Optional[float] = None) -> bool:
        """Validate order inputs against exchange limits."""
        # Basic type checks
        if not symbol or not isinstance(symbol, str):
            self.logger.error(f"[ORDER_VALIDATE] Invalid symbol: {symbol}")
            return False

        if not isinstance(amount, (int, float)):
            self.logger.error(f"[ORDER_VALIDATE] Invalid amount type: {type(amount)}")
            return False

        # CRITICAL: Check for zero/negative amount
        if amount <= 0:
            self.logger.error(
                f"[ORDER_VALIDATE] REJECTED: {symbol} amount={amount} <= 0 | "
                f"This would cause 'Amount can not be less than zero' error from MEXC"
            )
            return False

        # Get market limits
        limits = self._get_market_limits(symbol)

        # Check minimum amount
        if amount < limits['min_amount']:
            self.logger.error(
                f"[ORDER_VALIDATE] REJECTED: {symbol} amount={amount} < min={limits['min_amount']}"
            )
            return False

        # Check minimum notional (amount * price)
        if price:
            notional = amount * price
            if notional < limits['min_notional']:
                self.logger.error(
                    f"[ORDER_VALIDATE] REJECTED: {symbol} notional=${notional:.2f} < min=${limits['min_notional']:.2f} | "
                    f"amount={amount}, price={price}"
                )
                return False

        return True

    def _validate_response(
        self, result: Any, symbol: str, side: str
    ) -> Tuple[bool, Optional[OrderFailureReason]]:
        """Validate exchange response."""

        if result is None:
            return False, OrderFailureReason.API_RETURNED_NONE

        if not isinstance(result, dict):
            return False, OrderFailureReason.INVALID_RESPONSE_TYPE

        if not result.get('id'):
            return False, OrderFailureReason.API_RETURNED_NONE

        return True, None
