"""
Pump Engine for Alpha Sniper V4.2
- New token / pump catcher
- High RVOL, strong momentum
- Strict filters, tight risk
"""
from utils import helpers


class PumpEngine:
    """
    Pump Signal Engine
    - Catches new token pumps
    - Very high RVOL (>= 2.0)
    - 24h return 30-400%
    - Short hold time (max 6h)
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def generate_signals(self, market_data: dict, regime: str) -> list:
        """
        Generate pump signals from market data
        """
        signals = []

        if not self.config.pump_engine_enabled:
            return signals

        for symbol, data in market_data.items():
            try:
                signal = self._evaluate_symbol(symbol, data, regime)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for pump: {e}")

        return signals

    def _evaluate_symbol(self, symbol: str, data: dict, regime: str) -> dict:
        """
        Evaluate a single symbol for pump entry
        """
        # Get data
        ticker = data.get('ticker')
        df_15m = data.get('df_15m')
        df_1h = data.get('df_1h')
        volume_24h = ticker.get('quoteVolume', 0) if ticker else 0
        spread_pct = data.get('spread_pct', 999)

        if df_15m is None or len(df_15m) < 20:
            return None
        if df_1h is None or len(df_1h) < 20:
            return None

        # Pump-specific volume filter (stricter in pump-only mode)
        min_volume = self.config.pump_min_24h_quote_volume if self.config.pump_only_mode else self.config.min_24h_quote_volume
        if volume_24h < min_volume:
            return None

        # Pump spread filter (slightly looser than standard)
        if spread_pct > 1.5:
            return None

        # Current price
        current_price = df_15m['close'].iloc[-1]

        # RVOL
        current_volume = df_15m['volume'].iloc[-1]
        avg_volume = df_15m['volume'].iloc[-10:-1].mean() if len(df_15m) >= 11 else current_volume
        rvol = helpers.calculate_rvol(current_volume, avg_volume)

        # Momentum
        momentum_1h = helpers.calculate_momentum(df_1h, 12) if len(df_1h) >= 13 else 0

        # 24h return
        if len(df_1h) >= 25:
            return_24h = ((df_1h['close'].iloc[-1] / df_1h['close'].iloc[-25]) - 1) * 100
        else:
            return_24h = 0

        # Pump filters (stricter in pump-only mode)
        if self.config.pump_only_mode:
            # PUMP-ONLY MODE: Use stricter filters
            rvol_check = rvol >= self.config.pump_min_rvol
            momentum_check = momentum_1h >= self.config.pump_min_momentum_1h
            return_check = self.config.pump_min_24h_return <= return_24h <= self.config.pump_max_24h_return
        else:
            # NORMAL MODE: Standard pump filters
            rvol_check = rvol >= 2.0
            momentum_check = momentum_1h >= 25
            return_check = 30 <= return_24h <= 400  # Not too early, not too late

        # Calculate score
        score = 0

        if rvol >= 3.0:
            score += 30
        elif rvol >= 2.5:
            score += 20
        elif rvol >= 2.0:
            score += 10

        if momentum_1h >= 50:
            score += 30
        elif momentum_1h >= 35:
            score += 20
        elif momentum_1h >= 25:
            score += 10

        if 50 <= return_24h <= 150:
            score += 30  # Sweet spot
        elif 30 <= return_24h <= 200:
            score += 20
        elif return_check:
            score += 10

        # Volume quality
        if volume_24h > 500000:
            score += 10
        elif volume_24h > 200000:
            score += 5

        # Check minimum score (stricter in pump-only mode)
        min_score = self.config.pump_min_score if self.config.pump_only_mode else 70
        if score < min_score:
            return None

        # Check all core conditions
        if not (rvol_check and momentum_check and return_check):
            return None

        # Calculate stop loss (tighter for pumps)
        atr_15m = helpers.calculate_atr(df_15m, 14).iloc[-1]
        swing_low = df_15m['low'].iloc[-5:].min()

        # Pump SL: very tight (1.5 ATR or 3% below)
        sl_atr = current_price - (1.5 * atr_15m)
        sl_pct = current_price * 0.97  # 3% hard stop

        stop_loss = max(sl_atr, sl_pct, swing_low * 0.99)

        # Enforce minimum stop distance (Fast Stop Manager safety rail for pump)
        min_stop_distance = current_price * self.config.min_stop_pct_pump
        actual_stop_distance = current_price - stop_loss
        if actual_stop_distance < min_stop_distance:
            stop_loss = current_price - min_stop_distance

        # TP: Aggressive targets (1.5R and 3R for pumps)
        risk_per_unit = current_price - stop_loss
        tp_2r = current_price + (risk_per_unit * 1.5)
        tp_4r = current_price + (risk_per_unit * 3)

        # Max hold hours (shorter in pump-only mode)
        max_hold_hours = self.config.pump_max_hold_hours if self.config.pump_only_mode else 6

        # Return signal
        return {
            'symbol': symbol,
            'side': 'long',
            'engine': 'pump',
            'score': score,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'tp_2r': tp_2r,
            'tp_4r': tp_4r,
            'rvol': rvol,
            'momentum_1h': momentum_1h,
            'return_24h': return_24h,
            'volume_24h': volume_24h,
            'max_hold_hours': max_hold_hours,
            'regime': regime
        }
