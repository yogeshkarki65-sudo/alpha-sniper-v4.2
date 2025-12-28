"""
Backtesting portfolio manager

Simulates position management with exact same logic as LIVE mode:
- Position sizing based on R-based risk
- Portfolio heat tracking
- Daily loss limits
- Trailing stops
- Max hold time
"""
from typing import Dict, Optional

import pandas as pd


class BacktestPosition:
    """Represents an open position in backtest"""

    def __init__(
        self,
        symbol: str,
        side: str,
        entry_time: pd.Timestamp,
        entry_price: float,
        size_usd: float,
        stop_loss: float,
        tp_2r: float,
        tp_4r: float,
        max_hold_hours: float,
        signal_data: Dict
    ):
        self.symbol = symbol
        self.side = side
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.size_usd = size_usd
        self.stop_loss = stop_loss
        self.tp_2r = tp_2r
        self.tp_4r = tp_4r
        self.max_hold_hours = max_hold_hours
        self.signal_data = signal_data

        # Tracking
        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl_usd = 0.0
        self.pnl_pct = 0.0
        self.r_multiple = 0.0
        self.peak_price = entry_price
        self.trailing_stop = None

    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL in USD"""
        if self.side == 'long':
            pnl_pct = ((current_price / self.entry_price) - 1)
        else:
            pnl_pct = ((self.entry_price / current_price) - 1)

        return self.size_usd * pnl_pct

    def check_exit(
        self,
        current_time: pd.Timestamp,
        current_price: float,
        trailing_enabled: bool = False,
        trail_pct: float = 0.02
    ) -> Optional[str]:
        """
        Check if position should be exited

        Returns:
            Exit reason if should exit, None otherwise
        """
        # 1. Check stop loss
        if self.side == 'long' and current_price <= self.stop_loss:
            return 'Stop hit'
        if self.side == 'short' and current_price >= self.stop_loss:
            return 'Stop hit'

        # 2. Check TP levels
        if self.side == 'long':
            if current_price >= self.tp_4r:
                return 'TP 4R hit'
            elif current_price >= self.tp_2r:
                return 'TP 2R hit'
        elif self.side == 'short':
            if current_price <= self.tp_4r:
                return 'TP 4R hit'
            elif current_price <= self.tp_2r:
                return 'TP 2R hit'

        # 3. Check trailing stop
        if trailing_enabled and self.side == 'long':
            # Update peak
            if current_price > self.peak_price:
                self.peak_price = current_price
                # Update trailing stop
                self.trailing_stop = self.peak_price * (1 - trail_pct)

            # Check if trailing stop hit
            if self.trailing_stop and current_price <= self.trailing_stop:
                return 'Trailing stop hit'

        # 4. Check max hold time
        hold_hours = (current_time - self.entry_time).total_seconds() / 3600
        if hold_hours >= self.max_hold_hours:
            return 'Max hold time'

        return None

    def close(self, exit_time: pd.Timestamp, exit_price: float, exit_reason: str):
        """Close the position"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason

        # Calculate final PnL
        if self.side == 'long':
            self.pnl_pct = ((exit_price / self.entry_price) - 1) * 100
        else:
            self.pnl_pct = ((self.entry_price / exit_price) - 1) * 100

        self.pnl_usd = self.size_usd * (self.pnl_pct / 100)

        # Calculate R multiple
        risk_per_unit = abs(self.entry_price - self.stop_loss)
        if risk_per_unit > 0:
            price_move = abs(exit_price - self.entry_price)
            if self.pnl_usd >= 0:
                self.r_multiple = price_move / risk_per_unit
            else:
                self.r_multiple = -(price_move / risk_per_unit)

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        hold_minutes = 0
        if self.exit_time:
            hold_minutes = (self.exit_time - self.entry_time).total_seconds() / 60

        return {
            'timestamp_open': self.entry_time.isoformat(),
            'timestamp_close': self.exit_time.isoformat() if self.exit_time else None,
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'stop_loss': self.stop_loss,
            'size_usd': self.size_usd,
            'pnl_usd': self.pnl_usd,
            'pnl_pct': self.pnl_pct,
            'r_multiple': self.r_multiple,
            'hold_minutes': hold_minutes,
            'exit_reason': self.exit_reason,
            'score': self.signal_data.get('score', 0),
            'rvol': self.signal_data.get('rvol', 0),
            'return_24h': self.signal_data.get('return_24h', 0),
            'volume_24h': self.signal_data.get('volume_24h', 0)
        }


class BacktestPortfolio:
    """
    Manages backtest portfolio with risk management

    Applies same rules as LIVE mode:
    - PUMP_RISK_PER_TRADE
    - MAX_PORTFOLIO_HEAT
    - MAX_CONCURRENT_POSITIONS
    - MAX_DAILY_LOSS_PCT
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        # Equity tracking
        self.starting_equity = config.starting_equity
        self.current_equity = config.starting_equity
        self.peak_equity = config.starting_equity

        # Positions
        self.open_positions = []
        self.closed_positions = []

        # Daily tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.current_day = None

        # Stats
        self.total_fees = 0.0
        self.max_drawdown = 0.0

    def get_portfolio_heat(self) -> float:
        """
        Calculate current portfolio heat (total risk)

        Returns:
            Heat as decimal (e.g., 0.005 = 0.5%)
        """
        total_risk = 0.0

        for pos in self.open_positions:
            # Risk per position = distance to stop
            risk_pct = abs(pos.entry_price - pos.stop_loss) / pos.entry_price
            position_risk = pos.size_usd * risk_pct
            total_risk += position_risk

        if self.current_equity == 0:
            return 0.0

        return total_risk / self.current_equity

    def can_open_position(self, signal: Dict, entry_price: float, stop_loss: float) -> tuple:
        """
        Check if we can open a new position

        Returns:
            (can_open: bool, reason: str, size_usd: float)
        """
        # Check max concurrent positions
        max_concurrent = self.config.pump_max_concurrent if self.config.pump_only_mode else self.config.max_concurrent_positions
        if len(self.open_positions) >= max_concurrent:
            return (False, "Max concurrent positions", 0.0)

        # Check daily loss limit
        if self.config.enable_daily_loss_limit:
            daily_loss_pct = (self.daily_pnl / self.starting_equity) if self.starting_equity > 0 else 0
            if daily_loss_pct < -self.config.max_daily_loss_pct:
                return (False, "Daily loss limit hit", 0.0)

        # Calculate position size
        risk_pct = self.config.pump_risk_per_trade if signal.get('engine') == 'pump' else 0.0025

        risk_amount = self.current_equity * risk_pct
        price_risk_pct = abs((entry_price - stop_loss) / entry_price)

        if price_risk_pct == 0:
            return (False, "Invalid stop loss", 0.0)

        size_usd = risk_amount / price_risk_pct

        # Check portfolio heat
        new_heat = self.get_portfolio_heat() + (risk_amount / self.current_equity)
        if new_heat > self.config.max_portfolio_heat:
            return (False, "Portfolio heat limit", 0.0)

        # Minimum position size check
        if size_usd < 10:  # MEXC minimum
            return (False, "Position too small", 0.0)

        return (True, "OK", size_usd)

    def open_position(
        self,
        signal: Dict,
        entry_time: pd.Timestamp,
        entry_price: float
    ) -> Optional[BacktestPosition]:
        """
        Open a new position

        Returns:
            BacktestPosition if opened, None otherwise
        """
        can_open, reason, size_usd = self.can_open_position(
            signal,
            entry_price,
            signal['stop_loss']
        )

        if not can_open:
            self.logger.debug(f"Cannot open {signal['symbol']}: {reason}")
            return None

        position = BacktestPosition(
            symbol=signal['symbol'],
            side=signal['side'],
            entry_time=entry_time,
            entry_price=entry_price,
            size_usd=size_usd,
            stop_loss=signal['stop_loss'],
            tp_2r=signal.get('tp_2r', 0),
            tp_4r=signal.get('tp_4r', 0),
            max_hold_hours=signal.get('max_hold_hours', 6),
            signal_data=signal
        )

        # Deduct fees (0.1% maker/taker average on MEXC spot)
        fee = size_usd * 0.001
        self.total_fees += fee
        self.current_equity -= fee

        self.open_positions.append(position)

        self.logger.info(
            f"✅ OPEN {signal['symbol']} | "
            f"Entry: ${entry_price:.6f} | "
            f"Size: ${size_usd:.2f} | "
            f"Stop: ${signal['stop_loss']:.6f} | "
            f"Score: {signal.get('score', 0)}"
        )

        return position

    def update_positions(
        self,
        current_time: pd.Timestamp,
        prices: Dict[str, float]
    ):
        """
        Update all open positions and check for exits

        Args:
            current_time: Current timestamp in backtest
            prices: {symbol: current_price}
        """
        positions_to_close = []

        for pos in self.open_positions:
            if pos.symbol not in prices:
                continue

            current_price = prices[pos.symbol]

            # Check if should exit
            exit_reason = pos.check_exit(
                current_time,
                current_price,
                trailing_enabled=self.config.enable_trailing_stop,
                trail_pct=self.config.trailing_stop_pct
            )

            if exit_reason:
                positions_to_close.append((pos, current_price, exit_reason))

        # Close positions
        for pos, exit_price, exit_reason in positions_to_close:
            self.close_position(pos, current_time, exit_price, exit_reason)

    def close_position(
        self,
        position: BacktestPosition,
        exit_time: pd.Timestamp,
        exit_price: float,
        exit_reason: str
    ):
        """Close a position"""
        position.close(exit_time, exit_price, exit_reason)

        # Deduct exit fee
        fee = position.size_usd * 0.001
        self.total_fees += fee

        # Update equity
        self.current_equity += position.pnl_usd - fee
        self.daily_pnl += position.pnl_usd

        # Update peak
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        # Calculate drawdown
        current_dd = ((self.current_equity - self.peak_equity) / self.peak_equity) if self.peak_equity > 0 else 0
        if current_dd < self.max_drawdown:
            self.max_drawdown = current_dd

        self.logger.info(
            f"🔴 CLOSE {position.symbol} | "
            f"Exit: ${exit_price:.6f} | "
            f"PnL: ${position.pnl_usd:+.2f} ({position.pnl_pct:+.2f}%) | "
            f"R: {position.r_multiple:+.2f}R | "
            f"Reason: {exit_reason}"
        )

        # Move to closed
        self.open_positions.remove(position)
        self.closed_positions.append(position)
        self.daily_trades += 1

    def check_daily_reset(self, current_time: pd.Timestamp):
        """Reset daily counters at midnight UTC"""
        current_day = current_time.date()

        if self.current_day is None:
            self.current_day = current_day
            return

        if current_day > self.current_day:
            self.logger.info(
                f"🌅 Daily reset | "
                f"Trades: {self.daily_trades} | "
                f"Daily PnL: ${self.daily_pnl:+.2f}"
            )
            self.daily_pnl = 0.0
            self.daily_trades = 0
            self.current_day = current_day

    def get_stats(self) -> Dict:
        """Calculate final statistics"""
        total_trades = len(self.closed_positions)

        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_r': 0,
                'total_pnl_usd': 0,
                'total_pnl_pct': 0,
                'max_drawdown_pct': 0,
                'final_equity': self.current_equity,
                'total_fees': self.total_fees
            }

        wins = [p for p in self.closed_positions if p.pnl_usd > 0]
        losses = [p for p in self.closed_positions if p.pnl_usd <= 0]

        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        avg_r = sum(p.r_multiple for p in self.closed_positions) / total_trades if total_trades > 0 else 0

        total_pnl_usd = self.current_equity - self.starting_equity
        total_pnl_pct = (total_pnl_usd / self.starting_equity * 100) if self.starting_equity > 0 else 0

        best_trade = max(self.closed_positions, key=lambda p: p.pnl_usd)
        worst_trade = min(self.closed_positions, key=lambda p: p.pnl_usd)

        return {
            'total_trades': total_trades,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'avg_r': avg_r,
            'avg_win_usd': sum(p.pnl_usd for p in wins) / len(wins) if wins else 0,
            'avg_loss_usd': sum(p.pnl_usd for p in losses) / len(losses) if losses else 0,
            'best_trade_usd': best_trade.pnl_usd,
            'best_trade_symbol': best_trade.symbol,
            'worst_trade_usd': worst_trade.pnl_usd,
            'worst_trade_symbol': worst_trade.symbol,
            'total_pnl_usd': total_pnl_usd,
            'total_pnl_pct': total_pnl_pct,
            'max_drawdown_pct': self.max_drawdown * 100,
            'starting_equity': self.starting_equity,
            'final_equity': self.current_equity,
            'total_fees': self.total_fees
        }
