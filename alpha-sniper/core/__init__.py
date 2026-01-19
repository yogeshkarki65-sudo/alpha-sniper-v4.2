"""
Core async infrastructure for Alpha Sniper v4.2

Provides non-blocking I/O for exchange, database, and external services.
"""

from .exchange_async import AsyncExchange, create_async_exchange

__all__ = ["AsyncExchange", "create_async_exchange"]
