"""
Timebar alignment utility for scan scheduling.

Ensures scans happen at the start of closed 1-minute candles
to avoid indicator lookahead bias.
"""
import asyncio
import time


async def sleep_until_next_minute(offset_sec: float = 0.1):
    """
    Sleep until the next minute boundary + offset.

    Args:
        offset_sec: Seconds to wait after minute boundary (default: 0.1s)

    This ensures we're always scanning on a closed candle, not mid-candle.

    Example:
        Current time: 13:45:37.234
        Next trigger: 13:46:00.100 (waits ~22.9 seconds)
    """
    now = time.time()
    seconds_into_minute = now % 60
    seconds_until_next_minute = 60 - seconds_into_minute
    delay = seconds_until_next_minute + offset_sec

    if delay > 0:
        await asyncio.sleep(delay)
