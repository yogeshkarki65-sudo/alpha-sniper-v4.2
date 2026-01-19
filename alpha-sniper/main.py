"""
Alpha Sniper V4.2 - Main Entry Point
Full-Dynamic-Safe-Bull Trading Bot

Features:
- SIM and LIVE modes
- Regime-based position sizing
- Multiple signal engines (long, short, pump, bear_micro)
- Safe risk management
- Telegram alerts
- Fast Stop Manager (dual async loops)
"""
import argparse
import asyncio
import signal
import time
from datetime import datetime, timezone

import schedule
from config import get_config
from exchange import create_exchange
from risk_engine import RiskEngine
from signals.scanner import Scanner
from utils import helpers, setup_logger
from utils.dynamic_filters import update_dynamic_filters
from utils.entry_dete import EntryDETEngine
from utils.pump_trailer import PumpTrailer
from utils.telegram import TelegramNotifier
from utils.telegram_alerts import TelegramAlertManager


class AlphaSniperBot:
    """
    Main trading bot class
    """
    def __init__(self):
        # Load config
        self.config = get_config()

        # Setup logger
        self.logger = setup_logger()

        # Log startup
        self.logger.info("=" * 60)
        self.logger.info("🚀 Alpha Sniper V4.2 Starting...")
        self.logger.info("🔧 Mode: LIVE")
        self.logger.info(f"💰 Starting Equity: ${self.config.starting_equity:.2f}")
        self.logger.info("=" * 60)

        # Log V4.2 Overlay Status
        self.logger.info("")
        self.logger.info("📋 V4.2 Overlay Status:")
        self.logger.info(f"   Sideways Coil Boost: {'ENABLED' if self.config.sideways_coil_enabled else 'DISABLED'}")
        self.logger.info(f"   Short Funding Overlay: {'ENABLED' if self.config.short_funding_overlay_enabled else 'DISABLED'}")
        self.logger.info(f"   Pump Allocation Feedback: {'ENABLED' if self.config.pump_feedback_enabled else 'DISABLED'}")
        self.logger.info(f"   Liquidity-Aware Sizing: {'ENABLED' if self.config.liquidity_sizing_enabled else 'DISABLED'}")
        self.logger.info(f"   Correlation Guard: {'ENABLED' if self.config.correlation_limit_enabled else 'DISABLED'}")
        self.logger.info("")

        # Log Fast Stop Manager Status
        self.logger.info("⚡ Fast Stop Manager:")
        self.logger.info(f"   SCAN interval: {self.config.scan_interval_seconds}s")
        self.logger.info(f"   Position check interval: {self.config.position_check_interval_seconds}s (Fast Stop Manager enabled)")
        self.logger.info(f"   Min stop distance - Core: {self.config.min_stop_pct_core*100:.1f}%")
        self.logger.info(f"   Min stop distance - Bear Micro: {self.config.min_stop_pct_bear_micro*100:.1f}%")
        self.logger.info(f"   Min stop distance - Pump: {self.config.min_stop_pct_pump*100:.1f}%")
        self.logger.info("")

        # Initialize components
        self.telegram = TelegramNotifier(self.config, self.logger)
        self.alert_mgr = TelegramAlertManager(self.config, self.logger, self.telegram)
        self.exchange = create_exchange(self.config, self.logger)  # Use factory
        self.risk_engine = RiskEngine(self.config, self.exchange, self.logger, self.telegram, self.alert_mgr)
        self.scanner = Scanner(self.exchange, self.risk_engine, self.config, self.logger)
        self.entry_dete_engine = EntryDETEngine(self.config, self.logger, self.exchange, self.risk_engine)
        self.pump_trailer = PumpTrailer(self.config, self.logger)

        # Rate limiting for error notifications (15 min cooldown)
        self.last_error_notification = 0
        self.error_notification_cooldown = 900  # 15 minutes in seconds

        # Track if we've sent first equity sync notification
        self.first_equity_sync_notified = False

        # Last scan time tracking (for drift detection and heartbeat)
        self.last_scan_time = None
        self.drift_alert_sent = False  # Track if we've already sent drift alert

        # Fast mode tracking
        self.fast_mode_start_time = None
        if self.config.fast_mode_enabled:
            self.fast_mode_start_time = time.time()
            self.logger.info(f"⚡ FAST MODE ENABLED: {self.config.fast_scan_interval_seconds}s intervals")
            self.logger.info(f"   Will auto-disable after {self.config.fast_mode_max_runtime_hours} hours")

        # === v4.2.3: Live test mode tracking ===
        self.live_test_orders_today = 0
        self.live_test_reset_date = time.strftime("%Y-%m-%d")
        if self.config.live_test_mode:
            self.logger.info("")
            self.logger.info("🧪 LIVE TEST MODE ENABLED:")
            self.logger.info(f"   Max orders per day: {self.config.max_live_test_orders_per_day}")
            self.logger.info(f"   Max USD per order: ${self.config.max_live_test_usd_per_order:.2f}")
            self.logger.info(f"   Auto-cancel timeout: {self.config.live_test_cancel_timeout_seconds}s")
            self.logger.info("")

        # Send enhanced startup notification
        regime = self.risk_engine.current_regime if self.risk_engine.current_regime else 'UNKNOWN'

        self.logger.info("[TELEGRAM] Sending enhanced startup notification")
        self.alert_mgr.send_startup(
            mode='LIVE',
            pump_only=self.config.pump_only_mode,
            data_source='LIVE',
            equity=self.config.starting_equity,
            regime=regime
        )

        # Load existing positions
        self.risk_engine.load_positions(self.config.positions_file_path)

        # Running flag
        self.running = True

    def trading_cycle(self):
        """
        Main trading cycle - runs every scan interval
        """
        try:
            # Sync equity from MEXC
            try:
                live_equity = self.exchange.get_total_usdt_balance()
                if live_equity is not None and live_equity > 0:
                    old_equity = self.risk_engine.current_equity
                    self.risk_engine.update_equity(live_equity)

                    # Send enhanced Telegram notification on first equity sync
                    old_diff = abs(old_equity - self.config.starting_equity)
                    equity_diff = abs(live_equity - old_equity)
                    if (
                        not self.first_equity_sync_notified
                        and old_diff < 0.01
                        and equity_diff > 0.01
                    ):
                        self.alert_mgr.send_equity_sync(
                            config_equity=self.config.starting_equity,
                            mexc_balance=live_equity
                        )
                        self.logger.info("[TELEGRAM] Sent enhanced equity sync notification")
                        self.first_equity_sync_notified = True
                else:
                    self.logger.warning("⚠️ Failed to fetch MEXC balance, using cached equity")
            except Exception as e:
                self.logger.error(f"⚠️ Error syncing MEXC equity: {e}, using cached equity")

            # Enhanced cycle header with key info
            cycle_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            regime = self.risk_engine.current_regime or "UNKNOWN"
            open_pos = len(self.risk_engine.open_positions)

            self.logger.info("")
            self.logger.info("=" * 70)
            cycle_header = (
                f"🔄 New cycle | t={cycle_time} | regime={regime} | "
                f"equity=${self.risk_engine.current_equity:.2f} | "
                f"open_positions={open_pos}"
            )
            self.logger.info(cycle_header)
            self.logger.info("=" * 70)

            # 1. Check daily reset
            self.risk_engine.check_daily_reset()

            # 2. Update regime (and send alert if changed)
            old_regime = self.risk_engine.current_regime
            self.risk_engine.update_regime()
            new_regime = self.risk_engine.current_regime

            # Send regime change alert if regime changed
            if old_regime != new_regime and old_regime is not None:
                btc_price = 0
                try:
                    ticker = self.exchange.get_ticker('BTC/USDT')
                    if ticker:
                        btc_price = ticker.get('last', ticker.get('close', 0))
                except Exception:
                    pass
                self.alert_mgr.send_regime_change(old_regime, new_regime, btc_price)
                self.logger.info(f"[TELEGRAM] Sent regime change notification: {old_regime} → {new_regime}")

            # 3. Manage existing positions
            self._manage_positions()

            # 4. Run scanner to get signals
            signals = self.scanner.scan()

            # 5. Process new signals
            if signals:
                self._process_signals(signals)
            else:
                self.logger.info("📊 No signals to process")

            # 6. Save positions
            self.risk_engine.save_positions(self.config.positions_file_path)

            # 7. Log summary
            self._log_cycle_summary()

            self.logger.info("😴 Sleeping until next cycle...")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.logger.error(f"🔴 Error in trading cycle: {e}")
            self.logger.exception(e)

            # Send critical error alert to Telegram (rate limited to once per 15 min)
            try:
                current_time = time.time()
                if current_time - self.last_error_notification >= self.error_notification_cooldown:
                    error_type = type(e).__name__
                    error_msg = str(e)[:200]  # Limit to 200 chars
                    self.logger.info("[TELEGRAM] Sending critical error notification")
                    self.telegram.send(
                        f"🚨 [LIVE] CRITICAL ERROR\n"
                        f"Type: {error_type}\n"
                        f"Message: {error_msg}\n"
                        f"Bot will attempt to continue...\n"
                        f"(Rate limited: max 1 alert per 15 min)"
                    )
                    self.last_error_notification = current_time
            except Exception:
                pass  # Don't crash on Telegram failure

    def _manage_positions(self):
        """
        Manage open positions: check SL/TP, max hold time, partial TPs
        """
        if not self.risk_engine.open_positions:
            self.logger.info("📊 No open positions to manage")
            return

        self.logger.info(f"📊 Managing {len(self.risk_engine.open_positions)} open position(s)...")

        positions_to_close = []

        for position in self.risk_engine.open_positions:
            try:
                symbol = position['symbol']
                side = position['side']
                entry_price = position['entry_price']
                stop_loss = position['stop_loss']
                tp_2r = position.get('tp_2r', 0)
                tp_4r = position.get('tp_4r', 0)
                timestamp_open = position['timestamp_open']
                max_hold_hours = position.get('max_hold_hours', 48)

                # Get current price
                ticker = self.exchange.get_ticker(symbol)
                if not ticker:
                    self.logger.warning(f"⚠️ Could not fetch ticker for {symbol}")
                    continue

                current_price = ticker.get('last', ticker.get('close', 0))
                if current_price == 0:
                    continue

                # Calculate PnL%
                if side == 'long':
                    pnl_pct = ((current_price / entry_price) - 1) * 100
                else:
                    pnl_pct = ((entry_price / current_price) - 1) * 100

                # Calculate unrealized R-multiple for exit logic improvements
                risk_per_unit = abs(entry_price - stop_loss)
                if side == 'long':
                    unrealized_pnl_per_unit = current_price - entry_price
                else:
                    unrealized_pnl_per_unit = entry_price - current_price

                unrealized_r = unrealized_pnl_per_unit / risk_per_unit if risk_per_unit > 0 else 0

                # Exit improvement: Move stop to breakeven at +0.7R
                if unrealized_r >= 0.7 and 'breakeven_moved_at_07r' not in position:
                    position['breakeven_moved_at_07r'] = True
                    position['stop_loss'] = entry_price
                    try:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}: {float(unrealized_r):.2f}R")
                    except Exception:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}")

                # Exit improvement: Partial TP (50%) at +2R
                if unrealized_r >= 2.0 and 'partial_tp_taken' not in position:
                    qty = position.get('qty', 0)
                    partial_qty = qty * 0.5

                    # Execute the partial close order
                    try:
                        close_side = 'sell' if side == 'long' else 'buy'
                        order = self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=close_side,
                            amount=partial_qty
                        )
                        if not order or not order.get('id'):
                            self.logger.error(f"[EXIT] Partial TP order failed for {symbol}")
                            continue
                    except Exception as e:
                        self.logger.error(f"[EXIT] Failed to execute partial TP for {symbol}: {e}")
                        continue

                    # Mark as taken and update position tracking
                    position['partial_tp_taken'] = True
                    position['qty'] = qty - partial_qty
                    if 'size_usd' in position:
                        position['size_usd'] = position['size_usd'] * 0.5

                    self.logger.info(f"[EXIT] Partial TP at +2R for {symbol}: closed 50% at {current_price:.6f}")

                # Check max hold time
                hold_time_hours = (time.time() - timestamp_open) / 3600
                if hold_time_hours >= max_hold_hours:
                    positions_to_close.append((position, current_price, f"Max hold time ({max_hold_hours}h)"))
                    continue

                # Check stop loss
                if side == 'long':
                    if current_price <= stop_loss:
                        positions_to_close.append((position, current_price, "Stop loss hit"))
                        continue
                else:  # short
                    if current_price >= stop_loss:
                        positions_to_close.append((position, current_price, "Stop loss hit"))
                        continue

                # Check take profit targets
                if side == 'long':
                    if current_price >= tp_4r:
                        positions_to_close.append((position, current_price, "4R target hit"))
                        continue
                    elif current_price >= tp_2r:
                        # Partial TP: move SL to breakeven if not already done
                        if 'breakeven_moved' not in position:
                            position['breakeven_moved'] = True
                            position['stop_loss'] = entry_price * 1.001  # Breakeven + 0.1%
                            self.logger.info(f"✅ {symbol} {side} | 2R hit, SL moved to breakeven")
                else:  # short
                    if current_price <= tp_4r:
                        positions_to_close.append((position, current_price, "4R target hit"))
                        continue
                    elif current_price <= tp_2r:
                        if 'breakeven_moved' not in position:
                            position['breakeven_moved'] = True
                            position['stop_loss'] = entry_price * 0.999  # Breakeven - 0.1%
                            self.logger.info(f"✅ {symbol} {side} | 2R hit, SL moved to breakeven")

                # Log position status
                self.logger.debug(
                    f"   {symbol} {side} | "
                    f"Entry: ${entry_price:.6f} | "
                    f"Current: ${current_price:.6f} | "
                    f"PnL: {pnl_pct:+.2f}% | "
                    f"Hold: {hold_time_hours:.1f}h"
                )

            except Exception as e:
                self.logger.error(f"Error managing position {position.get('symbol', 'UNKNOWN')}: {e}")
                continue

        # Close positions
        for position, exit_price, reason in positions_to_close:
            self.risk_engine.close_position(position, exit_price, reason)

    def _check_fast_stops(self):
        """
        Fast Stop Manager - lightweight check for SL/TP hits only
        Runs every POSITION_CHECK_INTERVAL_SECONDS (e.g. 15s)
        Does NOT scan for new signals or update regime
        """
        if not self.risk_engine.open_positions:
            return  # No positions to check

        positions_to_close = []

        for position in self.risk_engine.open_positions:
            try:
                symbol = position['symbol']
                side = position['side']
                entry_price = position['entry_price']
                stop_loss = position['stop_loss']
                tp_2r = position.get('tp_2r', 0)
                tp_4r = position.get('tp_4r', 0)

                # Get current price using ticker (real-time)
                current_price = self.exchange.get_last_price(symbol)
                if not current_price or current_price == 0:
                    continue

                # Calculate unrealized R-multiple for exit logic improvements
                risk_per_unit = abs(entry_price - stop_loss)
                if side == 'long':
                    unrealized_pnl_per_unit = current_price - entry_price
                else:
                    unrealized_pnl_per_unit = entry_price - current_price

                unrealized_r = unrealized_pnl_per_unit / risk_per_unit if risk_per_unit > 0 else 0

                # Exit improvement: Move stop to breakeven at +0.7R
                if unrealized_r >= 0.7 and 'breakeven_moved_at_07r' not in position:
                    position['breakeven_moved_at_07r'] = True
                    position['stop_loss'] = entry_price
                    try:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}: {float(unrealized_r):.2f}R")
                    except Exception:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}")

                # Exit improvement: Partial TP (50%) at +2R
                if unrealized_r >= 2.0 and 'partial_tp_taken' not in position:
                    qty = position.get('qty', 0)
                    partial_qty = qty * 0.5

                    # Execute the partial close order
                    try:
                        close_side = 'sell' if side == 'long' else 'buy'
                        order = self.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=close_side,
                            amount=partial_qty
                        )
                        if not order or not order.get('id'):
                            self.logger.error(f"[EXIT] Partial TP order failed for {symbol}")
                            continue
                    except Exception as e:
                        self.logger.error(f"[EXIT] Failed to execute partial TP for {symbol}: {e}")
                        continue

                    # Mark as taken and update position tracking
                    position['partial_tp_taken'] = True
                    position['qty'] = qty - partial_qty
                    if 'size_usd' in position:
                        position['size_usd'] = position['size_usd'] * 0.5

                    self.logger.info(f"[EXIT] Partial TP at +2R for {symbol}: closed 50% at {current_price:.6f}")

                # Check stop loss (FAST enforcement)
                if side == 'long':
                    if current_price <= stop_loss:
                        positions_to_close.append((position, current_price, "Stop loss hit (FAST STOP)"))
                        continue
                else:  # short
                    if current_price >= stop_loss:
                        positions_to_close.append((position, current_price, "Stop loss hit (FAST STOP)"))
                        continue

                # Check take profit targets
                if side == 'long':
                    if current_price >= tp_4r:
                        positions_to_close.append((position, current_price, "4R target hit (FAST STOP)"))
                        continue
                    elif current_price >= tp_2r:
                        # Move to breakeven if not already done
                        if 'breakeven_moved' not in position:
                            position['breakeven_moved'] = True
                            position['stop_loss'] = entry_price * 1.001
                            self.logger.info(f"[FastStop] {symbol} {side} | 2R hit, SL moved to breakeven")
                else:  # short
                    if current_price <= tp_4r:
                        positions_to_close.append((position, current_price, "4R target hit (FAST STOP)"))
                        continue
                    elif current_price <= tp_2r:
                        if 'breakeven_moved' not in position:
                            position['breakeven_moved'] = True
                            position['stop_loss'] = entry_price * 0.999
                            self.logger.info(f"[FastStop] {symbol} {side} | 2R hit, SL moved to breakeven")

            except Exception as e:
                self.logger.error(f"[FastStop] Error checking {position.get('symbol', 'UNKNOWN')}: {e}")
                continue

        # Close positions with FAST STOP marker in logging
        for position, exit_price, reason in positions_to_close:
            symbol = position['symbol']
            side = position['side']
            entry = position['entry_price']
            stop = position['stop_loss']

            # Calculate slippage
            if side == 'long':
                slip_pct = ((exit_price / stop) - 1) * 100 if stop > 0 else 0
            else:
                slip_pct = ((stop / exit_price) - 1) * 100 if exit_price > 0 else 0

            # Calculate R-multiple
            risk_per_unit = abs(entry - stop)
            actual_pnl_per_unit = (exit_price - entry) if side == 'long' else (entry - exit_price)
            r_multiple = actual_pnl_per_unit / risk_per_unit if risk_per_unit > 0 else 0

            self.logger.info(
                f"[FastStop] Closing {symbol} {side} | price={exit_price:.6f} "
                f"{'<=' if side == 'long' else '>='} stop={stop:.6f} | "
                f"slip={slip_pct:+.2f}% | R={r_multiple:.2f}"
            )

            self.risk_engine.close_position(position, exit_price, reason)

    def _update_pump_trailing_stops(self):
        """
        Update ATR-based trailing stops for pump positions
        Runs every POSITION_CHECK_INTERVAL_SECONDS (e.g. 15s) as part of position loop
        """
        if not self.risk_engine.open_positions:
            return  # No positions to update

        for position in self.risk_engine.open_positions:
            try:
                # Only process pump positions
                if position.get('engine') != 'pump':
                    continue

                # Check if this position should be trailed
                if not self.pump_trailer.should_trail(position):
                    continue

                symbol = position['symbol']

                # Get current price
                current_price = self.exchange.get_last_price(symbol)
                if not current_price or current_price == 0:
                    self.logger.debug(f"[PumpTrailer] Skipping {symbol}: no price data")
                    continue

                # Get 15m klines for ATR calculation
                klines = self.exchange.get_klines(symbol, '15m', limit=20)
                if not klines or len(klines) < 15:
                    self.logger.debug(f"[PumpTrailer] Skipping {symbol}: insufficient kline data")
                    continue

                # Convert to dataframe and calculate ATR
                df_15m = helpers.ohlcv_to_dataframe(klines)
                atr_series = helpers.calculate_atr(df_15m, 14)
                if atr_series is None or len(atr_series) == 0:
                    self.logger.debug(f"[PumpTrailer] Skipping {symbol}: ATR calculation failed")
                    continue

                atr_15m = atr_series.iloc[-1]

                # Update trailing stop
                self.pump_trailer.update(position, current_price, atr_15m)

            except Exception as e:
                self.logger.debug(f"[PumpTrailer] Error updating {position.get('symbol', 'UNKNOWN')}: {e}")
                continue

    def _check_live_test_limits(self, size_usd: float, symbol: str) -> tuple[bool, float, str]:
        """
        Check and enforce live test mode limits

        Returns:
            (allowed: bool, adjusted_size: float, reason: str)
        """
        if not self.config.live_test_mode:
            return True, size_usd, ""

        # Check if we need to reset daily counter (new day)
        current_date = time.strftime("%Y-%m-%d")
        if current_date != self.live_test_reset_date:
            self.logger.info(f"[LIVE_TEST] Daily counter reset (new day: {current_date})")
            self.live_test_orders_today = 0
            self.live_test_reset_date = current_date

        # Check daily order limit
        if self.live_test_orders_today >= self.config.max_live_test_orders_per_day:
            return False, 0, f"LIVE_TEST_DAILY_LIMIT_REACHED ({self.live_test_orders_today}/{self.config.max_live_test_orders_per_day})"

        # Adjust size if exceeds per-order limit
        adjusted_size = min(size_usd, self.config.max_live_test_usd_per_order)
        if adjusted_size < size_usd:
            self.logger.info(
                f"[LIVE_TEST] Limiting order size for {symbol}: "
                f"${size_usd:.2f} → ${adjusted_size:.2f} (max ${self.config.max_live_test_usd_per_order:.2f})"
            )

        # Increment counter
        self.live_test_orders_today += 1

        return True, adjusted_size, ""

    def _process_signals(self, signals: list):
        """
        Process new trading signals with comprehensive validation and lifecycle logging
        """
        self.logger.info(f"📡 Processing {len(signals)} signal(s)...")

        signals_opened = 0
        signals_queued = 0

        # === v4.2.3: Skip reason tracking ===
        skip_reasons = {}  # {reason_code: count}

        def add_skip_reason(reason: str):
            """Track skip reasons for aggregate summary"""
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

        for sig in signals:
            try:
                # Check if we can open new position (CORE filters)
                can_open, reason = self.risk_engine.can_open_new_position(sig)

                if not can_open:
                    add_skip_reason("CORE_" + reason.replace(" ", "_").upper()[:30])
                    self.logger.debug(f"❌ Cannot open {sig['symbol']} {sig['engine']}: {reason}")
                    continue

                # === v4.2.3: Early Depth Gate - Filter out low-liquidity symbols BEFORE LiquidityGuard ===
                if self.config.min_depth_usd > 0:
                    try:
                        symbol = sig['symbol']
                        liquidity = self.exchange.get_liquidity_metrics(symbol)
                        depth_usd = liquidity.get('depth_usd', 0)

                        if depth_usd < self.config.min_depth_usd:
                            add_skip_reason("SKIP_EARLY_DEPTH_GATE")
                            self.logger.debug(
                                f"[EARLY_DEPTH_GATE] REJECT {symbol} | "
                                f"depth=${depth_usd:.0f} < min=${self.config.min_depth_usd:.0f}"
                            )
                            continue
                    except Exception as e:
                        self.logger.debug(f"[EARLY_DEPTH_GATE] Error for {sig['symbol']}: {e}, proceeding")

                # Entry-DETE: Queue sig instead of opening immediately
                if self.config.entry_dete_enabled:
                    self.entry_dete_engine.queue_signal(sig)
                    signals_queued += 1
                    continue  # Skip immediate entry logic below

                # Get current price (use entry_price from sig)
                entry_price = sig['entry_price']
                stop_loss = sig['stop_loss']
                symbol = sig['symbol']

                # Calculate position size (includes LiquidityGuard scaling)
                size_usd = self.risk_engine.calculate_position_size(sig, entry_price, stop_loss)

                # === v4.2.3: Viability Gate 1 - Check if LiquidityGuard rejected (returns 0.0) ===
                if size_usd <= 0:
                    add_skip_reason("SKIP_TOO_SMALL_AFTER_LIQUIDITY")
                    self.logger.debug(f"❌ [{symbol}] LiquidityGuard rejected (size={size_usd})")
                    continue

                # === v4.2.3: Viability Gate 2 - Spread and Depth checks ===
                try:
                    liquidity = self.exchange.get_liquidity_metrics(symbol)
                    spread_pct = liquidity.get('spread_pct', 0.5)
                    depth_usd = liquidity.get('depth_usd', 10000)

                    # Check spread
                    if spread_pct > self.config.max_spread_pct_order:
                        add_skip_reason("SKIP_SPREAD_TOO_HIGH")
                        self.logger.info(
                            f"[VIABILITY_CHECK] REJECT {symbol} | reason=SPREAD_TOO_HIGH | "
                            f"spread={spread_pct:.2f}% > max={self.config.max_spread_pct_order:.2f}%"
                        )
                        continue

                    # Check depth
                    required_depth = size_usd * self.config.min_depth_multiple
                    if depth_usd < required_depth:
                        add_skip_reason("SKIP_DEPTH_TOO_LOW")
                        self.logger.info(
                            f"[VIABILITY_CHECK] REJECT {symbol} | reason=DEPTH_TOO_LOW | "
                            f"depth=${depth_usd:.0f} < required=${required_depth:.0f} "
                            f"(size=${size_usd:.2f} * {self.config.min_depth_multiple}x)"
                        )
                        continue

                    # Log viability check success
                    self.logger.debug(
                        f"[VIABILITY_CHECK] PASS {symbol} | size=${size_usd:.2f} | "
                        f"spread={spread_pct:.2f}% | depth=${depth_usd:.0f}"
                    )

                except Exception as e:
                    self.logger.warning(f"[VIABILITY_CHECK] Error for {symbol}: {e}, proceeding with caution")

                # === v4.2.3: Exchange Validation ===
                # Validate against exchange limits (minQty, minNotional, precision)
                valid, reason_code, details = self.exchange.validate_order(symbol, size_usd, entry_price)

                if not valid:
                    add_skip_reason(reason_code)
                    self.logger.info(
                        f"[ORDER_VALIDATION] REJECT {symbol} | reason={reason_code} | "
                        f"size=${size_usd:.2f} | price={entry_price:.6f} | "
                        f"details={details}"
                    )
                    continue

                self.logger.debug(f"[ORDER_VALIDATION] PASS {symbol} | {details}")

                # Calculate risk % and quantities
                risk_pct = self.risk_engine.get_risk_per_trade(sig.get('engine', 'standard'))
                equity_at_entry = self.risk_engine.current_equity
                initial_risk_usd = equity_at_entry * risk_pct
                qty = size_usd / entry_price if entry_price > 0 else 0

                # Create position object
                position = {
                    'symbol': sig['symbol'],
                    'side': sig['side'],
                    'engine': sig['engine'],
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'tp_2r': sig.get('tp_2r', 0),
                    'tp_4r': sig.get('tp_4r', 0),
                    'size_usd': size_usd,
                    'qty': qty,
                    'risk_pct': risk_pct,
                    'initial_risk_usd': initial_risk_usd,
                    'equity_at_entry': equity_at_entry,
                    'score': sig.get('score', 0),
                    'regime': sig.get('regime', ''),
                    'timestamp_open': time.time(),
                    'max_hold_hours': sig.get('max_hold_hours', 48)
                }

                # === LIVE ORDER with full lifecycle logging ===

                # === v4.2.3: Check live test mode limits ===
                if self.config.live_test_mode:
                    test_allowed, adjusted_size_usd, test_reason = self._check_live_test_limits(size_usd, symbol)

                    if not test_allowed:
                        add_skip_reason("LIVE_TEST_LIMIT")
                        self.logger.info(
                            f"[LIVE_TEST] REJECT {symbol} | reason={test_reason}"
                        )
                        continue

                    # Use adjusted size
                    if adjusted_size_usd != size_usd:
                        size_usd = adjusted_size_usd
                        position['size_usd'] = size_usd
                        qty = size_usd / entry_price if entry_price > 0 else 0
                        position['qty'] = qty

                # Calculate amount in base currency
                amount = size_usd / entry_price

                # Log order validation start
                self.logger.info(
                    f"[ORDER_VALIDATING] {symbol} | side={position['side']} | "
                    f"size=${size_usd:.2f} | amount={amount:.6f} | price={entry_price:.6f}"
                )

                try:
                    # Attempt to create order
                    order = self.exchange.create_order(
                        symbol=position['symbol'],
                        type='market',
                        side='buy' if position['side'] == 'long' else 'sell',
                        amount=amount,
                        params={'leverage': 1}  # 1x isolated
                    )

                    # Check if order succeeded
                    if order and order.get('id'):
                        # Extract filled details
                        order_id = order.get('id')
                        filled_qty = order.get('filled', amount)
                        avg_price = order.get('average', order.get('price', entry_price))
                        order_status = order.get('status', 'unknown')

                        # Log order placed
                        self.logger.info(
                            f"[ORDER_PLACED] {symbol} | id={order_id} | "
                            f"side={position['side']} | amount={amount:.6f} | status={order_status}"
                        )

                        # Log order filled (for market orders, usually immediate)
                        if order_status in ['closed', 'filled']:
                            self.logger.info(
                                f"[ORDER_FILLED] {symbol} | id={order_id} | "
                                f"filled_qty={filled_qty:.6f} | avg_price={avg_price:.6f}"
                            )

                        # Success - add position
                        self.logger.info(
                            f"✅ [LIVE] Opened {position['side']} | "
                            f"{position['symbol']} | "
                            f"Size: ${size_usd:.2f} | "
                            f"Order ID: {order_id}"
                        )

                        position['order_id'] = order_id
                        self.risk_engine.add_position(position)
                        signals_opened += 1

                        # Send enhanced Telegram notification for LIVE open
                        try:
                            target = sig.get('tp_4r', sig.get('tp_2r', 0))
                            r_multiple = None
                            if stop_loss > 0 and entry_price > 0:
                                risk_per_unit = abs(entry_price - stop_loss)
                                if risk_per_unit > 0 and target > 0:
                                    reward_per_unit = abs(target - entry_price)
                                    r_multiple = reward_per_unit / risk_per_unit

                            self.alert_mgr.send_trade_open(
                                symbol=position['symbol'],
                                side=position['side'].upper(),
                                engine=position['engine'].upper(),
                                regime=position['regime'],
                                size=amount,
                                entry=entry_price,
                                stop=stop_loss,
                                target=target if target > 0 else None,
                                leverage=1.0,
                                risk_pct=risk_pct * 100,
                                r_multiple=r_multiple
                            )
                            self.logger.info(f"[TELEGRAM] Sent enhanced LIVE trade open notification for {symbol}")
                        except Exception as e:
                            self.logger.warning(f"[TELEGRAM] Failed to send LIVE trade open notification: {e}")

                    else:
                        # Order returned None or no ID - exchange rejected
                        add_skip_reason("EXCHANGE_REJECTED")
                        self.logger.error(
                            f"[ORDER_REJECTED] {symbol} | reason=EXCHANGE_REJECTED | "
                            f"order_response={order}"
                        )

                except Exception as e:
                    # Exception during order creation
                    add_skip_reason("ORDER_EXCEPTION")
                    error_msg = str(e)
                    self.logger.error(
                        f"[ORDER_EXCEPTION] {symbol} | error={error_msg} | "
                        f"error_type={type(e).__name__}"
                    )

                    # Try to extract exchange response if available
                    if hasattr(e, 'response'):
                        try:
                            response_payload = getattr(e, 'response', {})
                            self.logger.error(f"[ORDER_EXCEPTION] Exchange response: {response_payload}")
                        except Exception:
                            pass

            except Exception as e:
                self.logger.error(f"Error processing sig {sig.get('symbol', 'UNKNOWN')}: {e}")
                continue

        # === v4.2.3: Log results with aggregated skip reasons ===
        if signals_queued > 0:
            self.logger.info(f"🎯 Queued {signals_queued} signal(s) for Entry-DETE confirmation")

        if signals_opened > 0:
            self.logger.info(f"✅ Opened {signals_opened} new position(s)")

        if signals_opened == 0 and signals_queued == 0:
            if skip_reasons:
                # Format skip reasons for logging
                reasons_str = " | ".join([f"{k}={v}" for k, v in sorted(skip_reasons.items(), key=lambda x: -x[1])])
                self.logger.info(f"📊 No new positions opened | skip_reasons: {reasons_str}")
            else:
                self.logger.info("📊 No new positions opened or queued (no signals processed)")

    def _log_cycle_summary(self):
        """
        Log summary of current state
        """
        self.logger.info("")
        self.logger.info("📊 Cycle Summary:")
        self.logger.info(f"   Regime: {self.risk_engine.current_regime}")
        self.logger.info(f"   Equity: ${self.risk_engine.current_equity:.2f}")
        self.logger.info(f"   Daily PnL: ${self.risk_engine.daily_pnl:+.2f}")
        self.logger.info(f"   Open Positions: {len(self.risk_engine.open_positions)}/{self.config.max_concurrent_positions}")

        heat = self.risk_engine._calculate_current_heat()
        self.logger.info(f"   Portfolio Heat: {heat*100:.2f}% / {self.config.max_portfolio_heat*100:.2f}%")

    def run_dfe(self):
        """
        Run Dynamic Filter Engine daily adjustment at 00:05 UTC
        """
        if self.config.dfe_enabled:
            try:
                update_dynamic_filters(self.config, self.logger)
            except Exception as e:
                self.logger.error(f"DFE | Error running dynamic filter adjustment: {e}")
                self.logger.exception(e)

    async def scan_loop(self):
        """
        SCAN LOOP (slow, CPU-heavy)
        - Runs every SCAN_INTERVAL_SECONDS (e.g. 300s)
        - Updates regime
        - Scans universe for signals
        - Opens new positions
        - Runs DFE daily at 00:05 UTC
        - Supports FAST_MODE with auto-disable
        """
        self.logger.info("🔄 SCAN LOOP started")

        # Determine scan interval (fast mode or normal)
        scan_interval = self.config.fast_scan_interval_seconds if self.config.fast_mode_enabled else self.config.scan_interval_seconds
        self.logger.info(f"   Scan interval: {scan_interval}s")

        # Run first cycle immediately
        self.trading_cycle()
        self.last_scan_time = time.time()  # Track scan time

        # Setup DFE scheduling if enabled
        if self.config.dfe_enabled:
            schedule.every().day.at("00:05").do(self.run_dfe)
            self.logger.info("🔧 DFE enabled - scheduled daily at 00:05 UTC")
        else:
            self.logger.info("🔧 DFE disabled - filters will not auto-adjust")

        last_scan_time = time.time()

        while self.running:
            try:
                current_time = time.time()
                elapsed = current_time - last_scan_time

                # Check if FAST_MODE should be auto-disabled
                if self.config.fast_mode_enabled and self.fast_mode_start_time:
                    fast_mode_runtime_hours = (current_time - self.fast_mode_start_time) / 3600

                    if fast_mode_runtime_hours >= self.config.fast_mode_max_runtime_hours:
                        # Disable fast mode
                        self.logger.info(
                            f"⚡ FAST MODE AUTO-DISABLED after {fast_mode_runtime_hours:.1f} hours "
                            f"(max: {self.config.fast_mode_max_runtime_hours}h)"
                        )

                        # Switch to normal scan interval
                        self.config.fast_mode_enabled = False
                        scan_interval = self.config.scan_interval_seconds

                        # Send Telegram notification
                        try:
                            self.telegram.send(
                                f"⚡ <b>[LIVE] FAST MODE DISABLED</b>\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"<b>Runtime:</b> {fast_mode_runtime_hours:.1f}h\n"
                                f"<b>Max allowed:</b> {self.config.fast_mode_max_runtime_hours}h\n"
                                f"<b>New scan interval:</b> {scan_interval}s\n"
                                f"\n📊 <i>Reverting to normal scan frequency</i>"
                            )
                            self.logger.info("[TELEGRAM] Fast mode auto-disable notification sent")
                        except Exception as e:
                            self.logger.warning(f"[TELEGRAM] Failed to send fast mode disable notification: {e}")

                # Check if it's time to run next scan
                if elapsed >= scan_interval:
                    self.trading_cycle()
                    last_scan_time = current_time
                    self.last_scan_time = current_time  # Track for drift detection
                    self.drift_alert_sent = False  # Reset drift alert when scan completes

                # Check scheduled tasks (DFE)
                schedule.run_pending()

                # Short sleep to prevent CPU spinning
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in scan_loop: {e}")
                self.logger.exception(e)
                await asyncio.sleep(5)  # Back off on error

    async def position_loop(self):
        """
        POSITION LOOP (fast, lightweight)
        - Runs every POSITION_CHECK_INTERVAL_SECONDS (e.g. 15s)
        - Checks SL/TP for open positions only
        - Does NOT scan universe or generate signals
        - Does NOT update regime or filters
        """
        self.logger.info("⚡ POSITION LOOP (Fast Stop Manager) started")

        # Wait a bit before starting to avoid conflicts with initial scan
        await asyncio.sleep(self.config.position_check_interval_seconds)

        while self.running:
            try:
                # Fast stop check
                self._check_fast_stops()

                # Entry-DETE: Process pending signals for micro-confirmation
                if self.config.entry_dete_enabled:
                    self.entry_dete_engine.process_pending()

                # Pump Trailer: Update trailing stops for pump positions
                self._update_pump_trailing_stops()

                # Save positions after any fast stop triggers or Entry-DETE openings
                if self.risk_engine.open_positions:
                    self.risk_engine.save_positions(self.config.positions_file_path)

                # Sleep until next check
                await asyncio.sleep(self.config.position_check_interval_seconds)

            except Exception as e:
                self.logger.error(f"Error in position_loop: {e}")
                self.logger.exception(e)
                await asyncio.sleep(5)  # Back off on error

    async def drift_detection_loop(self):
        """
        DRIFT DETECTION LOOP
        - Runs every 60s
        - Checks if scan loop has stalled
        - Sends Telegram alert if drift detected
        """
        self.logger.info("🔍 DRIFT DETECTION started")

        # Wait a bit before starting to avoid false positives on startup
        await asyncio.sleep(120)  # 2 minutes grace period on startup

        while self.running:
            try:
                current_time = time.time()

                # Check if last_scan_time exists and is set
                if self.last_scan_time is not None:
                    elapsed_since_scan = current_time - self.last_scan_time

                    # Calculate max allowed stall time: max(3 * scan_interval, 600s)
                    max_stall_seconds = max(
                        self.config.drift_max_stall_multiplier * self.config.scan_interval_seconds,
                        600  # 10 minutes minimum
                    )

                    # Check if scan loop has stalled
                    if elapsed_since_scan > max_stall_seconds:
                        # Send alert only once per stall event
                        if not self.drift_alert_sent:
                            self.logger.error(
                                f"🚨 DRIFT DETECTED: Scan loop stalled! "
                                f"Last scan: {elapsed_since_scan:.0f}s ago (max: {max_stall_seconds:.0f}s)"
                            )

                            # Send Telegram alert
                            try:
                                self.telegram.send(
                                    f"⚠️ <b>[{mode}] DRIFT DETECTED</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━\n"
                                    f"<b>Issue:</b> Scan loop stalled\n"
                                    f"<b>Last scan:</b> {elapsed_since_scan:.0f}s ago\n"
                                    f"<b>Max allowed:</b> {max_stall_seconds:.0f}s\n"
                                    f"<b>Scan interval:</b> {self.config.scan_interval_seconds}s\n"
                                    f"\n⚠️ <i>Bot may be hung or stuck in scan loop</i>"
                                )
                                self.logger.info("[TELEGRAM] Drift detection alert sent")
                                self.drift_alert_sent = True
                            except Exception as e:
                                self.logger.warning(f"[TELEGRAM] Failed to send drift alert: {e}")

                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)

            except Exception as e:
                self.logger.error(f"Error in drift_detection_loop: {e}")
                self.logger.exception(e)
                await asyncio.sleep(60)  # Continue checking even on error

    def run(self):
        """
        Main run loop - starts dual async loops (scan + position)
        """
        try:
            # Run both loops concurrently using asyncio
            asyncio.run(self._run_async())

        except KeyboardInterrupt:
            self.logger.info("")
            self.logger.info("👋 Bot stopped by user (Ctrl+C)")
            self.shutdown()

        except Exception as e:
            self.logger.error(f"🔴 Fatal error in main loop: {e}")
            self.logger.exception(e)

            # Send fatal error alert to Telegram
            try:
                error_type = type(e).__name__
                error_msg = str(e)[:200]  # Limit to 200 chars
                self.logger.info("[TELEGRAM] Sending fatal error notification")
                self.telegram.send(
                    f"🚨 [LIVE] FATAL ERROR\n"
                    f"Type: {error_type}\n"
                    f"Message: {error_msg}\n"
                    f"BOT IS SHUTTING DOWN"
                )
            except Exception:
                pass  # Don't crash on Telegram failure

            self.shutdown()

    async def _run_async(self):
        """
        Run scan_loop, position_loop, and drift_detection concurrently
        """
        try:
            tasks = [
                self.scan_loop(),
                self.position_loop()
            ]

            # Add drift detection if enabled
            if self.config.drift_detection_enabled:
                tasks.append(self.drift_detection_loop())

            await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            self.logger.info("Async loops cancelled")
        except Exception as e:
            self.logger.error(f"Error in async loops: {e}")
            self.logger.exception(e)
            raise

    def shutdown(self):
        """
        Graceful shutdown

        NOTE: Does NOT call sys.exit() - that must be handled by the caller
        to avoid SystemExit exceptions inside async event loops
        """
        self.logger.info("🛑 Shutting down...")

        # Stop the bot loop
        self.running = False

        # Save final positions
        try:
            self.risk_engine.save_positions(self.config.positions_file_path)
        except Exception as e:
            self.logger.error(f"Error saving positions during shutdown: {e}")

        # Send shutdown notification
        try:
            self.telegram.send("🛑 Alpha Sniper V4.2 stopped", description="Shutdown")
        except Exception as e:
            self.logger.error(f"Error sending Telegram shutdown message: {e}")

        self.logger.info("👋 Goodbye!")


def main():
    """
    Main entry point
    """
    # Parse arguments
    parser = argparse.ArgumentParser(description='Alpha Sniper V4.2 Trading Bot')
    parser.add_argument('--once', action='store_true',
                        help='Run a single cycle then exit (for testing)')
    args = parser.parse_args()

    bot = AlphaSniperBot()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        bot.logger.info("")
        bot.logger.info("👋 Received shutdown signal")
        bot.running = False
        bot.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run mode
    if args.once:
        bot.logger.info("🧪 Running in --once test mode (single cycle)")
        bot.trading_cycle()
        bot.logger.info("✅ Test cycle complete, exiting")
        bot.shutdown()
    else:
        # Normal scheduled mode
        bot.run()


if __name__ == "__main__":
    main()
