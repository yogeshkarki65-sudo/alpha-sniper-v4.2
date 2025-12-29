"""
Alpha Sniper v4.2 - Async Main Entrypoint

Fully asynchronous trading bot with:
- Non-blocking I/O for all operations
- Bounded concurrency via Semaphore
- Shared indicator precompute
- SQLite WAL + single writer
- Graceful shutdown with queue draining
"""

import asyncio
import signal
import logging
import sys
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent / "alpha-sniper"))

from config.settings import get_settings
from core.exchange_async import AsyncExchange
from db.async_driver import AsyncDB
from notify.telegram_async import AsyncTelegram
from scanner.runner import scan_symbols, MarketDataCache
from universe.select import select_top_liquid_symbols_with_cache

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

# Global stop event for graceful shutdown
stop_event = asyncio.Event()


def setup_signal_handlers():
    """
    Set up signal handlers for graceful shutdown.

    Handles SIGINT (Ctrl+C) and SIGTERM (kill).
    """
    def signal_handler(signum, frame):
        signame = signal.Signals(signum).name
        logger.warning(f"Received {signame}, initiating graceful shutdown...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Signal handlers registered (SIGINT, SIGTERM)")


async def main():
    """
    Main async entrypoint.

    Sets up all async components and runs the trading loop.
    """
    try:
        # Load settings
        settings = get_settings()

        logger.info("=" * 80)
        logger.info("🚀 Alpha Sniper v4.2 - ASYNC MODE")
        logger.info("=" * 80)
        logger.info(f"Mode: {settings.MODE}")
        logger.info(f"Exchange: {settings.EXCHANGE_ID}")
        logger.info(f"Universe size: {settings.UNIVERSE_SIZE}")
        logger.info(f"Scan concurrency: {settings.SCAN_CONCURRENCY}")
        logger.info(f"Scan interval: {settings.SCAN_INTERVAL_SECONDS}s")
        logger.info(f"Timeframe: {settings.TIMEFRAME}")
        logger.info("=" * 80)

        # Set up signal handlers
        setup_signal_handlers()

        # Initialize async exchange
        logger.info("Initializing exchange...")
        exchange = AsyncExchange(
            exchange_id=settings.EXCHANGE_ID,
            api_key=settings.API_KEY,
            secret=settings.API_SECRET,
            testnet=settings.TESTNET,
        )

        # Load markets
        logger.info("Loading markets...")
        markets = await exchange.load_markets()
        logger.info(f"Markets loaded: {len(markets)} symbols")

        # Initialize async database
        logger.info("Initializing database...")
        db = AsyncDB(settings.DB_PATH)
        await db.connect()
        logger.info(f"Database connected: {settings.DB_PATH}")

        # Initialize Telegram (if configured)
        telegram = None
        if settings.TELEGRAM_ENABLED and settings.TELEGRAM_TOKEN and settings.TELEGRAM_CHAT_ID:
            logger.info("Initializing Telegram...")
            telegram = AsyncTelegram(
                token=settings.TELEGRAM_TOKEN,
                chat_id=settings.TELEGRAM_CHAT_ID,
                max_queue_size=settings.TELEGRAM_MAX_QUEUE,
            )
            await telegram.start()
            logger.info("Telegram initialized")

            # Send startup notification
            await telegram.send(
                f"🚀 Alpha Sniper v4.2 ASYNC\n"
                f"Mode: {settings.MODE}\n"
                f"Exchange: {settings.EXCHANGE_ID}\n"
                f"Universe: {settings.UNIVERSE_SIZE} symbols\n"
                f"Concurrency: {settings.SCAN_CONCURRENCY}\n"
                f"Status: ✅ ONLINE"
            )
        else:
            logger.info("Telegram disabled or not configured")

        # Initialize caches
        universe_cache = {}
        market_data_cache = MarketDataCache(ttl_seconds=settings.MARKET_DATA_CACHE_TTL)

        logger.info("=" * 80)
        logger.info("✅ All components initialized")
        logger.info("🔄 Starting trading loop...")
        logger.info("=" * 80)

        # Main trading loop
        scan_count = 0

        while not stop_event.is_set():
            try:
                scan_count += 1
                logger.info(f"\n{'=' * 80}")
                logger.info(f"🔍 SCAN #{scan_count}")
                logger.info(f"{'=' * 80}")

                # Step 1: Select universe by liquidity
                symbols = await select_top_liquid_symbols_with_cache(
                    exchange=exchange,
                    base_quote=settings.UNIVERSE_BASE_QUOTE,
                    max_symbols=settings.UNIVERSE_SIZE,
                    min_quote_volume=settings.UNIVERSE_MIN_QUOTE_VOLUME,
                    cache=universe_cache,
                )

                if not symbols:
                    logger.warning("No symbols selected for universe, skipping scan")
                    await asyncio.sleep(settings.SCAN_INTERVAL_SECONDS)
                    continue

                # Step 2: Scan symbols (fetch OHLCV + compute indicators)
                market_data = await scan_symbols(
                    symbols=symbols,
                    timeframe=settings.TIMEFRAME,
                    exchange=exchange,
                    concurrency=settings.SCAN_CONCURRENCY,
                    limit=500,
                )

                logger.info(f"Market data fetched: {len(market_data)}/{len(symbols)} symbols")

                # Step 3: TODO - Run trading engines on market_data
                # This is where you would integrate your existing engine logic
                # For now, just log that we have the data
                logger.info(f"Market data ready for engines: {len(market_data)} symbols")

                # Example: Access precomputed indicators
                # for symbol, data in market_data.items():
                #     indicators = data['indicators']
                #     rsi = indicators.get('rsi_14', 50)
                #     ema_20 = indicators.get('ema_20', 0)
                #     # ... run your engine logic here

                # Step 4: Wait for next scan (or stop signal)
                logger.info(f"Scan #{scan_count} complete, waiting {settings.SCAN_INTERVAL_SECONDS}s...")

                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=settings.SCAN_INTERVAL_SECONDS
                    )
                    # If we get here, stop_event was set
                    break
                except asyncio.TimeoutError:
                    # Timeout is normal - continue to next scan
                    pass

            except asyncio.CancelledError:
                logger.info("Trading loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)

                if telegram:
                    await telegram.send(f"⚠️ Error in trading loop: {str(e)[:200]}")

                # Wait a bit before retrying
                await asyncio.sleep(10)

        # Graceful shutdown
        logger.info("\n" + "=" * 80)
        logger.info("🛑 Shutting down gracefully...")
        logger.info("=" * 80)

        if telegram:
            await telegram.send("🛑 Alpha Sniper shutting down...")
            logger.info("Closing Telegram...")
            await telegram.close()

        logger.info("Closing database...")
        await db.close()

        logger.info("Closing exchange...")
        await exchange.close()

        logger.info("=" * 80)
        logger.info("✅ Shutdown complete")
        logger.info("=" * 80)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
