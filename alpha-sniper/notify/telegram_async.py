"""
Async Telegram Notifier for Alpha Sniper v4.2

Non-blocking Telegram notifications with:
- Message queue to never block trading logic
- Exponential backoff retry with jitter
- Rate limiting compliance
- Graceful shutdown with queue draining
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)

try:
    from aiogram import Bot
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.exceptions import TelegramAPIError
except ImportError:
    raise ImportError(
        "aiogram not installed. Run: pip install aiogram>=3.0"
    )

logger = logging.getLogger(__name__)

RETRYABLE_ERRORS = (TelegramAPIError,)


class AsyncTelegram:
    """
    Async Telegram notification manager with message queue.

    Messages are queued and sent asynchronously with retry logic.
    Trading logic never blocks on Telegram operations.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        max_queue_size: int = 500,
        rate_limit_delay: float = 0.05,  # 50ms between messages
    ):
        """
        Initialize async Telegram client.

        Args:
            token: Telegram bot token
            chat_id: Target chat ID
            max_queue_size: Max queued messages (prevents memory issues)
            rate_limit_delay: Min delay between sends (seconds)
        """
        self.chat_id = chat_id
        self.rate_limit_delay = rate_limit_delay

        # Create bot with aiohttp session
        session = AiohttpSession()
        self.bot = Bot(token=token, session=session)

        # Message queue
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=max_queue_size)
        self._sender_task: Optional[asyncio.Task] = None
        self._closed = False

        logger.info(
            f"AsyncTelegram initialized | chat_id={chat_id} | "
            f"max_queue={max_queue_size} | rate_limit={rate_limit_delay}s"
        )

    async def start(self):
        """
        Start the background sender task.

        Call this before sending any messages.
        """
        if self._sender_task is not None:
            logger.warning("Telegram sender already started")
            return

        self._sender_task = asyncio.create_task(self._sender_loop())
        logger.info("Telegram sender task started")

    async def send(self, text: str, parse_mode: Optional[str] = None):
        """
        Queue a message for async sending.

        Args:
            text: Message text
            parse_mode: Parse mode ('HTML', 'Markdown', None)

        Raises:
            asyncio.QueueFull: If queue is full
        """
        if self._closed:
            logger.warning("Attempted to send message after close")
            return

        message = {"text": text, "parse_mode": parse_mode}

        try:
            # Try to queue without blocking
            self._queue.put_nowait(message)
            logger.debug(f"Message queued | queue_size={self._queue.qsize()}")
        except asyncio.QueueFull:
            logger.error(
                f"Telegram queue full ({self._queue.maxsize}), dropping message: {text[:100]}"
            )
            raise

    async def _sender_loop(self):
        """
        Background task that processes the message queue.

        Sends messages with retry logic and rate limiting.
        """
        logger.info("Telegram sender loop started")

        while True:
            # Get next message from queue
            message = await self._queue.get()

            if message is None:  # Shutdown sentinel
                self._queue.task_done()
                logger.info("Telegram sender loop shutting down")
                break

            # Send message with retry
            await self._send_with_retry(message)

            # Mark as done
            self._queue.task_done()

            # Rate limiting delay
            if self.rate_limit_delay > 0:
                await asyncio.sleep(self.rate_limit_delay)

        logger.info("Telegram sender loop exited")

    async def _send_with_retry(self, message: dict):
        """
        Send a single message with exponential backoff retry.

        Args:
            message: Dict with 'text' and 'parse_mode'
        """
        text = message["text"]
        parse_mode = message.get("parse_mode")

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_exponential_jitter(initial=0.5, max=30.0, jitter=5.0),
                retry=retry_if_exception_type(RETRYABLE_ERRORS),
                reraise=False,  # Don't crash on final failure
            ):
                with attempt:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode=parse_mode,
                    )

                    if attempt.retry_state.attempt_number > 1:
                        logger.info(
                            f"Telegram send succeeded after "
                            f"{attempt.retry_state.attempt_number} attempts"
                        )

                    return  # Success

        except Exception as e:
            # Final failure after all retries
            logger.error(
                f"Telegram send failed after retries: {type(e).__name__}: {e} | "
                f"message={text[:100]}"
            )

    async def close(self):
        """
        Gracefully close Telegram client.

        Drains message queue and closes HTTP session.
        """
        if self._closed:
            return

        self._closed = True

        logger.info("Closing Telegram client...")

        # Send shutdown sentinel
        if self._sender_task and not self._sender_task.done():
            await self._queue.put(None)

            # Wait for queue to drain
            logger.info(f"Draining Telegram queue ({self._queue.qsize()} messages)...")
            await self._queue.join()

            # Wait for sender task to exit
            await self._sender_task

        # Close bot session
        await self.bot.session.close()

        logger.info("Telegram client closed")

    def __repr__(self) -> str:
        return (
            f"AsyncTelegram(chat_id={self.chat_id}, "
            f"queue_size={self._queue.qsize()}, closed={self._closed})"
        )


# Convenience factory function
def create_async_telegram(
    token: str,
    chat_id: str,
    max_queue_size: int = 500,
) -> AsyncTelegram:
    """
    Factory function to create an AsyncTelegram instance.

    Args:
        token: Telegram bot token
        chat_id: Target chat ID
        max_queue_size: Max queued messages

    Returns:
        AsyncTelegram instance
    """
    return AsyncTelegram(
        token=token,
        chat_id=chat_id,
        max_queue_size=max_queue_size,
    )
