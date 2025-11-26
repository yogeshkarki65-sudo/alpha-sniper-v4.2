"""
Risk Engine for Alpha Sniper V4.2
- Regime detection (BULL, SIDEWAYS, MILD_BEAR, DEEP_BEAR)
- Position sizing based on regime
- Portfolio heat tracking
- Daily loss limit
"""
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List
from utils import helpers


class RiskEngine:
    """
    Central risk management and regime detection engine
    """
    def __init__(self, config, exchange, logger, telegram):
        self.config = config
        self.exchange = exchange
        self.logger = logger
        self.telegram = telegram

        # Regime state
        self.current_regime = None
        self.last_regime_update = 0
        self.regime_update_interval = 3600  # 1 hour

        # Equity tracking
        self.starting_equity = config.starting_equity
        self.current_equity = config.starting_equity
        self.daily_pnl = 0.0
        self.daily_reset_time = self._get_next_utc_midnight()

        # Open positions
        self.open_positions = []

        # Position tracking for daily loss
        self.closed_trades_today = []
        self.daily_loss_alert_sent = False  # Track if alert already sent today

        self.logger.info(f"💰 RiskEngine initialized | Starting equity: ${self.starting_equity:.2f}")

    def _get_next_utc_midnight(self) -> float:
        """Get timestamp of next UTC midnight"""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = tomorrow.timestamp() + 86400  # Next day
        return tomorrow

    def update_regime(self):
        """
        Update market regime based on BTC/USDT daily data
        Regimes: BULL, SIDEWAYS, MILD_BEAR, DEEP_BEAR
        """
        current_time = time.time()

        # Only update if stale (> 1 hour old) or None
        if self.current_regime is not None:
            if (current_time - self.last_regime_update) < self.regime_update_interval:
                return self.current_regime

        self.logger.debug("🔄 Updating regime...")

        try:
            # Fetch BTC/USDT daily candles
            ohlcv = self.exchange.get_klines('BTC/USDT', '1d', limit=250)
            if not ohlcv or len(ohlcv) < 200:
                self.logger.warning("⚠️ Not enough BTC data for regime detection, defaulting to SIDEWAYS")
                self.current_regime = "SIDEWAYS"
                self.last_regime_update = current_time
                return self.current_regime

            df = helpers.ohlcv_to_dataframe(ohlcv)

            # Ensure close column is numeric (critical for calculations)
            df['close'] = df['close'].astype(float)

            # Calculate indicators
            ema200 = helpers.calculate_ema(df, 'close', 200).iloc[-1]
            rsi = helpers.calculate_rsi(df, 'close', 14).iloc[-1]

            # 30-day return
            if len(df) >= 31:
                return_30d = ((df['close'].iloc[-1] / df['close'].iloc[-31]) - 1) * 100
            else:
                return_30d = 0.0

            current_price = df['close'].iloc[-1]

            self.logger.info(f"📈 Regime update | price={current_price:.2f}, ema200={ema200:.2f}, RSI={rsi:.1f}, 30d={return_30d:.2f}%")

            # Regime rules
            if current_price > ema200 and rsi > 55 and return_30d > 10:
                regime = "BULL"
            elif return_30d <= -20 and rsi < 40:
                regime = "DEEP_BEAR"
            elif current_price < ema200 and -20 < return_30d <= -10 and 35 <= rsi <= 50:
                regime = "MILD_BEAR"
            elif abs(return_30d) <= 10 or (45 <= rsi <= 55):
                regime = "SIDEWAYS"
            else:
                # Default to SIDEWAYS for edge cases
                regime = "SIDEWAYS"

            # Check if regime changed
            if regime != self.current_regime:
                self.logger.info(f"📊 Regime changed: {self.current_regime} → {regime}")

                # Enhanced Telegram alert with details
                alert_msg = (
                    f"📈 Regime changed: {self.current_regime} → {regime}\n"
                    f"Price: ${current_price:.2f}\n"
                    f"EMA200: ${ema200:.2f}\n"
                    f"RSI: {rsi:.1f}\n"
                    f"30d Return: {return_30d:+.1f}%"
                )
                self.telegram.send(alert_msg)
                self.current_regime = regime
            else:
                self.logger.info(f"📊 Current regime: {regime}")

            self.last_regime_update = current_time
            return self.current_regime

        except Exception as e:
            self.logger.error(f"🔴 Error updating regime: {e}")
            if self.current_regime is None:
                self.current_regime = "SIDEWAYS"
            return self.current_regime

    def get_risk_per_trade(self, engine: str = "standard") -> float:
        """
        Get risk per trade based on current regime and engine
        Returns: risk as decimal (e.g., 0.0025 for 0.25%)
        """
        if engine == "pump":
            return self.config.pump_risk_per_trade

        # Standard engines use regime-based risk
        regime = self.current_regime or "SIDEWAYS"

        risk_map = {
            "BULL": self.config.risk_per_trade_bull,
            "SIDEWAYS": self.config.risk_per_trade_sideways,
            "MILD_BEAR": self.config.risk_per_trade_mild_bear,
            "DEEP_BEAR": self.config.risk_per_trade_deep_bear,
        }

        return risk_map.get(regime, self.config.risk_per_trade_sideways)

    def calculate_position_size(
        self,
        signal: Dict,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        Calculate position size in USD based on R-based risk
        """
        engine = signal.get('engine', 'standard')
        risk_pct = self.get_risk_per_trade(engine)

        position_size = helpers.calculate_position_size_from_risk(
            self.current_equity,
            risk_pct,
            entry_price,
            stop_loss_price
        )

        return position_size

    def can_open_new_position(self, signal: Dict) -> tuple[bool, Optional[str]]:
        """
        Check if we can open a new position
        Returns: (can_open, reason_if_not)
        """
        # Check daily loss limit
        if self.config.enable_daily_loss_limit:
            daily_loss_pct = self.daily_pnl / self.starting_equity if self.starting_equity > 0 else 0
            if daily_loss_pct <= -self.config.max_daily_loss_pct:
                # Send alert first time it's hit
                if not self.daily_loss_alert_sent:
                    self.telegram.send(
                        f"🚨 DAILY LOSS LIMIT HIT\n"
                        f"Loss: ${self.daily_pnl:.2f} ({daily_loss_pct*100:.2f}%)\n"
                        f"Limit: {self.config.max_daily_loss_pct*100:.1f}%\n"
                        f"No new positions until daily reset"
                    )
                    self.daily_loss_alert_sent = True
                return False, f"Daily loss limit hit ({daily_loss_pct*100:.2f}%)"

        # Check max concurrent positions
        if len(self.open_positions) >= self.config.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({len(self.open_positions)})"

        # Check pump-specific limits
        engine = signal.get('engine', 'standard')
        if engine == 'pump':
            pump_count = sum(1 for p in self.open_positions if p.get('engine') == 'pump')
            if pump_count >= self.config.pump_max_concurrent:
                return False, f"Max pump positions reached ({pump_count})"

        # Check portfolio heat
        current_heat = self._calculate_current_heat()
        engine_risk = self.get_risk_per_trade(engine)

        if (current_heat + engine_risk) > self.config.max_portfolio_heat:
            return False, f"Portfolio heat limit ({current_heat*100:.3f}% + {engine_risk*100:.3f}% > {self.config.max_portfolio_heat*100:.2f}%)"

        return True, None

    def _calculate_current_heat(self) -> float:
        """
        Calculate current portfolio heat (sum of open position risks)
        """
        total_risk = 0.0
        for pos in self.open_positions:
            risk_pct = pos.get('risk_pct', 0.0)
            total_risk += risk_pct
        return total_risk

    def add_position(self, position: Dict):
        """
        Add a new open position
        """
        self.open_positions.append(position)
        self.logger.info(f"✅ Position opened | {position['symbol']} {position['side']} | size=${position.get('size_usd', 0):.2f}")

    def close_position(self, position: Dict, exit_price: float, reason: str):
        """
        Close a position and update PnL
        """
        entry_price = position['entry_price']
        size_usd = position.get('size_usd', 0)
        side = position['side']

        # Calculate PnL
        if side == 'long':
            pnl_pct = ((exit_price / entry_price) - 1) * 100
        else:  # short
            pnl_pct = ((entry_price / exit_price) - 1) * 100

        pnl_usd = size_usd * (pnl_pct / 100)

        # Calculate R-multiple
        sl_price = position['stop_loss']
        if side == 'long':
            risk_pct_price = abs((entry_price - sl_price) / entry_price)
            r_multiple = pnl_pct / (risk_pct_price * 100) if risk_pct_price > 0 else 0
        else:
            risk_pct_price = abs((sl_price - entry_price) / entry_price)
            r_multiple = pnl_pct / (risk_pct_price * 100) if risk_pct_price > 0 else 0

        # Update equity and daily PnL
        self.current_equity += pnl_usd
        self.daily_pnl += pnl_usd

        # Hold time
        hold_time_sec = time.time() - position['timestamp_open']
        hold_time_hours = hold_time_sec / 3600

        self.logger.info(
            f"🔴 Position closed | {position['symbol']} {position['side']} | "
            f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%) | R: {r_multiple:.2f}R | "
            f"Hold: {hold_time_hours:.1f}h | Reason: {reason}"
        )

        # Send Telegram alert for significant trades
        if abs(pnl_pct) > 2 or abs(r_multiple) > 1.5:
            self.telegram.send(
                f"🔴 Trade closed\n"
                f"{position['symbol']} {position['side']}\n"
                f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%)\n"
                f"R: {r_multiple:.2f}R\n"
                f"Reason: {reason}"
            )

        # Track closed trade
        closed_trade = {
            **position,
            'exit_price': exit_price,
            'pnl_usd': pnl_usd,
            'pnl_pct': pnl_pct,
            'r_multiple': r_multiple,
            'hold_time_hours': hold_time_hours,
            'exit_reason': reason,
            'timestamp_close': time.time()
        }
        self.closed_trades_today.append(closed_trade)

        # Remove from open positions
        if position in self.open_positions:
            self.open_positions.remove(position)

    def check_daily_reset(self):
        """
        Check if we need to reset daily counters (at UTC midnight)
        """
        current_time = time.time()
        if current_time >= self.daily_reset_time:
            self.logger.info(f"🌅 Daily reset | PnL today: ${self.daily_pnl:.2f}")

            # Send daily summary
            if self.closed_trades_today:
                wins = sum(1 for t in self.closed_trades_today if t['pnl_usd'] > 0)
                losses = sum(1 for t in self.closed_trades_today if t['pnl_usd'] <= 0)
                self.telegram.send(
                    f"📊 Daily Summary\n"
                    f"PnL: ${self.daily_pnl:.2f}\n"
                    f"Trades: {len(self.closed_trades_today)} (W:{wins} L:{losses})\n"
                    f"Equity: ${self.current_equity:.2f}"
                )

            # Reset
            self.daily_pnl = 0.0
            self.closed_trades_today = []
            self.daily_loss_alert_sent = False  # Reset alert flag
            self.daily_reset_time = self._get_next_utc_midnight()

    def save_positions(self, filepath: str = 'positions.json'):
        """
        Save open positions to JSON
        """
        helpers.save_json_atomic(filepath, self.open_positions)

    def load_positions(self, filepath: str = 'positions.json'):
        """
        Load open positions from JSON
        """
        self.open_positions = helpers.load_json(filepath, default=[])
        if self.open_positions:
            self.logger.info(f"📂 Loaded {len(self.open_positions)} open positions from {filepath}")
