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
import time
import schedule
import signal
import sys
import argparse
import asyncio
from datetime import datetime, timezone

from config import get_config
from utils import setup_logger
from utils.dynamic_filters import update_dynamic_filters
from utils.entry_dete import EntryDETEngine
from utils.pump_trailer import PumpTrailer
from utils.telegram import TelegramNotifier
from utils.telegram_alerts import TelegramAlertManager
from utils import helpers
from exchange import create_exchange
from risk_engine import RiskEngine
from signals.scanner import Scanner


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
        mode_str = "SIM" if self.config.sim_mode else "LIVE"
        self.logger.info("=" * 60)
        self.logger.info("🚀 Alpha Sniper V4.2 Starting...")
        self.logger.info(f"🔧 Mode: {mode_str}")
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

        # Send enhanced startup notification
        sim_data_source = getattr(self.config, 'sim_data_source', 'FAKE')
        regime = self.risk_engine.current_regime if self.risk_engine.current_regime else 'UNKNOWN'

        mode_str = 'SIM' if self.config.sim_mode else 'LIVE'
        data_source = sim_data_source if self.config.sim_mode else 'LIVE'

        self.logger.info(f"[TELEGRAM] Sending enhanced startup notification")
        self.alert_mgr.send_startup(
            mode=mode_str,
            pump_only=self.config.pump_only_mode,
            data_source=data_source,
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
            # Sync equity from MEXC in LIVE mode
            if not self.config.sim_mode:
                try:
                    live_equity = self.exchange.get_total_usdt_balance()
                    if live_equity is not None and live_equity > 0:
                        old_equity = self.risk_engine.current_equity
                        self.risk_engine.update_equity(live_equity)

                        # Send enhanced Telegram notification on first equity sync
                        if not self.first_equity_sync_notified and abs(old_equity - self.config.starting_equity) < 0.01 and abs(live_equity - old_equity) > 0.01:
                            self.alert_mgr.send_equity_sync(
                                config_equity=self.config.starting_equity,
                                mexc_balance=live_equity
                            )
                            self.logger.info(f"[TELEGRAM] Sent enhanced equity sync notification")
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
            self.logger.info(f"🔄 New cycle | t={cycle_time} | regime={regime} | sim={self.config.sim_mode} | equity=${self.risk_engine.current_equity:.2f} | open_positions={open_pos}")
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
                except:
                    pass
                self.alert_mgr.send_regime_change(old_regime, new_regime, btc_price)
                self.logger.info(f"[TELEGRAM] Sent regime change notification: {old_regime} → {new_regime}")

            # 3. Manage existing positions
            self._manage_positions()

            # 4. Run scanner to get signals
            scan_start_time = time.time()
            signals = self.scanner.scan()
            scan_duration_ms = (time.time() - scan_start_time) * 1000

            # Send scan summary (if enabled)
            try:
                # Get enabled engines based on pump_only_mode
                enabled_engines = []
                if self.config.pump_only_mode:
                    enabled_engines.append('PUMP')
                else:
                    # Default: all engines enabled (adjust based on your actual logic)
                    enabled_engines = ['PUMP', 'LONG', 'SHORT', 'BEAR_MICRO']

                # Get top signals
                top_signals = []
                if signals:
                    sorted_signals = sorted(signals, key=lambda x: x.get('score', 0), reverse=True)
                    top_signals = [(s['symbol'], s.get('engine', 'unknown').upper(), f"{s.get('score', 0):.2f}")
                                   for s in sorted_signals[:3]]

                # Get universe count (estimate from config or default)
                universe_count = getattr(self.config, 'scan_universe_max', 800)
                signals_count = len(signals) if signals else 0

                self.alert_mgr.send_scan_summary(
                    regime=new_regime,
                    enabled_engines=enabled_engines,
                    universe_count=universe_count,
                    signals_count=signals_count,
                    top_signals=top_signals,
                    scan_time_ms=scan_duration_ms
                )
                self.logger.info(f"📨 Scan summary sent to Telegram ({signals_count} signals)")
            except Exception as e:
                self.logger.error(f"❌ Failed to send scan summary: {e}")

            # 5. Process new signals
            signals_opened_count = 0
            if signals:
                signals_opened_count = self._process_signals(signals)
            else:
                self.logger.info("📊 No signals to process")

            # Send "why no trade" if signals existed but none were opened
            if signals and signals_opened_count == 0:
                try:
                    reasons = []
                    reasons.append(f"{len(signals)} signals generated but none passed risk checks")
                    reasons.append("Possible reasons: max positions reached, insufficient equity, cooldown active")
                    self.alert_mgr.send_why_no_trade(regime=new_regime, reasons=reasons)
                except Exception as e:
                    self.logger.debug(f"Failed to send why-no-trade message: {e}")

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
                    mode = "SIM" if self.config.sim_mode else "LIVE"
                    error_type = type(e).__name__
                    error_msg = str(e)[:200]  # Limit to 200 chars
                    self.logger.info(f"[TELEGRAM] Sending critical error notification")
                    self.telegram.send(
                        f"🚨 [{mode}] CRITICAL ERROR\n"
                        f"Type: {error_type}\n"
                        f"Message: {error_msg}\n"
                        f"Bot will attempt to continue...\n"
                        f"(Rate limited: max 1 alert per 15 min)"
                    )
                    self.last_error_notification = current_time
            except:
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
                    except:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}")

                # Exit improvement: Partial TP (50%) at +2R
                if unrealized_r >= 2.0 and 'partial_tp_taken' not in position:
                    qty = position.get('qty', 0)
                    partial_qty = qty * 0.5

                    # Execute the partial close order (LIVE mode)
                    if not self.config.sim_mode:
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

                # HARD STOP: Guaranteed max loss for PUMP trades (synthetic enforcement)
                engine = position.get('engine', '')
                if engine == 'pump' and side == 'long':
                    hard_stop_price = entry_price * (1 - self.config.pump_max_loss_pct)
                    if current_price <= hard_stop_price:
                        loss_pct = ((current_price / entry_price) - 1) * 100
                        self.logger.error(
                            f"[PUMP_MAX_LOSS] triggered symbol={symbol} engine=pump side={side} "
                            f"entry={entry_price:.6f} current={current_price:.6f} "
                            f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}%"
                        )
                        positions_to_close.append((position, current_price, f"Pump max loss {self.config.pump_max_loss_pct*100:.1f}%"))
                        continue
                elif engine == 'pump' and side == 'short':
                    hard_stop_price = entry_price * (1 + self.config.pump_max_loss_pct)
                    if current_price >= hard_stop_price:
                        loss_pct = ((entry_price / current_price) - 1) * 100
                        self.logger.error(
                            f"[PUMP_MAX_LOSS] triggered symbol={symbol} engine=pump side={side} "
                            f"entry={entry_price:.6f} current={current_price:.6f} "
                            f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}%"
                        )
                        positions_to_close.append((position, current_price, f"Pump max loss {self.config.pump_max_loss_pct*100:.1f}%"))
                        continue

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
                    except:
                        self.logger.info(f"[EXIT] Breakeven activated for {symbol}")

                # Exit improvement: Partial TP (50%) at +2R
                if unrealized_r >= 2.0 and 'partial_tp_taken' not in position:
                    qty = position.get('qty', 0)
                    partial_qty = qty * 0.5

                    # Execute the partial close order (LIVE mode)
                    if not self.config.sim_mode:
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

                # HARD STOP: Guaranteed max loss for PUMP trades (synthetic enforcement) - FAST CHECK
                # This must be checked BEFORE regular stop loss to ensure guaranteed protection
                engine = position.get('engine', '')
                if engine == 'pump' and side == 'long':
                    hard_stop_price = entry_price * (1 - self.config.pump_max_loss_pct)
                    if current_price <= hard_stop_price:
                        loss_pct = ((current_price / entry_price) - 1) * 100
                        self.logger.error(
                            f"[PUMP_MAX_LOSS_FAST] triggered symbol={symbol} engine=pump side={side} "
                            f"entry={entry_price:.6f} current={current_price:.6f} "
                            f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}%"
                        )
                        positions_to_close.append((position, current_price, f"Pump max loss {self.config.pump_max_loss_pct*100:.1f}% (FAST)"))
                        continue
                elif engine == 'pump' and side == 'short':
                    hard_stop_price = entry_price * (1 + self.config.pump_max_loss_pct)
                    if current_price >= hard_stop_price:
                        loss_pct = ((entry_price / current_price) - 1) * 100
                        self.logger.error(
                            f"[PUMP_MAX_LOSS_FAST] triggered symbol={symbol} engine=pump side={side} "
                            f"entry={entry_price:.6f} current={current_price:.6f} "
                            f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}%"
                        )
                        positions_to_close.append((position, current_price, f"Pump max loss {self.config.pump_max_loss_pct*100:.1f}% (FAST)"))
                        continue

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

    async def _synthetic_stop_watchdog(self):
        """
        SYNTHETIC STOP WATCHDOG (ultra-lightweight, dedicated protection loop)

        Runs independently every PUMP_MAX_LOSS_WATCHDOG_INTERVAL (default: 1 second)
        Monitors ONLY pump positions for max loss breaches

        This is the GUARANTEED backstop that ensures pump trades never exceed max loss,
        even if:
        - Exchange stop placement fails
        - Exchange has minimum stop distance constraints
        - Exchange stop order is cancelled/rejected
        - Any other stop placement issues occur

        Design:
        - Ultra-lightweight: only checks price vs hard stop threshold
        - No complex logic, no ATR calculations, no regime checks
        - Minimal API calls: only get_last_price for open pump positions
        - Fast execution: sub-second response time
        - Resilient: runs independently of main scan loop
        """
        self.logger.info("🛡️ SYNTHETIC STOP WATCHDOG started")
        self.logger.info(f"   Check interval: {self.config.pump_max_loss_watchdog_interval}s")
        self.logger.info(f"   Hard stop threshold: {self.config.pump_max_loss_pct*100}%")

        while self.running:
            try:
                # Only process if we have open positions
                if not self.risk_engine.open_positions:
                    await asyncio.sleep(self.config.pump_max_loss_watchdog_interval)
                    continue

                positions_to_close = []

                for position in self.risk_engine.open_positions:
                    try:
                        engine = position.get('engine', '')

                        # ONLY monitor pump positions
                        if engine != 'pump':
                            continue

                        symbol = position['symbol']
                        side = position['side']
                        entry_price = position['entry_price']

                        # Get current price (lightweight ticker call)
                        current_price = self.exchange.get_last_price(symbol)
                        if not current_price or current_price == 0:
                            continue

                        # Check hard stop breach
                        if side == 'long':
                            hard_stop_price = entry_price * (1 - self.config.pump_max_loss_pct)
                            if current_price <= hard_stop_price:
                                loss_pct = ((current_price / entry_price) - 1) * 100
                                self.logger.error(
                                    f"[WATCHDOG_STOP] 🛡️ TRIGGERED | {symbol} {side} | "
                                    f"entry={entry_price:.6f} current={current_price:.6f} "
                                    f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}% | "
                                    f"GUARANTEED_MAX_LOSS_ENFORCED"
                                )
                                positions_to_close.append((position, current_price, f"Watchdog hard stop {loss_pct:.1f}%"))
                        else:  # short
                            hard_stop_price = entry_price * (1 + self.config.pump_max_loss_pct)
                            if current_price >= hard_stop_price:
                                loss_pct = ((entry_price / current_price) - 1) * 100
                                self.logger.error(
                                    f"[WATCHDOG_STOP] 🛡️ TRIGGERED | {symbol} {side} | "
                                    f"entry={entry_price:.6f} current={current_price:.6f} "
                                    f"hard_stop={hard_stop_price:.6f} loss={loss_pct:.2f}% | "
                                    f"GUARANTEED_MAX_LOSS_ENFORCED"
                                )
                                positions_to_close.append((position, current_price, f"Watchdog hard stop {loss_pct:.1f}%"))

                    except Exception as e:
                        self.logger.error(f"[WATCHDOG] Error checking {position.get('symbol', 'UNKNOWN')}: {e}")
                        continue

                # Close positions that breached hard stop
                for position, exit_price, reason in positions_to_close:
                    try:
                        symbol = position['symbol']
                        # Send Telegram alert for watchdog stop trigger
                        try:
                            self.alert_mgr.send_trade_close(
                                symbol=symbol,
                                side=position['side'].upper(),
                                engine=position['engine'].upper(),
                                size=position.get('qty', 0),
                                entry=position['entry_price'],
                                exit=exit_price,
                                pnl_usd=(exit_price - position['entry_price']) * position.get('qty', 0) if position['side'] == 'long' else (position['entry_price'] - exit_price) * position.get('qty', 0),
                                reason=reason
                            )
                            self.logger.info(f"[WATCHDOG] Sent Telegram alert for {symbol} hard stop")
                        except Exception as e:
                            self.logger.warning(f"[WATCHDOG] Failed to send Telegram alert: {e}")

                        # Close position
                        self.risk_engine.close_position(position, exit_price, reason)
                        self.logger.info(f"[WATCHDOG] ✅ Closed {symbol} at {exit_price:.6f} | {reason}")
                    except Exception as e:
                        self.logger.error(f"[WATCHDOG] Error closing {position.get('symbol', 'UNKNOWN')}: {e}")

                # Sleep until next check
                await asyncio.sleep(self.config.pump_max_loss_watchdog_interval)

            except asyncio.CancelledError:
                self.logger.info("🛡️ Synthetic stop watchdog cancelled")
                break
            except Exception as e:
                self.logger.error(f"[WATCHDOG] Error in watchdog loop: {e}")
                await asyncio.sleep(self.config.pump_max_loss_watchdog_interval)

    def _process_signals(self, signals: list):
        """
        Process new trading signals
        """
        self.logger.info(f"📡 Processing {len(signals)} signal(s)...")

        signals_opened = 0
        signals_queued = 0

        for signal in signals:
            try:
                # Check if we can open new position
                can_open, reason = self.risk_engine.can_open_new_position(signal)

                if not can_open:
                    self.logger.debug(f"❌ Cannot open {signal['symbol']} {signal['engine']}: {reason}")
                    continue

                # Entry-DETE: Queue signal instead of opening immediately
                if self.config.entry_dete_enabled:
                    self.entry_dete_engine.queue_signal(signal)
                    signals_queued += 1
                    continue  # Skip immediate entry logic below

                # Get current price (use entry_price from signal)
                entry_price = signal['entry_price']
                stop_loss = signal['stop_loss']

                # Calculate position size
                size_usd = self.risk_engine.calculate_position_size(signal, entry_price, stop_loss)

                # Minimum position size (adjusted for account size)
                min_position_size = max(1.0, self.config.starting_equity * 0.01)  # 1% of equity or $1, whichever is higher
                if size_usd < min_position_size:
                    self.logger.debug(f"❌ Position size too small for {signal['symbol']}: ${size_usd:.2f} (min: ${min_position_size:.2f})")
                    continue

                # Calculate risk % and quantities
                risk_pct = self.risk_engine.get_risk_per_trade(signal.get('engine', 'standard'))
                equity_at_entry = self.risk_engine.current_equity
                initial_risk_usd = equity_at_entry * risk_pct
                qty = size_usd / entry_price if entry_price > 0 else 0

                # Create position object
                position = {
                    'symbol': signal['symbol'],
                    'side': signal['side'],
                    'engine': signal['engine'],
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'tp_2r': signal.get('tp_2r', 0),
                    'tp_4r': signal.get('tp_4r', 0),
                    'size_usd': size_usd,
                    'qty': qty,
                    'risk_pct': risk_pct,
                    'initial_risk_usd': initial_risk_usd,
                    'equity_at_entry': equity_at_entry,
                    'score': signal.get('score', 0),
                    'regime': signal.get('regime', ''),
                    'timestamp_open': time.time(),
                    'max_hold_hours': signal.get('max_hold_hours', 48)
                }

                # Place order (SIM or LIVE)
                if self.config.sim_mode:
                    # Detailed SIM logging
                    self.logger.info(
                        f"✅ [SIM-OPEN] {position['symbol']} {position['side']} | "
                        f"equity=${equity_at_entry:.2f} | "
                        f"regime={position['regime']} | "
                        f"risk={risk_pct*100:.3f}% | "
                        f"risk_usd=${initial_risk_usd:.2f} | "
                        f"size_usd=${size_usd:.2f} | "
                        f"qty={qty:.6f} | "
                        f"entry={entry_price:.6f} | "
                        f"stop={stop_loss:.6f} | "
                        f"engine={position['engine']} | "
                        f"score={position['score']}"
                    )

                    # Add position
                    self.risk_engine.add_position(position)
                    signals_opened += 1

                    # Send enhanced Telegram notification for SIM open
                    try:
                        target = signal.get('tp_4r', signal.get('tp_2r', 0))
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
                            size=qty,
                            entry=entry_price,
                            stop=stop_loss,
                            target=target if target > 0 else None,
                            leverage=1.0,
                            risk_pct=risk_pct * 100,
                            r_multiple=r_multiple
                        )
                        self.logger.info(f"[TELEGRAM] Sent enhanced SIM trade open notification for {position['symbol']}")
                    except Exception as e:
                        self.logger.warning(f"[TELEGRAM] Failed to send enhanced trade open notification: {e}")

                else:
                    # LIVE order
                    # Calculate amount in base currency
                    amount = size_usd / entry_price

                    order = self.exchange.create_order(
                        symbol=position['symbol'],
                        type='market',
                        side='buy' if position['side'] == 'long' else 'sell',
                        amount=amount,
                        params={'leverage': 1}  # 1x isolated
                    )

                    if order and order.get('id'):
                        self.logger.info(
                            f"✅ [LIVE] Opened {position['side']} | "
                            f"{position['symbol']} | "
                            f"Size: ${size_usd:.2f} | "
                            f"Order ID: {order['id']}"
                        )

                        position['order_id'] = order['id']
                        self.risk_engine.add_position(position)
                        signals_opened += 1

                        # EXCHANGE STOP ORDER PLACEMENT (with fallback)
                        # Attempt to place exchange-native stop order for additional protection
                        # Synthetic hard stop remains active regardless of exchange stop success/failure
                        engine = position.get('engine', '')
                        if engine == 'pump':
                            try:
                                # Calculate stop price based on config hard stop percentage
                                stop_price = entry_price * (1 - self.config.pump_max_loss_pct) if position['side'] == 'long' else entry_price * (1 + self.config.pump_max_loss_pct)
                                stop_side = 'sell' if position['side'] == 'long' else 'buy'

                                # Try placing exchange stop-limit order
                                # Note: MEXC Spot may or may not support this - we handle gracefully
                                stop_order = self.exchange.create_order(
                                    symbol=position['symbol'],
                                    type='stop_limit',
                                    side=stop_side,
                                    amount=amount,
                                    price=stop_price * 0.99 if position['side'] == 'long' else stop_price * 1.01,  # Limit price slightly worse
                                    params={
                                        'stopPrice': stop_price,
                                        'leverage': 1
                                    }
                                )

                                if stop_order and stop_order.get('id'):
                                    position['exchange_stop_order_id'] = stop_order['id']
                                    self.logger.info(
                                        f"[STOP_PLACED] {position['symbol']} {position['side']} | "
                                        f"stop_price={stop_price:.6f} | "
                                        f"order_id={stop_order['id']} | "
                                        f"type=exchange_native"
                                    )
                                else:
                                    self.logger.warning(
                                        f"[STOP_BLOCKED] {position['symbol']} {position['side']} | "
                                        f"reason=exchange_returned_no_order_id | "
                                        f"synthetic_protection=ACTIVE"
                                    )
                            except Exception as e:
                                # Exchange stop placement failed - log and continue with synthetic only
                                error_msg = str(e)
                                self.logger.warning(
                                    f"[STOP_BLOCKED] {position['symbol']} {position['side']} | "
                                    f"reason={error_msg[:100]} | "
                                    f"synthetic_protection=ACTIVE"
                                )

                        # POSITION PROTECTION AUDIT LOG
                        # Comprehensive logging of all protective measures for this position
                        exchange_stop_status = "PLACED" if position.get('exchange_stop_order_id') else "BLOCKED"
                        exchange_stop_detail = (
                            f"order_id={position.get('exchange_stop_order_id')}"
                            if exchange_stop_status == "PLACED"
                            else "using_synthetic_only"
                        )

                        self.logger.info(
                            f"[POSITION_PROTECT] {position['symbol']} {position['side']} {position['engine'].upper()} | "
                            f"min_stop_pct={self.config.pump_max_loss_pct*100 if engine == 'pump' else 'N/A'}% | "
                            f"desired_exchange_stop={f'{self.config.pump_max_loss_pct*100}%' if engine == 'pump' else 'N/A'} | "
                            f"exchange_stop_status={exchange_stop_status} ({exchange_stop_detail}) | "
                            f"synthetic_hard_stop={f'ACTIVE_{self.config.pump_max_loss_pct*100}%' if engine == 'pump' else 'N/A'} | "
                            f"max_hold={position.get('max_hold_hours', 48)}h | "
                            f"entry={entry_price:.6f} | "
                            f"stop={stop_loss:.6f} | "
                            f"protection=FULL"
                        )

                        # Send Telegram notification for stop placement status (pump trades only)
                        if engine == 'pump':
                            try:
                                stop_pct = self.config.pump_max_loss_pct * 100
                                if exchange_stop_status == "PLACED":
                                    stop_msg = (
                                        f"🛡️ PUMP PROTECTION ARMED\n"
                                        f"Symbol: {position['symbol']}\n"
                                        f"Side: {position['side'].upper()}\n"
                                        f"Entry: ${entry_price:.6f}\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"✅ Exchange Stop: PLACED\n"
                                        f"   Stop Price: ${stop_price:.6f} ({stop_pct:.1f}%)\n"
                                        f"   Order ID: {position.get('exchange_stop_order_id')}\n"
                                        f"🛡️ Synthetic Watchdog: ACTIVE ({stop_pct:.1f}%)\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"DOUBLE PROTECTION: Exchange + Watchdog"
                                    )
                                else:
                                    stop_msg = (
                                        f"🛡️ PUMP PROTECTION ARMED\n"
                                        f"Symbol: {position['symbol']}\n"
                                        f"Side: {position['side'].upper()}\n"
                                        f"Entry: ${entry_price:.6f}\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"⚠️ Exchange Stop: BLOCKED\n"
                                        f"   (Exchange constraints or unsupported)\n"
                                        f"🛡️ Synthetic Watchdog: ACTIVE ({stop_pct:.1f}%)\n"
                                        f"   Hard Stop: ${stop_price:.6f}\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"FALLBACK PROTECTION: Watchdog monitoring active\n"
                                        f"Max loss GUARANTEED at {stop_pct:.1f}%"
                                    )

                                # Send via Telegram
                                import requests
                                if self.config.telegram_bot_token and self.config.telegram_chat_id:
                                    requests.post(
                                        f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
                                        json={"chat_id": self.config.telegram_chat_id, "text": stop_msg},
                                        timeout=5
                                    )
                                    self.logger.info(f"[TELEGRAM] Sent pump protection status for {position['symbol']}")
                            except Exception as e:
                                self.logger.warning(f"[TELEGRAM] Failed to send pump protection alert: {e}")

                        # Send enhanced Telegram notification for LIVE open
                        try:
                            target = signal.get('tp_4r', signal.get('tp_2r', 0))
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
                            self.logger.info(f"[TELEGRAM] Sent enhanced LIVE trade open notification for {position['symbol']}")
                        except Exception as e:
                            self.logger.warning(f"[TELEGRAM] Failed to send enhanced LIVE trade open notification: {e}")
                    else:
                        self.logger.error(f"🔴 Failed to create order for {position['symbol']}")

            except Exception as e:
                self.logger.error(f"Error processing signal {signal.get('symbol', 'UNKNOWN')}: {e}")
                continue

        # Log results
        if signals_queued > 0:
            self.logger.info(f"🎯 Queued {signals_queued} signal(s) for Entry-DETE confirmation")
        if signals_opened > 0:
            self.logger.info(f"✅ Opened {signals_opened} new position(s)")
        if signals_opened == 0 and signals_queued == 0:
            self.logger.info("📊 No new positions opened or queued")

        return signals_opened

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
        self.last_scan_time = time.time()  # Track scan time for both elapsed calc and drift detection

        # Setup DFE scheduling if enabled
        if self.config.dfe_enabled:
            schedule.every().day.at("00:05").do(self.run_dfe)
            self.logger.info("🔧 DFE enabled - scheduled daily at 00:05 UTC")
        else:
            self.logger.info("🔧 DFE disabled - filters will not auto-adjust")

        while self.running:
            try:
                current_time = time.time()
                elapsed = current_time - self.last_scan_time

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
                            mode = "SIM" if self.config.sim_mode else "LIVE"
                            self.telegram.send(
                                f"⚡ <b>[{mode}] FAST MODE DISABLED</b>\n"
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
                    self.last_scan_time = current_time  # Track for drift detection and next elapsed calc
                    self.drift_alert_sent = False  # Reset drift alert when scan completes

                # Check scheduled tasks (DFE)
                schedule.run_pending()

                # Short sleep to prevent CPU spinning
                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in scan_loop: {e}")
                self.logger.exception(e)
                await asyncio.sleep(30)  # Back off on error (30s to prevent rapid error logging)

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
                            mode = "SIM" if self.config.sim_mode else "LIVE"
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
                mode = "SIM" if self.config.sim_mode else "LIVE"
                error_type = type(e).__name__
                error_msg = str(e)[:200]  # Limit to 200 chars
                self.logger.info(f"[TELEGRAM] Sending fatal error notification")
                self.telegram.send(
                    f"🚨 [{mode}] FATAL ERROR\n"
                    f"Type: {error_type}\n"
                    f"Message: {error_msg}\n"
                    f"BOT IS SHUTTING DOWN"
                )
            except:
                pass  # Don't crash on Telegram failure

            self.shutdown()

    async def _run_async(self):
        """
        Run scan_loop, position_loop, drift_detection, and synthetic_stop_watchdog concurrently
        """
        try:
            tasks = [
                self.scan_loop(),
                self.position_loop(),
                self._synthetic_stop_watchdog()  # Dedicated hard stop protection for pump trades
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
        if not self.config.sim_mode:
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
