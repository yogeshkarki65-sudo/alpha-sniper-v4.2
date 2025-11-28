"""
Alpha Sniper V4.2 - Main Entry Point
Full-Dynamic-Safe-Bull Trading Bot

Features:
- SIM and LIVE modes
- Regime-based position sizing
- Multiple signal engines (long, short, pump, bear_micro)
- Safe risk management
- Telegram alerts
"""
import time
import schedule
import signal
import sys
import argparse
from datetime import datetime, timezone

from config import get_config
from utils import setup_logger
from utils.telegram import TelegramNotifier
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

        # Initialize components
        self.telegram = TelegramNotifier(self.config, self.logger)
        self.exchange = create_exchange(self.config, self.logger)  # Use factory
        self.risk_engine = RiskEngine(self.config, self.exchange, self.logger, self.telegram)
        self.scanner = Scanner(self.exchange, self.risk_engine, self.config, self.logger)

        # Rate limiting for error notifications (15 min cooldown)
        self.last_error_notification = 0
        self.error_notification_cooldown = 900  # 15 minutes in seconds

        # Send startup notification
        sim_data_source = getattr(self.config, 'sim_data_source', 'FAKE')
        regime = self.risk_engine.current_regime if self.risk_engine.current_regime else 'UNKNOWN'
        startup_msg = (
            f"🚀 Alpha Sniper V4.2 started\n"
            f"Mode: {'SIM' if self.config.sim_mode else 'LIVE'}\n"
            f"Data: {sim_data_source if self.config.sim_mode else 'LIVE'}\n"
            f"Starting Equity: ${self.config.starting_equity:.2f}\n"
            f"Regime: {regime}"
        )
        self.logger.info(f"[TELEGRAM] Sending startup notification")
        self.telegram.send(startup_msg)

        # Load existing positions
        self.risk_engine.load_positions('positions.json')

        # Running flag
        self.running = True

    def trading_cycle(self):
        """
        Main trading cycle - runs every scan interval
        """
        try:
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

            # 2. Update regime
            self.risk_engine.update_regime()

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
            self.risk_engine.save_positions('positions.json')

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
                        f"🚨 CRITICAL ERROR\n"
                        f"Mode: {mode}\n"
                        f"Type: {error_type}\n"
                        f"Message: {error_msg}\n"
                        f"Bot will attempt to continue..."
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

    def _process_signals(self, signals: list):
        """
        Process new trading signals
        """
        self.logger.info(f"📡 Processing {len(signals)} signal(s)...")

        signals_opened = 0

        for signal in signals:
            try:
                # Check if we can open new position
                can_open, reason = self.risk_engine.can_open_new_position(signal)

                if not can_open:
                    self.logger.debug(f"❌ Cannot open {signal['symbol']} {signal['engine']}: {reason}")
                    continue

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

                    # Send Telegram notification for SIM open
                    try:
                        telegram_msg = (
                            f"✅ TRADE OPENED\n"
                            f"Symbol: {position['symbol']} ({position['side']}, engine={position['engine']})\n"
                            f"Regime: {position['regime']}\n"
                            f"Size: ${size_usd:.2f}\n"
                            f"Entry: {entry_price:.4f}\n"
                            f"SL: {stop_loss:.4f}\n"
                            f"Risk: {risk_pct*100:.2f}% (R=1.0)"
                        )
                        self.logger.info(f"[TELEGRAM] Sending trade open notification for {position['symbol']}")
                        self.telegram.send(telegram_msg)
                    except Exception as e:
                        self.logger.warning(f"[TELEGRAM] Failed to send trade open notification: {e}")

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

                        # Send Telegram notification for LIVE open
                        try:
                            telegram_msg = (
                                f"✅ TRADE OPENED [LIVE]\n"
                                f"Symbol: {position['symbol']} ({position['side']}, engine={position['engine']})\n"
                                f"Regime: {position['regime']}\n"
                                f"Size: ${size_usd:.2f}\n"
                                f"Entry: {entry_price:.4f}\n"
                                f"SL: {stop_loss:.4f}\n"
                                f"Risk: {risk_pct*100:.2f}% (R=1.0)"
                            )
                            self.logger.info(f"[TELEGRAM] Sending LIVE trade open notification for {position['symbol']}")
                            self.telegram.send(telegram_msg)
                        except Exception as e:
                            self.logger.warning(f"[TELEGRAM] Failed to send LIVE trade open notification: {e}")
                    else:
                        self.logger.error(f"🔴 Failed to create order for {position['symbol']}")

            except Exception as e:
                self.logger.error(f"Error processing signal {signal.get('symbol', 'UNKNOWN')}: {e}")
                continue

        if signals_opened > 0:
            self.logger.info(f"✅ Opened {signals_opened} new position(s)")
        else:
            self.logger.info("📊 No new positions opened")

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

    def run(self):
        """
        Main run loop with scheduling
        """
        try:
            # Run immediately on start
            self.trading_cycle()

            # Schedule regular runs
            interval_sec = self.config.scan_interval_seconds
            self.logger.info(f"⏰ Scheduling scans every {interval_sec} seconds")

            schedule.every(interval_sec).seconds.do(self.trading_cycle)

            # Main loop
            while self.running:
                schedule.run_pending()
                time.sleep(1)

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
                    f"🚨 FATAL ERROR - BOT STOPPING\n"
                    f"Mode: {mode}\n"
                    f"Type: {error_type}\n"
                    f"Message: {error_msg}\n"
                    f"Bot is shutting down..."
                )
            except:
                pass  # Don't crash on Telegram failure

            self.shutdown()

    def shutdown(self):
        """
        Graceful shutdown
        """
        self.logger.info("🛑 Shutting down...")

        # Save final positions
        self.risk_engine.save_positions('positions.json')

        # Send shutdown notification
        if not self.config.sim_mode:
            self.telegram.send("🛑 Alpha Sniper V4.2 stopped")

        self.logger.info("👋 Goodbye!")
        sys.exit(0)


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
