"""
Enhanced Telegram Alert System for Alpha Sniper V4.2

Provides detailed, production-ready alerts for all trading events:
- Startup alerts
- Regime changes
- Trade open/close with full metrics
- Daily summaries
- Crash/error alerts

Usage:
    from utils.telegram_alerts import TelegramAlertManager
    alert_mgr = TelegramAlertManager(config, logger, telegram_notifier)
    alert_mgr.send_trade_open(...)
    alert_mgr.send_trade_close(...)
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class TelegramAlertManager:
    """
    Enhanced Telegram alert manager with detailed, formatted notifications
    """
    def __init__(self, config, logger, telegram_notifier):
        """
        Args:
            config: Bot configuration object
            logger: Logger instance
            telegram_notifier: TelegramNotifier instance (utils/telegram.py)
        """
        self.config = config
        self.logger = logger
        self.telegram = telegram_notifier

        # Daily stats tracking
        self.daily_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.daily_pnl = 0.0
        self.daily_max_drawdown = 0.0
        self.day_start_equity = 0.0
        self.last_summary_day = datetime.now(timezone.utc).day

    def send_startup(self, mode: str, pump_only: bool, data_source: str,
                     equity: float, regime: str):
        """
        Send enhanced startup notification

        Args:
            mode: 'LIVE' or 'SIM'
            pump_only: True if pump-only mode
            data_source: 'LIVE', 'FAKE', etc.
            equity: Starting equity
            regime: Current regime (BULL/BEAR/SIDEWAYS/UNKNOWN)
        """
        pump_str = ' (PUMP-ONLY)' if pump_only else ''

        msg = (
            f"🚀 <b>Alpha Sniper V4.2 Started</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Mode:</b> {mode}{pump_str}\n"
            f"<b>Data:</b> {data_source}\n"
            f"<b>Starting Equity:</b> ${equity:.2f}\n"
            f"<b>Regime:</b> {regime}\n"
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        )

        if mode == 'LIVE':
            msg += f"\n💰 <i>Equity will sync from MEXC shortly</i>"

        self.telegram.send(msg)
        self.logger.info("[TELEGRAM] Startup alert sent")

    def send_equity_sync(self, config_equity: float, mexc_balance: float):
        """
        Send equity sync notification

        Args:
            config_equity: Equity from config (baseline)
            mexc_balance: Actual MEXC balance
        """
        diff = mexc_balance - config_equity
        diff_pct = (diff / config_equity * 100) if config_equity > 0 else 0

        msg = (
            f"💰 <b>Equity Synced from MEXC</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Config Baseline:</b> ${config_equity:.2f}\n"
            f"<b>MEXC Balance:</b> ${mexc_balance:.2f}\n"
            f"<b>Difference:</b> ${diff:+.2f} ({diff_pct:+.1f}%)\n"
        )

        self.telegram.send(msg)
        self.logger.info("[TELEGRAM] Equity sync alert sent")

    def send_regime_change(self, old_regime: str, new_regime: str, btc_price: float):
        """
        Send regime change notification

        Args:
            old_regime: Previous regime
            new_regime: New regime
            btc_price: Current BTC price
        """
        emoji_map = {
            'BULL': '📈',
            'BEAR': '📉',
            'SIDEWAYS': '↔️',
            'UNKNOWN': '❓'
        }

        old_emoji = emoji_map.get(old_regime, '❓')
        new_emoji = emoji_map.get(new_regime, '❓')

        msg = (
            f"{new_emoji} <b>Regime Change</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>From:</b> {old_emoji} {old_regime}\n"
            f"<b>To:</b> {new_emoji} {new_regime}\n"
            f"<b>BTC Price:</b> ${btc_price:,.2f}\n"
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        )

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Regime change alert sent: {old_regime} -> {new_regime}")

    def send_trade_open(self, symbol: str, side: str, engine: str, regime: str,
                        size: float, entry: float, stop: float, target: Optional[float],
                        leverage: float, risk_pct: float, r_multiple: Optional[float] = None):
        """
        Send trade OPEN notification with full details

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            side: 'LONG' or 'SHORT'
            engine: 'PUMP', 'CORE', 'SHORT', 'BEAR_MICRO'
            regime: Current regime
            size: Position size in base asset
            entry: Entry price
            stop: Stop-loss price
            target: Take-profit price (optional)
            leverage: Leverage used
            risk_pct: Risk as percentage of equity
            r_multiple: Expected R multiple (optional)
        """
        side_emoji = '🟢' if side == 'LONG' else '🔴'

        notional = size * entry
        stop_distance_pct = abs((entry - stop) / entry * 100) if entry > 0 else 0

        msg = (
            f"{side_emoji} <b>[{engine}] TRADE OPENED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side} ×{leverage:.1f}\n"
            f"<b>Regime:</b> {regime}\n"
            f"<b>Entry:</b> ${entry:.6f}\n"
            f"<b>Size:</b> {size:.4f}\n"
            f"<b>Notional:</b> ${notional:.2f}\n"
            f"<b>Stop:</b> ${stop:.6f} ({stop_distance_pct:.2f}%)\n"
        )

        if target:
            target_distance_pct = abs((target - entry) / entry * 100) if entry > 0 else 0
            msg += f"<b>Target:</b> ${target:.6f} ({target_distance_pct:.2f}%)\n"

        msg += f"<b>Risk:</b> {risk_pct:.3f}% of equity\n"

        if r_multiple:
            msg += f"<b>R Multiple:</b> {r_multiple:.2f}R\n"

        msg += f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Trade open alert sent: {symbol} {side} @ {entry}")

    def send_trade_close(self, symbol: str, side: str, engine: str, regime: str,
                         entry: float, exit_price: float, size: float,
                         pnl_usd: float, pnl_pct: float, r_multiple: float,
                         hold_time: str, reason: str):
        """
        Send trade CLOSE notification with full details

        Args:
            symbol: Trading pair
            side: 'LONG' or 'SHORT'
            engine: 'PUMP', 'CORE', 'SHORT', 'BEAR_MICRO'
            regime: Current regime
            entry: Entry price
            exit_price: Exit price
            size: Position size
            pnl_usd: P&L in USD
            pnl_pct: P&L as percentage
            r_multiple: Actual R multiple achieved
            hold_time: Time held (e.g., '1h 23m')
            reason: Exit reason ('TP hit', 'Stop hit', 'Time exit', etc.)
        """
        # Determine emoji based on P&L
        if pnl_usd > 0:
            emoji = '💚'  # Win
        elif pnl_usd < 0:
            emoji = '🔴'  # Loss
        else:
            emoji = '⚪'  # Breakeven

        # Exit reason emoji
        reason_emoji = {
            'TP hit': '🎯',
            'Stop hit': '🛑',
            'Time exit': '⏰',
            'Manual close': '✋',
            'Timeout': '⏰',
            'Max hold': '⏰'
        }.get(reason, '🔵')

        msg = (
            f"{emoji} <b>[{engine}] TRADE CLOSED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Regime:</b> {regime}\n"
            f"<b>Entry:</b> ${entry:.6f}\n"
            f"<b>Exit:</b> ${exit_price:.6f}\n"
            f"<b>Size:</b> {size:.4f}\n"
            f"<b>P&L:</b> ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
            f"<b>R Multiple:</b> {r_multiple:+.2f}R\n"
            f"<b>Hold Time:</b> {hold_time}\n"
            f"<b>Reason:</b> {reason_emoji} {reason}\n"
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        )

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Trade close alert sent: {symbol} {pnl_usd:+.2f} USD")

        # Update daily stats
        self.daily_trades += 1
        self.daily_pnl += pnl_usd
        if pnl_usd > 0:
            self.daily_wins += 1
        elif pnl_usd < 0:
            self.daily_losses += 1

    def send_daily_summary(self, final_equity: float, open_positions: int):
        """
        Send daily trading summary

        Args:
            final_equity: Ending equity for the day
            open_positions: Number of open positions
        """
        # Calculate daily P&L
        day_pnl_pct = ((final_equity - self.day_start_equity) / self.day_start_equity * 100) if self.day_start_equity > 0 else 0

        # Calculate win rate
        total_closed = self.daily_wins + self.daily_losses
        win_rate = (self.daily_wins / total_closed * 100) if total_closed > 0 else 0

        # Determine emoji based on daily P&L
        if self.daily_pnl > 0:
            day_emoji = '📈'
        elif self.daily_pnl < 0:
            day_emoji = '📉'
        else:
            day_emoji = '➖'

        msg = (
            f"{day_emoji} <b>Daily Summary</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Date:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"<b>Total Trades:</b> {self.daily_trades}\n"
            f"<b>Wins/Losses:</b> {self.daily_wins}W / {self.daily_losses}L\n"
            f"<b>Win Rate:</b> {win_rate:.1f}%\n"
            f"<b>Day P&L:</b> ${self.daily_pnl:+.2f} ({day_pnl_pct:+.2f}%)\n"
            f"<b>Max Drawdown:</b> {self.daily_max_drawdown:.2f}%\n"
            f"<b>Final Equity:</b> ${final_equity:.2f}\n"
            f"<b>Open Positions:</b> {open_positions}\n"
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        )

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Daily summary sent: {self.daily_trades} trades, ${self.daily_pnl:+.2f}")

        # Reset daily stats
        self._reset_daily_stats(final_equity)

    def send_crash_alert(self, exception_type: str, exception_msg: str, traceback_info: str = ""):
        """
        Send crash/critical error alert

        Args:
            exception_type: Type of exception (e.g., 'RuntimeError')
            exception_msg: Exception message
            traceback_info: Optional traceback snippet
        """
        mode = "SIM" if self.config.sim_mode else "LIVE"

        msg = (
            f"🚨 <b>[{mode}] CRITICAL ERROR</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Type:</b> {exception_type}\n"
            f"<b>Message:</b> {exception_msg[:300]}\n"  # Limit to 300 chars
        )

        if traceback_info:
            msg += f"<b>Traceback:</b>\n<code>{traceback_info[:500]}</code>\n"  # Limit to 500 chars

        msg += (
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
            f"\n⚠️ <i>Check logs immediately</i>"
        )

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Crash alert sent: {exception_type}")

    def send_daily_loss_limit_hit(self, loss_pct: float, max_loss_pct: float):
        """
        Send alert when daily loss limit is hit

        Args:
            loss_pct: Current daily loss percentage
            max_loss_pct: Maximum allowed loss percentage
        """
        msg = (
            f"🚨 <b>DAILY LOSS LIMIT HIT</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Current Loss:</b> {loss_pct:.2f}%\n"
            f"<b>Max Allowed:</b> {max_loss_pct:.2f}%\n"
            f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
            f"\n🛑 <b>Trading stopped for today</b>\n"
            f"Will resume at UTC 00:00"
        )

        self.telegram.send(msg)
        self.logger.info(f"[TELEGRAM] Daily loss limit alert sent: {loss_pct:.2f}%")

    def check_and_send_daily_summary(self, current_equity: float, open_positions: int):
        """
        Check if day has changed and send daily summary if needed

        Args:
            current_equity: Current equity
            open_positions: Number of open positions
        """
        current_day = datetime.now(timezone.utc).day

        if current_day != self.last_summary_day:
            # Day has changed, send summary
            self.send_daily_summary(current_equity, open_positions)
            self.last_summary_day = current_day

    def _reset_daily_stats(self, starting_equity: float):
        """Reset daily statistics for new day"""
        self.daily_trades = 0
        self.daily_wins = 0
        self.daily_losses = 0
        self.daily_pnl = 0.0
        self.daily_max_drawdown = 0.0
        self.day_start_equity = starting_equity

    def update_drawdown(self, current_equity: float):
        """
        Update daily max drawdown tracking

        Args:
            current_equity: Current equity
        """
        if self.day_start_equity > 0:
            current_drawdown = ((current_equity - self.day_start_equity) / self.day_start_equity * 100)
            if current_drawdown < 0:  # Negative = drawdown
                self.daily_max_drawdown = min(self.daily_max_drawdown, current_drawdown)
