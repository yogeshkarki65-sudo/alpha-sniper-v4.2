"""
Alpha Sniper v4.2 - Async Trading Bot

Fully asynchronous trading bot with:
- Pump detection and signal generation
- Risk-based position sizing
- Idempotent order execution
- Position management (breakeven, partial TP, SL/TP)
- Circuit breakers (daily loss cap, streak breaker)
- SQLite WAL + single writer pattern
- Graceful shutdown with queue draining
"""

import asyncio
import signal
import logging
import sys
import time
import uuid
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent / "alpha-sniper"))

from config.settings import get_settings
from config.runtime_settings import RuntimeSettings
from core.exchange_async import AsyncExchange
from core.autotune import AutoTunePro
from db.async_driver import AsyncDB
from notify.telegram_async import AsyncTelegram
from scanner.runner import scan_symbols, MarketDataCache
from universe.select import select_top_liquid_symbols_with_cache
from signals.pump_engine import PumpEngine
from signals.hold_policy import update_position_with_hold_brain
from risk.async_risk_engine import AsyncRiskEngine
from utils.locks import symbol_lock
from utils.timebar import sleep_until_next_minute

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


async def process_signals_async(
    signals: list,
    exchange: AsyncExchange,
    risk: AsyncRiskEngine,
    telegram: AsyncTelegram,
    settings,
) -> tuple[int, int]:
    """
    Process signals and place orders.

    Args:
        signals: List of signal dicts from pump engine
        exchange: Exchange instance
        risk: Risk engine instance
        telegram: Telegram notifier
        settings: Settings object

    Returns:
        (signals_opened, signals_skipped)
    """
    opened, skipped = 0, 0

    for sig in signals:
        symbol = sig.get('symbol')

        try:
            # Step 1: Check if can open new position
            can_open, reason = await risk.can_open_new_position_async(sig, exchange)
            if not can_open:
                logger.debug(f"Cannot open {symbol}: {reason}")
                skipped += 1
                continue

            # Step 1.1: Check cooldown (Phase 1.1)
            if settings.COOLDOWN_PER_SYMBOL_SEC > 0:
                if await risk.is_symbol_on_cooldown(symbol):
                    logger.debug(f"Symbol {symbol} on cooldown, skipping")
                    skipped += 1
                    continue

            # Step 2: Calculate position size
            entry_price = sig.get('entry_price')
            stop_loss = sig.get('stop_loss')
            size_usd = await risk.calculate_position_size_async(sig, entry_price, stop_loss, exchange)

            if size_usd <= 0 or size_usd < settings.MIN_VIABLE_TRADE_USD:
                logger.debug(f"Position size too small for {symbol}: ${size_usd:.2f}")
                skipped += 1
                continue

            # Step 3: Exchange validation
            valid, why, details = await exchange.validate_order(symbol, size_usd, entry_price)
            if not valid:
                logger.info(f"Order validation failed for {symbol}: {why} | {details}")
                skipped += 1
                continue

            amount = details['amount']
            price = details['price']

            # Step 4: Liquidity gate (pre-order check)
            liq = await exchange.get_liquidity_metrics(symbol, size_usd)
            if liq['spread_pct'] > settings.MAX_SPREAD_PCT_ORDER:
                logger.info(
                    f"Spread too high for {symbol}: {liq['spread_pct']:.2f}% > {settings.MAX_SPREAD_PCT_ORDER:.2f}%"
                )
                skipped += 1
                continue

            required_depth = size_usd * settings.MIN_DEPTH_MULTIPLE
            if liq['depth_usd'] < required_depth:
                logger.info(
                    f"Insufficient depth for {symbol}: ${liq['depth_usd']:.0f} < ${required_depth:.0f}"
                )
                skipped += 1
                continue

            # Phase 1.1: Absolute depth floor check
            if settings.MIN_DEPTH_USD_ABSOLUTE > 0:
                if liq['depth_usd'] < settings.MIN_DEPTH_USD_ABSOLUTE:
                    logger.info(
                        f"Depth below absolute floor for {symbol}: ${liq['depth_usd']:.0f} < ${settings.MIN_DEPTH_USD_ABSOLUTE:.0f}"
                    )
                    skipped += 1
                    continue

            # Step 5: LIVE_TEST_MODE check
            if settings.LIVE_TEST_MODE:
                test_allowed, adjusted_size, test_reason = await risk.check_live_test_limits_async(
                    size_usd, symbol
                )
                if not test_allowed:
                    logger.info(f"LIVE_TEST_MODE limit: {test_reason}")
                    skipped += 1
                    continue

                if adjusted_size != size_usd:
                    size_usd = adjusted_size
                    amount = size_usd / entry_price

            # Step 6: Place order with per-symbol lock + idempotency
            async with symbol_lock(symbol):
                client_oid = f"alpha-{symbol.replace('/', '')}-{int(time.time()//60)}-{uuid.uuid4().hex[:6]}"

                try:
                    # Use aggressive limit IOC for pump/pump_early signals if enabled
                    if settings.AGGRESSIVE_LIMIT_IOC and sig.get('engine') in ('pump', 'pump_early'):
                        order = await exchange.create_aggressive_limit_ioc(
                            symbol=symbol,
                            side='buy' if sig['side'] == 'long' else 'sell',
                            size_usd=size_usd,
                            max_slip_pct=settings.AGG_LIMIT_MAX_SLIP_PCT,
                            client_oid=client_oid,
                        )
                    else:
                        order = await exchange.create_order_idempotent(
                            symbol=symbol,
                            side='buy' if sig['side'] == 'long' else 'sell',
                            order_type='market',
                            amount=amount,
                            client_oid=client_oid,
                            params={'leverage': 1}
                        )
                except Exception as e:
                    logger.error(f"Order placement error for {symbol}: {e}", exc_info=True)
                    skipped += 1
                    continue

            # Step 7: Verify order success and add position
            if order and order.get('id'):
                order_id = order.get('id')
                filled_qty = order.get('filled', amount)
                avg_price = order.get('average', entry_price)

                # Phase 1.1: Track slippage
                expected_price = liq.get('best_ask', entry_price)  # Best ask for buys
                await risk.track_order_fill(expected_price, avg_price)

                # Create position object
                now_ts = int(time.time())
                max_hold_hours = sig.get('max_hold_hours', 6)
                deadline_ts = now_ts + int(max_hold_hours * 3600)

                position = {
                    'symbol': symbol,
                    'side': sig['side'],
                    'engine': sig.get('engine', 'pump'),
                    'entry_price': avg_price,
                    'stop_loss': stop_loss,
                    'tp_2r': sig.get('tp_2r'),
                    'tp_4r': sig.get('tp_4r'),
                    'qty': filled_qty,
                    'size_usd': size_usd,
                    'risk_pct': settings.RISK_PER_TRADE,
                    'initial_risk_usd': abs(avg_price - stop_loss) * filled_qty,
                    'equity_at_entry': await risk.get_real_equity_async(exchange),
                    'score': sig.get('score'),
                    'regime': sig.get('regime', 'SIDEWAYS'),
                    'timestamp_open': now_ts,
                    'max_hold_hours': max_hold_hours,
                    'deadline_ts': deadline_ts,
                    'peak_price': avg_price,
                    'promoted_count': 0,
                }

                # Add to database
                await risk.add_position_async(position)
                opened += 1

                # Notify via Telegram
                if telegram:
                    r_risk = abs(avg_price - stop_loss)
                    r_reward = abs(sig.get('tp_4r', avg_price) - avg_price) if sig.get('tp_4r') else 0
                    r_multiple = (r_reward / r_risk) if r_risk > 0 else 0

                    await telegram.send(
                        f"✅ OPENED {sig['side'].upper()}\n"
                        f"Symbol: {symbol}\n"
                        f"Entry: ${avg_price:.6f}\n"
                        f"Stop: ${stop_loss:.6f}\n"
                        f"Target: ${sig.get('tp_4r', 0):.6f}\n"
                        f"Size: ${size_usd:.2f}\n"
                        f"R: {r_multiple:.2f}R\n"
                        f"Score: {sig.get('score', 0)}"
                    )

                logger.info(
                    f"✅ Position opened: {symbol} | "
                    f"side={sig['side']} | size=${size_usd:.2f} | "
                    f"entry=${avg_price:.6f} | order_id={order_id}"
                )
            else:
                logger.error(f"Order returned invalid response for {symbol}: {order}")
                skipped += 1

        except Exception as e:
            logger.error(f"Error processing signal for {symbol}: {e}", exc_info=True)
            skipped += 1

    return opened, skipped


async def manage_positions_loop(
    exchange: AsyncExchange,
    risk: AsyncRiskEngine,
    telegram: AsyncTelegram,
    autotune: 'AutoTunePro' = None,
):
    """
    Continuously manage open positions.

    Checks every 5 seconds for:
    - Breakeven at +0.7R
    - Partial TP (50%) at +2R
    - Stop-loss hits
    - Take-profit hits (2R, 4R)
    - Max hold time exceeded
    """
    logger.info("Position management loop started")

    while not stop_event.is_set():
        try:
            positions = await risk.get_open_positions_async()

            for pos in positions:
                symbol = pos['symbol']

                try:
                    # Fetch current price
                    ticker = await exchange.fetch_ticker(symbol)
                    current_price = ticker.get('last', ticker.get('close'))

                    if not current_price:
                        continue

                    entry_price = pos['entry_price']
                    stop_loss = pos['stop_loss']
                    side = pos['side']

                    # Calculate R-multiple
                    risk_per_unit = abs(entry_price - stop_loss) or 1e-12
                    if side == 'long':
                        unrealized_pnl = current_price - entry_price
                    else:
                        unrealized_pnl = entry_price - current_price

                    unrealized_r = unrealized_pnl / risk_per_unit

                    # Dynamic Hold Brain: Promote/Demote/Trailing Stop
                    # Fetch market data for hold brain analysis (if available)
                    market_data_for_brain = None
                    # We'll pass None for now - could fetch OHLCV here if needed for EMA/RVOL checks

                    updated_pos, brain_action = update_position_with_hold_brain(
                        pos, current_price, market_data_for_brain, settings
                    )

                    # Handle brain actions
                    if brain_action == "DEMOTED":
                        logger.info(f"🧠 Hold brain: DEMOTE {symbol} (flat/negative too long)")
                        await close_position_async(pos, current_price, 'DEMOTED_BY_BRAIN', exchange, risk, telegram, autotune)
                        continue
                    elif brain_action == "HARD_CAP":
                        logger.info(f"🧠 Hold brain: HARD_CAP {symbol} (max {settings.HOLD_BRAIN_MAX_HOLD_HOURS}h)")
                        await close_position_async(pos, current_price, 'HARD_CAP', exchange, risk, telegram, autotune)
                        continue
                    elif brain_action == "PROMOTED":
                        await risk.update_position_async(updated_pos)
                        logger.info(f"🧠 Hold brain: PROMOTE {symbol} (deadline extended, count={updated_pos.get('promoted_count', 0)})")
                        pos = updated_pos
                    elif brain_action == "TRAILING_STOP":
                        await risk.update_position_async(updated_pos)
                        logger.info(f"🧠 Hold brain: TRAILING_STOP {symbol} (new stop=${updated_pos['stop_loss']:.6f})")
                        pos = updated_pos
                        stop_loss = pos['stop_loss']  # Update for subsequent checks

                    # Breakeven at +0.7R
                    if unrealized_r >= 0.7 and not pos.get('breakeven_moved'):
                        pos['stop_loss'] = entry_price
                        pos['breakeven_moved'] = 1
                        await risk.update_position_async(pos)
                        logger.info(f"🔒 Breakeven activated for {symbol} at +{unrealized_r:.2f}R")

                    # Partial TP at +2R
                    if unrealized_r >= 2.0 and not pos.get('partial_tp_taken'):
                        partial_qty = pos['qty'] * 0.5

                        async with symbol_lock(symbol):
                            try:
                                await exchange.create_order_idempotent(
                                    symbol=symbol,
                                    side='sell' if side == 'long' else 'buy',
                                    order_type='market',
                                    amount=partial_qty,
                                )
                                pos['qty'] *= 0.5
                                pos['partial_tp_taken'] = 1
                                await risk.update_position_async(pos)
                                logger.info(f"💰 Partial TP (50%) taken for {symbol} at +{unrealized_r:.2f}R")
                            except Exception as e:
                                logger.error(f"Failed to take partial TP for {symbol}: {e}")

                    # Check stop-loss
                    if (side == 'long' and current_price <= stop_loss) or \
                       (side == 'short' and current_price >= stop_loss):
                        await close_position_async(pos, current_price, 'STOP_LOSS', exchange, risk, telegram, autotune)
                        continue

                    # Check take-profit targets
                    tp_4r = pos.get('tp_4r')
                    tp_2r = pos.get('tp_2r')

                    if tp_4r and side == 'long' and current_price >= tp_4r:
                        await close_position_async(pos, current_price, 'TP_4R', exchange, risk, telegram, autotune)
                        continue
                    elif tp_2r and side == 'long' and current_price >= tp_2r:
                        await close_position_async(pos, current_price, 'TP_2R', exchange, risk, telegram, autotune)
                        continue

                    # Check deadline (replaces old max_hold_hours check)
                    # Note: deadline_ts is now managed by hold brain, which can extend it
                    deadline_ts = pos.get('deadline_ts')
                    if deadline_ts and time.time() >= deadline_ts:
                        await close_position_async(pos, current_price, 'DEADLINE_EXPIRED', exchange, risk, telegram, autotune)
                        continue

                except Exception as e:
                    logger.error(f"Error managing position {symbol}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in position management loop: {e}", exc_info=True)

        # Wait 5 seconds before next check
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5.0)
            break  # Stop event was set
        except asyncio.TimeoutError:
            pass  # Normal - continue loop


async def daily_digest_loop(
    risk: AsyncRiskEngine,
    telegram: AsyncTelegram,
    settings,
    autotune: 'AutoTunePro' = None,
):
    """
    Send daily digest at configured hour (UTC).

    Includes:
    - Daily PnL and trade stats
    - IOC reject rate
    - Average slippage
    - Open positions
    """
    logger.info("Daily digest loop started")

    last_digest_date = None

    while not stop_event.is_set():
        try:
            import datetime
            now_utc = datetime.datetime.utcnow()
            current_date = now_utc.strftime("%Y-%m-%d")
            current_hour = now_utc.hour

            # Check if it's time to send digest
            if (
                settings.DIGEST_ENABLE
                and current_hour == settings.DIGEST_HOUR_UTC
                and current_date != last_digest_date
                and telegram
            ):
                # Generate digest
                digest = await risk.get_daily_digest()

                # Format message
                msg = (
                    f"📊 Daily Digest - {digest['date']}\n\n"
                    f"Trades: {digest['total_trades']} ({digest['winners']}W / {digest['losers']}L)\n"
                    f"Win Rate: {digest['win_rate']:.1f}%\n"
                    f"PnL: ${digest['total_pnl']:.2f}\n\n"
                    f"Orders: {digest['total_fills']}/{digest['total_orders']} filled\n"
                    f"IOC Rejects: {digest['ioc_rejects']}\n"
                    f"Avg Slippage: {digest['avg_slippage_bps']:.1f} bps\n\n"
                    f"Open Positions: {digest['open_positions']}"
                )

                # Add AutoTune snapshot if available
                if autotune:
                    snap = autotune.snapshot()
                    msg += (
                        f"\n\n🤖 AutoTune Pro\n"
                        f"Signals/hr: {snap['signals_per_hour']}  Slip(p95): {snap['p95_slip_bps']}bps\n"
                        f"IOC Rej: {int(100*snap['ioc_reject_rate'])}%  AvgR: {snap['avgR']:.2f}  Win: {int(100*snap['winrate'])}%\n"
                        f"RET5M: {snap['EARLY_RET_5M_MIN']:.4f}  VSpk: {snap['EARLY_VOL_SPIKE_MIN']:.2f}\n"
                        f"Score: {snap['MIN_SCORE']}  Risk: {snap['RISK_PER_TRADE']:.4f}\n"
                        f"Test Mode: {snap['LIVE_TEST_MODE']}"
                    )

                await telegram.send(msg)
                logger.info(f"Daily digest sent for {current_date}")
                last_digest_date = current_date

            # Check every 5 minutes
            await asyncio.sleep(300)

        except Exception as e:
            logger.error(f"Error in digest loop: {e}", exc_info=True)
            await asyncio.sleep(60)


async def close_position_async(
    position: dict,
    exit_price: float,
    reason: str,
    exchange: AsyncExchange,
    risk: AsyncRiskEngine,
    telegram: AsyncTelegram,
    autotune: 'AutoTunePro' = None,
):
    """
    Close a position and record the trade.

    Args:
        position: Position dict
        exit_price: Current/exit price
        reason: Close reason (STOP_LOSS, TP_2R, TP_4R, MAX_HOLD_TIME)
        exchange: Exchange instance
        risk: Risk engine instance
        telegram: Telegram notifier
    """
    symbol = position['symbol']
    side = position['side']
    qty = position['qty']

    logger.info(f"🔴 Closing position {symbol} | reason={reason}")

    # Place close order
    async with symbol_lock(symbol):
        try:
            order = await exchange.create_order_idempotent(
                symbol=symbol,
                side='sell' if side == 'long' else 'buy',
                order_type='market',
                amount=qty,
            )

            if order and order.get('id'):
                filled_price = order.get('average', exit_price)
            else:
                filled_price = exit_price

        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}", exc_info=True)
            filled_price = exit_price

    # Calculate PnL
    entry_price = position['entry_price']
    if side == 'long':
        pnl_usd = (filled_price - entry_price) * qty
    else:
        pnl_usd = (entry_price - filled_price) * qty

    pnl_pct = (pnl_usd / position['size_usd'] * 100) if position['size_usd'] > 0 else 0
    r_multiple = (pnl_usd / position['initial_risk_usd']) if position['initial_risk_usd'] > 0 else 0

    # Save to trade history
    await risk.save_closed_trade_async(position, filled_price, pnl_usd, reason)

    # Remove from open positions
    await risk.remove_position_async(symbol)

    # Phase 1.1: Set cooldown for this symbol
    await risk.set_symbol_cooldown(symbol)

    # Feed R-multiple to AutoTune Pro
    if autotune:
        autotune.on_trade_closed(r_multiple)

    # Notify
    if telegram:
        emoji = "✅" if pnl_usd > 0 else "❌"
        await telegram.send(
            f"{emoji} CLOSED {side.upper()}\n"
            f"Symbol: {symbol}\n"
            f"Entry: ${entry_price:.6f}\n"
            f"Exit: ${filled_price:.6f}\n"
            f"PnL: ${pnl_usd:.2f} ({pnl_pct:+.2f}%)\n"
            f"R: {r_multiple:+.2f}R\n"
            f"Reason: {reason}"
        )

    logger.info(
        f"Position closed: {symbol} | "
        f"PnL=${pnl_usd:.2f} ({pnl_pct:+.2f}%) | "
        f"R={r_multiple:+.2f}R | reason={reason}"
    )


async def reconciliation_loop(
    exchange: AsyncExchange,
    risk: AsyncRiskEngine,
    telegram: AsyncTelegram,
):
    """
    Periodic reconciliation between DB and exchange.

    Checks every 60 seconds for:
    - Positions in DB but not on exchange
    - Positions on exchange but not in DB
    """
    logger.info("Reconciliation loop started")

    while not stop_event.is_set():
        try:
            # Get open positions from DB
            db_positions = await risk.get_open_positions_async()
            db_symbols = {p['symbol'] for p in db_positions}

            # For now, just log counts
            # In production, you'd fetch exchange positions and compare
            if db_symbols:
                logger.debug(f"Reconciliation: {len(db_symbols)} positions in DB")

        except Exception as e:
            logger.error(f"Error in reconciliation loop: {e}", exc_info=True)

        # Wait 60 seconds before next check
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60.0)
            break  # Stop event was set
        except asyncio.TimeoutError:
            pass  # Normal - continue loop


async def main():
    """
    Main async entrypoint.

    Sets up all async components and runs the trading loop.
    """
    try:
        # Load settings
        settings = get_settings()

        # Load runtime overrides (persisted changes survive restarts)
        logger.info("Loading runtime overrides...")
        overlay = RuntimeSettings(settings, path="./data/overrides.json", log=logger)
        overlay.load()

        logger.info("=" * 80)
        logger.info("🚀 Alpha Sniper v4.2 - ASYNC TRADING BOT")
        logger.info("=" * 80)
        logger.info(f"Mode: {settings.MODE}")
        logger.info(f"Exchange: {settings.EXCHANGE_ID}")
        logger.info(f"Universe size: {settings.UNIVERSE_SIZE}")
        logger.info(f"Scan concurrency: {settings.SCAN_CONCURRENCY}")
        logger.info(f"Scan interval: {settings.SCAN_INTERVAL_SECONDS}s")
        logger.info(f"Timeframe: {settings.TIMEFRAME}")
        logger.info(f"Min pump score: {settings.MIN_SCORE}")
        logger.info(f"LIVE_TEST_MODE: {settings.LIVE_TEST_MODE}")
        if settings.LIVE_TEST_MODE:
            logger.info(f"  Max orders/day: {settings.LIVE_TEST_MAX_ORDERS_PER_DAY}")
            logger.info(f"  Max USD/order: ${settings.LIVE_TEST_MAX_USD_PER_ORDER}")
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

        # Initialize async risk engine
        logger.info("Initializing risk engine...")
        risk = AsyncRiskEngine(settings.DB_PATH, settings, logger)
        await risk.connect()
        logger.info("Risk engine connected")

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
            equity = await risk.get_real_equity_async(exchange)
            await telegram.send(
                f"🚀 Alpha Sniper v4.2 ASYNC\n"
                f"Mode: {settings.MODE}\n"
                f"Exchange: {settings.EXCHANGE_ID}\n"
                f"Universe: {settings.UNIVERSE_SIZE} symbols\n"
                f"Equity: ${equity:.2f}\n"
                f"Test Mode: {settings.LIVE_TEST_MODE}\n"
                f"Status: ✅ ONLINE"
            )
        else:
            logger.info("Telegram disabled or not configured")

        # Initialize pump engine (synchronous - called from async loop)
        logger.info("Initializing pump engine...")
        # Create a minimal config object for pump engine
        class PumpConfig:
            def __init__(self, s):
                self.pump_engine_enabled = True
                self.pump_only_mode = s.PUMP_ONLY_MODE
                self.min_24h_quote_volume = s.MIN_24H_QUOTE_VOLUME
                self.pump_debug_logging = False

            def get_pump_thresholds(self, regime):
                # Simple threshold object
                class Thresholds:
                    def __init__(self, s):
                        self.min_24h_quote_volume = s.MIN_24H_QUOTE_VOLUME
                        self.min_score = s.MIN_SCORE
                        self.min_rvol = 2.0
                        self.min_24h_return = 0.30
                        self.max_24h_return = 4.0
                        self.min_momentum = 0.02
                        self.new_listing_min_rvol = 3.0
                        self.new_listing_min_score = 35
                        self.new_listing_min_momentum = 0.05
                return Thresholds(settings)

        pump_config = PumpConfig(settings)
        pump_engine = PumpEngine(pump_config, logger)
        logger.info("Pump engine initialized")

        # Initialize AutoTune Pro
        logger.info("Initializing AutoTune Pro...")
        autotune = AutoTunePro(settings, overlay, logger)
        logger.info(f"AutoTune Pro initialized (enabled: {settings.AUTOTUNE_ENABLE})")

        # Initialize caches
        universe_cache = {}
        market_data_cache = MarketDataCache(ttl_seconds=settings.MARKET_DATA_CACHE_TTL)

        logger.info("=" * 80)
        logger.info("✅ All components initialized")
        logger.info("🔄 Starting trading loops...")
        logger.info("=" * 80)

        # Start background tasks
        position_task = asyncio.create_task(manage_positions_loop(exchange, risk, telegram, autotune))
        reconcile_task = asyncio.create_task(reconciliation_loop(exchange, risk, telegram))
        digest_task = asyncio.create_task(daily_digest_loop(risk, telegram, settings, autotune))

        # Main trading loop - aligned to closed 1-minute candles
        scan_count = 0

        while not stop_event.is_set():
            try:
                # Wait until next minute boundary (closed candle)
                await sleep_until_next_minute(offset_sec=0.1)

                scan_count += 1
                logger.info(f"\n{'=' * 80}")
                logger.info(f"🔍 SCAN #{scan_count} | {time.strftime('%Y-%m-%d %H:%M:%S')}")
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
                    logger.warning("No symbols in universe, skipping scan")
                    continue

                logger.info(f"Universe: {len(symbols)} symbols")

                # Step 2: Scan symbols (fetch OHLCV + compute indicators)
                market_data = await scan_symbols(
                    symbols=symbols,
                    timeframe=settings.TIMEFRAME,
                    exchange=exchange,
                    concurrency=settings.SCAN_CONCURRENCY,
                    limit=500,
                )

                logger.info(f"Market data fetched: {len(market_data)}/{len(symbols)} symbols")
                # --- Feature extraction (from raw OHLCV) ---
                def _features_from_ohlcv(ohlcv, wick_mult: float):
                    try:
                        if not ohlcv or len(ohlcv) < 25:
                            return {"ret_5m": 0.0, "rvol_1m_vs20": 0.0, "accel": False, "wick_flag": False}
                        closes = [float(x[4]) for x in ohlcv]
                        vols   = [float(x[5]) for x in ohlcv]
                        c_last, c_first5 = closes[-1], closes[-5]
                        ret5m = (c_last / c_first5) - 1.0
                        v_last = vols[-1]
                        v_avg20 = (sum(vols[-21:-1]) / 20.0) if len(vols) >= 21 else max(sum(vols)/max(len(vols),1), 1e-9)
                        vspike = (v_last / v_avg20) if v_avg20 > 0 else 0.0
                        accel = closes[-1] > closes[-2]
                        highs = [float(x[2]) for x in ohlcv]
                        lows  = [float(x[3]) for x in ohlcv]
                        trs=[]
                        for i in range(-15, -1):
                            h,l,pc = highs[i], lows[i], closes[i-1]
                            trs.append(max(h-l, abs(h-pc), abs(l-pc)))
                        atr14 = (sum(trs)/14.0) if trs else 0.0
                        o_last = float(ohlcv[-1][1])
                        body_top = max(o_last, c_last)
                        wick_flag = (atr14>0.0) and ((highs[-1] - body_top) >= wick_mult * atr14)
                        return {"ret_5m": ret5m, "rvol_1m_vs20": vspike, "accel": accel, "wick_flag": wick_flag}
                    except Exception:
                        return {"ret_5m": 0.0, "rvol_1m_vs20": 0.0, "accel": False, "wick_flag": False}

                wick_mult_cfg = float(getattr(settings, "WICK_FILTER_ATR_MULT", 2.0))
                _rows = []
                for _sym, _d in (market_data or {}).items():
                    _f = (_d or {}).get("features") or {}
                    if "ret_5m" not in _f or "rvol_1m_vs20" not in _f:
                        _calc = _features_from_ohlcv((_d or {}).get("ohlcv") or [], wick_mult_cfg)
                        _f.update(_calc)
                        # simple composite for sorting visibility
                        _f.setdefault("pump_score", (_calc["ret_5m"]*100.0) + max((_calc["rvol_1m_vs20"]-1.0)*10.0, 0.0))
                        (_d or {})["features"] = _f
                        market_data[_sym] = _d
                    _rows.append({
                        "symbol": _sym,
                        "ret5m": float(_f.get("ret_5m", 0.0)),
                        "vspike": float(_f.get("rvol_1m_vs20", 0.0)),
                        "score": float(_f.get("pump_score", 0.0)),
                        "accel": bool(_f.get("accel", False)),
                        "wick":  bool(_f.get("wick_flag", False)),
                        "depth": float((_d or {}).get("depth_usd", 0.0)),
                    })
                # Highest "energy" at top for near-miss visibility
                _rows.sort(key=lambda r: (r["ret5m"]*100 + r["vspike"]*5 + r["score"]), reverse=True)

                # --- Lightweight depth snapshot for top-K (cached) ---
                try:
                    _now = time.time()
                    _k   = int(getattr(settings, "SNAPSHOT_DEPTH_TOPK", 3))
                    _ttl = int(getattr(settings, "SNAPSHOT_DEPTH_CACHE_SEC", 20))
                    if _k > 0:
                        for _r in _rows[:_k]:
                            sym = _r["symbol"]
                            md  = market_data.get(sym) or {}
                            if md.get("_depth_ts") and (_now - md["_depth_ts"] < _ttl):
                                continue
                            try:
                                ob = await exchange.fetch_order_book(sym)
                                bids = ob.get("bids") or []; asks = ob.get("asks") or []
                                def _depth_usd(levels):
                                    total = 0.0
                                    for px, qty in levels[:10]:
                                        total += float(px) * float(qty)
                                    return total
                                depth_usd = min(_depth_usd(bids), _depth_usd(asks))
                                md["depth_usd"] = depth_usd
                                md["_depth_ts"] = _now
                                market_data[sym] = md
                                _r["depth"] = depth_usd
                            except Exception:
                                pass
                except Exception:
                    pass

                signals = pump_engine.generate_signals(market_data, regime='SIDEWAYS')

                logger.info(f"Signals generated: {len(signals)}")

                # Feed signal count to AutoTune Pro
                autotune.on_scan(len(signals))

                # Log top 3 near-miss candidates when no signals
                if not signals:
                    try:
                        for _row in _rows[:3]:
                            logger.info(
                                "[EARLY_TOP] %s ret5m=%.2f%% vspike=%.2f score=%.1f accel=%s wick=%s depth=$%.0f",
                                _row["symbol"], _row["ret5m"]*100.0, _row["vspike"], _row["score"],
                                _row["accel"], _row["wick"], _row["depth"]
                            )
                    except Exception:
                        pass

                # --- EAGER breakout entry path (optional, LIVE_TEST gated by default) ---
                eager_opened = 0
                eager_max_per_scan = int(getattr(settings, "EAGER_MAX_PER_SCAN", 1))
                if getattr(settings, "EAGER_ENABLE", True) and (eager_opened < eager_max_per_scan):
                    if (not getattr(settings, "EAGER_ONLY_LIVE_TEST", True)) or bool(getattr(settings, "LIVE_TEST_MODE", True)):
                        try:
                            for row in _rows:
                                if eager_opened >= eager_max_per_scan:
                                    break
                                # Arm conditions: big vspike & not too negative over 5m; must not be a wick
                                if row["vspike"] < float(settings.EAGER_VSPIKE_MIN):
                                    continue
                                if row["ret5m"] < float(settings.EAGER_MAX_NEG_RET5M):
                                    continue
                                if row["wick"]:
                                    continue
                                if getattr(settings, "EAGER_REQUIRE_ACCEL", False) and (not row["accel"]):
                                    continue
                                sym = row["symbol"]
                                md = market_data.get(sym) or {}
                                ohlcv = md.get("ohlcv") or []
                                lookback_n = int(getattr(settings, "EAGER_LOOKBACK_HIGH_N", 5))
                                if len(ohlcv) < max(6, lookback_n + 1):
                                    continue
                                highs = [float(x[2]) for x in ohlcv]
                                lookback_high = max(highs[-(lookback_n+1):-1])
                                trigger = lookback_high * (1.0 + float(settings.EAGER_EPS_PCT))
                                last_close = float(ohlcv[-1][4])
                                entry_px = max(trigger, last_close)

                                # position sizing with tight SL
                                sl_price = entry_px * (1.0 - float(settings.EAGER_SL_PCT))
                                size_usd = await risk.calculate_position_size_async(
                                    {"symbol": sym, "side": "long", "engine": "pump"},
                                    entry_px, sl_price
                                )
                                if size_usd < float(settings.MIN_VIABLE_TRADE_USD):
                                    continue
                                valid, why, det = await exchange.validate_order(sym, size_usd, entry_px)
                                if not valid:
                                    logger.info(f"[EAGER] {sym} rejected by validate_order: {why}")
                                    continue
                                qty = size_usd / entry_px
                                # Sanitize symbol for client order ID (remove illegal chars)
                                safe_sym = sym.replace("/", "").replace("-", "")
                                client_oid = f"eager-{safe_sym}-{int(time.time()*1000)}"
                                try:
                                    order = await exchange.create_order_idempotent(
                                        symbol=sym,
                                        side="buy",
                                        order_type="limit",
                                        amount=qty,
                                        price=entry_px,
                                        params={"timeInForce": "IOC"},
                                        client_oid=client_oid
                                    )
                                except Exception as e:
                                    logger.info(f"[EAGER] {sym} create_order failed: {e}")
                                    continue
                                if order and order.get("id"):
                                    tp = entry_px * (1.0 + float(settings.EAGER_TP_PCT))
                                    pos = {
                                        "symbol": sym, "side": "long", "engine": "pump",
                                        "entry_price": entry_px, "stop_loss": sl_price,
                                        "tp_2r": tp, "tp_4r": tp,
                                        "qty": qty, "size_usd": size_usd,
                                        "timestamp_open": int(time.time()),
                                        "max_hold_hours": max(0.25, float(getattr(settings, "HOLD_BRAIN_MAX_HOLD_HOURS", 8.0)))
                                    }
                                    await risk.add_position_async(pos)
                                    logger.info(f"[EAGER] OPENED {sym} @ {entry_px:.8f} size=${size_usd:.2f} tp={tp:.8f} sl={sl_price:.8f}")
                                    eager_opened += 1
                        except Exception as e:
                            logger.error(f"[EAGER] pipeline error: {e}", exc_info=True)

                if signals:
                    for sig in signals[:5]:  # Log first 5
                        logger.info(
                            f"  🎯 {sig['symbol']} | score={sig.get('score', 0)} | "
                            f"entry=${sig.get('entry_price', 0):.6f}"
                        )

                # Step 4: Process signals (place orders)
                opened, skipped = await process_signals_async(
                    signals, exchange, risk, telegram, settings
                )

                logger.info(f"Signals processed: opened={opened}, skipped={skipped}")

                # Step 5: Save equity snapshot
                await risk.save_equity_snapshot_async(exchange)

                # Step 6: Run AutoTune adjustments
                autotune.maybe_tune()
                autotune.maybe_sizing_autopilot()
                autotune.maybe_flip_live_test_off()

            except asyncio.CancelledError:
                logger.info("Trading loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                if telegram:
                    await telegram.send(f"⚠️ Error in trading loop: {str(e)[:200]}")

        # Graceful shutdown
        logger.info("\n" + "=" * 80)
        logger.info("🛑 Shutting down gracefully...")
        logger.info("=" * 80)

        # Cancel background tasks
        position_task.cancel()
        reconcile_task.cancel()

        try:
            await asyncio.gather(position_task, reconcile_task, return_exceptions=True)
        except Exception:
            pass

        if telegram:
            await telegram.send("🛑 Alpha Sniper shutting down...")
            logger.info("Closing Telegram...")
            await telegram.close()

        logger.info("Closing database...")
        await db.close()

        logger.info("Closing risk engine...")
        await risk.close()

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
