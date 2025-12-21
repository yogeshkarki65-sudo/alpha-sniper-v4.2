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

        # Pre-flight validation
        if not self._validate_inputs(symbol, amount):
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

    def _validate_inputs(self, symbol: str, amount: float) -> bool:
        """Validate order inputs."""
        if not symbol or not isinstance(symbol, str):
            return False
        if amount <= 0 or not isinstance(amount, (int, float)):
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
