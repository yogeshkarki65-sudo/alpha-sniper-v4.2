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

        self.telegram.send(msg, description="Startup")

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

        self.telegram.send(msg, description="Equity Sync")

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

        self.telegram.send(msg, description=f"Regime Change ({old_regime}→{new_regime})")

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

        self.telegram.send(msg, description=f"Trade Open ({symbol} {side})")

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

        self.telegram.send(msg, description=f"Trade Close ({symbol} {emoji})")
        self.logger.info(f"[TELEGRAM] Trade close alert sent: {symbol} {pnl_usd:+.2f} USD")

        # Update daily stats
        self.daily_trades += 1
        self.daily_pnl += pnl_usd
        if pnl_usd > 0:
            self.daily_wins += 1
        elif pnl_usd < 0:
            self.daily_losses += 1

    def send_daily_summary(self, final_equity: float, open_positions: int, trades_list: list = None):
        """
        Send daily trading summary with best/worst trades

        Args:
            final_equity: Ending equity for the day
            open_positions: Number of open positions
            trades_list: List of trade dictionaries from closed_trades_today (optional)
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
        )

        # Add best/worst trades if available
        if trades_list and len(trades_list) > 0:
            best_trade = max(trades_list, key=lambda t: t.get('pnl_usd', 0))
            worst_trade = min(trades_list, key=lambda t: t.get('pnl_usd', 0))

            best_pnl = best_trade.get('pnl_usd', 0)
            worst_pnl = worst_trade.get('pnl_usd', 0)
            best_symbol = best_trade.get('symbol', 'UNKNOWN')
            worst_symbol = worst_trade.get('symbol', 'UNKNOWN')

            msg += (
                f"<b>Best Trade:</b> {best_symbol} ${best_pnl:+.2f}\n"
                f"<b>Worst Trade:</b> {worst_symbol} ${worst_pnl:+.2f}\n"
            )

        msg += f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"

        self.telegram.send(msg, description="Daily Summary")
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

        self.telegram.send(msg, description=f"Crash Alert ({exception_type})")
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

        self.telegram.send(msg, description="Daily Loss Limit Hit")
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

    def send_scan_summary(self, regime: str, enabled_engines: list, universe_count: int,
                         signals_count: int, top_signals: list = None, scan_time_ms: float = 0):
        """
        Send scan cycle start summary

        Args:
            regime: Current market regime
            enabled_engines: List of enabled engine names
            universe_count: Number of symbols scanned
            signals_count: Total signals generated
            top_signals: List of top 3 signals [(symbol, engine, score), ...]
            scan_time_ms: Scan duration in milliseconds
        """
        if not getattr(self.config, 'telegram_scan_summary', True):
            return  # Disabled

        engines_str = ', '.join(enabled_engines) if enabled_engines else 'None'

        msg = (
            f"🔍 <b>Scan Cycle Complete</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Regime:</b> {regime}\n"
            f"<b>Enabled Engines:</b> {engines_str}\n"
            f"<b>Universe:</b> {universe_count} symbols\n"
            f"<b>Signals:</b> {signals_count} total\n"
        )

        if scan_time_ms > 0:
            msg += f"<b>Scan Time:</b> {scan_time_ms:.0f}ms\n"

        if top_signals and len(top_signals) > 0:
            msg += f"\n<b>Top Signals:</b>\n"
            for symbol, engine, score in top_signals[:3]:
                msg += f"  • {symbol} ({engine}) - {score}\n"
        elif signals_count == 0:
            msg += f"\n<i>No signals above threshold</i>\n"

        msg += f"\n🕐 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"

        self.telegram.send(msg, description="Scan Summary")

    def send_why_no_trade(self, regime: str, reasons: list):
        """
        Send explanation why no trade was taken

        Args:
            regime: Current market regime
            reasons: List of reasons (strings)
        """
        if not getattr(self.config, 'telegram_why_no_trade', True):
            return  # Disabled

        msg = (
            f"❓ <b>Why No Trade?</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Regime:</b> {regime}\n"
            f"\n<b>Reasons:</b>\n"
        )

        for reason in reasons:
            msg += f"  • {reason}\n"

        msg += f"\n🕐 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"

        self.telegram.send(msg, description="Why No Trade")

    def send_position_entry_detailed(self, symbol: str, side: str, engine: str, regime: str,
                                    score: float, entry_price: float, qty: float, size_usd: float,
                                    stop_price: float, virtual_max_loss_pct: float,
                                    min_stop_pct: float, max_hold_hours: float,
                                    triggers: dict = None, liquidity_info: dict = None):
        """
        Send detailed position entry notification with full context

        Args:
            symbol: Trading symbol
            side: 'LONG' or 'SHORT'
            engine: Signal engine name
            regime: Market regime
            score: Signal score
            entry_price: Entry price
            qty: Position quantity
            size_usd: Position size in USD
            stop_price: Stop loss price
            virtual_max_loss_pct: Virtual max loss percentage (e.g., 0.02 for 2%)
            min_stop_pct: Minimum stop percentage
            max_hold_hours: Maximum hold time in hours
            triggers: Optional dict with trigger info (baseline, dip_pct, etc.)
            liquidity_info: Optional dict with liquidity scaling info
        """
        if not getattr(self.config, 'telegram_trade_alerts', True):
            return  # Disabled

        stop_pct = abs((stop_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        msg = (
            f"{'🟢' if side == 'LONG' else '🔴'} <b>POSITION OPENED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Engine:</b> {engine.upper()}\n"
            f"<b>Score:</b> {score:.1f}\n"
            f"<b>Regime:</b> {regime}\n"
            f"\n"
            f"<b>Entry:</b> ${entry_price:.6f}\n"
            f"<b>Quantity:</b> {qty:.4f}\n"
            f"<b>Size:</b> ${size_usd:.2f}\n"
            f"\n"
            f"<b>Stop Loss:</b> ${stop_price:.6f} ({stop_pct:.2f}%)\n"
            f"<b>Virtual Max Loss:</b> {virtual_max_loss_pct*100:.1f}%\n"
            f"<b>Min Stop:</b> {min_stop_pct*100:.1f}%\n"
            f"<b>Max Hold:</b> {max_hold_hours:.0f}h\n"
        )

        if triggers:
            msg += f"\n<b>Triggers:</b>\n"
            if 'baseline' in triggers:
                msg += f"  • Baseline: ${triggers['baseline']:.6f}\n"
            if 'dip_pct' in triggers:
                msg += f"  • Dip: {triggers['dip_pct']:.2f}%\n"

        if liquidity_info:
            requested = liquidity_info.get('requested_usd', size_usd)
            adjusted = liquidity_info.get('adjusted_usd', size_usd)
            if requested != adjusted:
                scaling_pct = (adjusted / requested * 100) if requested > 0 else 100
                msg += f"\n<b>Liquidity Scaling:</b>\n"
                msg += f"  • Requested: ${requested:.2f}\n"
                msg += f"  • Adjusted: ${adjusted:.2f} ({scaling_pct:.0f}%)\n"
                if 'reason' in liquidity_info:
                    msg += f"  • Reason: {liquidity_info['reason']}\n"

        msg += f"\n🕐 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"

        # Truncate if too long
        max_len = getattr(self.config, 'telegram_max_msg_len', 3500)
        if len(msg) > max_len:
            msg = msg[:max_len-20] + "\n...(truncated)"

        self.telegram.send(msg, description=f"Entry: {symbol}")

    def send_position_exit_detailed(self, symbol: str, side: str, engine: str,
                                   entry_price: float, exit_price: float,
                                   qty: float, pnl_usd: float, pnl_pct: float,
                                   hold_time_hours: float, reason: str,
                                   trigger_details: dict = None):
        """
        Send detailed position exit notification

        Args:
            symbol: Trading symbol
            side: 'LONG' or 'SHORT'
            engine: Signal engine name
            entry_price: Entry price
            exit_price: Exit price
            qty: Position quantity
            pnl_usd: Realized PnL in USD
            pnl_pct: Realized PnL percentage
            hold_time_hours: Hold time in hours
            reason: Exit reason
            trigger_details: Optional dict with trigger thresholds
        """
        if not getattr(self.config, 'telegram_trade_alerts', True):
            return  # Disabled

        is_profit = pnl_usd >= 0
        emoji = "💰" if is_profit else "📉"

        msg = (
            f"{emoji} <b>POSITION CLOSED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Engine:</b> {engine.upper()}\n"
            f"\n"
            f"<b>Entry:</b> ${entry_price:.6f}\n"
            f"<b>Exit:</b> ${exit_price:.6f}\n"
            f"<b>Quantity:</b> {qty:.4f}\n"
            f"\n"
            f"<b>PnL:</b> ${pnl_usd:+.2f} ({pnl_pct:+.2f}%)\n"
            f"<b>Hold Time:</b> {hold_time_hours:.1f}h\n"
            f"<b>Reason:</b> {reason}\n"
        )

        if trigger_details:
            msg += f"\n<b>Trigger Details:</b>\n"
            for key, value in trigger_details.items():
                msg += f"  • {key}: {value}\n"

        msg += f"\n🕐 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"

        # Update daily stats
        self.daily_trades += 1
        self.daily_pnl += pnl_usd
        if pnl_usd >= 0:
            self.daily_wins += 1
        else:
            self.daily_losses += 1

        self.telegram.send(msg, description=f"Exit: {symbol}")

