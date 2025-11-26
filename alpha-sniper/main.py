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

from config import get_config
from utils import setup_logger
from utils.telegram import TelegramNotifier
from utils import helpers
from exchange import ExchangeClient
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

        # Initialize components
        self.telegram = TelegramNotifier(self.config, self.logger)
        self.exchange = ExchangeClient(self.config, self.logger)
        self.risk_engine = RiskEngine(self.config, self.exchange, self.logger, self.telegram)
        self.scanner = Scanner(self.exchange, self.risk_engine, self.config, self.logger)

        # Load existing positions
        self.risk_engine.load_positions('positions.json')

        # Send startup notification
        if not self.config.sim_mode:
            self.telegram.send(f"🚀 Alpha Sniper V4.2 started in {mode_str} mode")

        # Running flag
        self.running = True

    def trading_cycle(self):
        """
        Main trading cycle - runs every scan interval
        """
        try:
            self.logger.info("")
            self.logger.info("🔄" + "=" * 58)
            self.logger.info("🔄 New trading cycle starting...")
            self.logger.info("🔄" + "=" * 58)

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

                if size_usd < 10:  # Minimum position size
                    self.logger.debug(f"❌ Position size too small for {signal['symbol']}: ${size_usd:.2f}")
                    continue

                # Calculate risk %
                risk_pct = self.risk_engine.get_risk_per_trade(signal.get('engine', 'standard'))

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
                    'risk_pct': risk_pct,
                    'score': signal.get('score', 0),
                    'regime': signal.get('regime', ''),
                    'timestamp_open': time.time(),
                    'max_hold_hours': signal.get('max_hold_hours', 48)
                }

                # Place order (SIM or LIVE)
                if self.config.sim_mode:
                    # Simulated order - just log
                    self.logger.info(
                        f"✅ [SIM] Opening {position['side']} | "
                        f"{position['symbol']} | "
                        f"Size: ${size_usd:.2f} | "
                        f"Entry: ${entry_price:.6f} | "
                        f"SL: ${stop_loss:.6f} | "
                        f"Score: {position['score']} | "
                        f"Engine: {position['engine']}"
                    )

                    # Add position
                    self.risk_engine.add_position(position)
                    signals_opened += 1

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

                        # Send Telegram alert
                        self.telegram.send(
                            f"✅ Trade opened\n"
                            f"{position['symbol']} {position['side']}\n"
                            f"Size: ${size_usd:.2f}\n"
                            f"Entry: ${entry_price:.6f}\n"
                            f"Engine: {position['engine']}"
                        )
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
    bot = AlphaSniperBot()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        bot.logger.info("")
        bot.logger.info("👋 Received shutdown signal")
        bot.running = False
        bot.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot
    bot.run()


if __name__ == "__main__":
    main()
