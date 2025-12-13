"""
Standard Short Engine for Alpha Sniper V4.2
- Breakdown and reversal short setups
- Active in SIDEWAYS, MILD_BEAR, DEEP_BEAR regimes only
- Funding rate filter for shorts
"""
from utils import helpers


class ShortEngine:
    """
    Standard Short Signal Engine
    - Breakdown setups
    - Failed rallies
    - Funding rate checks
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def generate_signals(self, market_data: dict, regime: str) -> list:
        """
        Generate short signals from market data
        Only active in SIDEWAYS, MILD_BEAR, DEEP_BEAR
        """
        signals = []

        # Shorts only in non-BULL regimes
        if regime == 'BULL':
            return signals

        for symbol, data in market_data.items():
            try:
                signal = self._evaluate_symbol(symbol, data, regime)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for short: {e}")

        return signals

    def _evaluate_symbol(self, symbol: str, data: dict, regime: str) -> dict:
        """
        Evaluate a single symbol for short entry
        """
        # Get data
        ticker = data.get('ticker')
        df_15m = data.get('df_15m')
        df_1h = data.get('df_1h')
        funding_rate = data.get('funding_rate', 0)

        if df_15m is None or len(df_15m) < 50:
            return None
        if df_1h is None or len(df_1h) < 50:
            return None

        # Funding filter: skip if funding too high (expensive to short)
        if funding_rate > self.config.max_funding_8h_short:
            return None

        # === UPGRADE B: Short Funding Overlay ===
        # Only short when funding is positive enough (we get paid to short)
        if self.config.short_funding_overlay_enabled:
            if funding_rate < self.config.short_min_funding_8h:
                self.logger.info(
                    f"[ShortFundingOverlay] REJECT short | "
                    f"symbol={symbol} | "
                    f"funding={funding_rate:.5f} < min={self.config.short_min_funding_8h:.5f}"
                )
                return None
            else:
                self.logger.info(
                    f"[ShortFundingOverlay] OK short | "
                    f"symbol={symbol} | "
                    f"funding={funding_rate:.5f} >= min={self.config.short_min_funding_8h:.5f}"
                )

        # Current price
        current_price = df_15m['close'].iloc[-1]

        # Calculate indicators for 15m
        ema_20_15m = helpers.calculate_ema(df_15m, 'close', 20).iloc[-1]
        ema_50_15m = helpers.calculate_ema(df_15m, 'close', 50).iloc[-1]

        # Calculate indicators for 1h
        ema_20_1h = helpers.calculate_ema(df_1h, 'close', 20).iloc[-1]
        ema_50_1h = helpers.calculate_ema(df_1h, 'close', 50).iloc[-1]
        rsi_1h = helpers.calculate_rsi(df_1h, 'close', 14).iloc[-1]

        # RVOL
        current_volume = df_15m['volume'].iloc[-1]
        avg_volume = df_15m['volume'].iloc[-20:-1].mean()
        rvol = helpers.calculate_rvol(current_volume, avg_volume)

        # Momentum
        momentum_1h = helpers.calculate_momentum(df_1h, 12)

        # Regime-based RVOL requirements
        rvol_threshold = {
            'SIDEWAYS': 1.3,
            'MILD_BEAR': 1.2,
            'DEEP_BEAR': 1.15
        }.get(regime, 1.3)

        # Entry conditions for shorts
        price_below_15m_emas = current_price < ema_20_15m and current_price < ema_50_15m
        price_below_1h_emas = current_price < ema_20_1h and current_price < ema_50_1h
        ema_alignment = ema_20_15m < ema_50_15m  # Short EMA < Long EMA (downtrend)
        rvol_check = rvol >= rvol_threshold
        rsi_overbought = rsi_1h > 60  # Failed rally / overbought

        # Calculate score (0-100)
        score = 0

        if price_below_15m_emas:
            score += 20
        if price_below_1h_emas:
            score += 20
        if ema_alignment:
            score += 15

        # RVOL scoring
        if rvol >= 2.0:
            score += 25
        elif rvol >= 1.5:
            score += 15
        elif rvol >= rvol_threshold:
            score += 10

        # RSI overbought + negative momentum
        if rsi_overbought and momentum_1h < -5:
            score += 20
        elif momentum_1h < -10:
            score += 15
        elif momentum_1h < -5:
            score += 10

        # Check if meets minimum score
        if score < self.config.min_score:
            return None

        # Check core conditions
        if not (price_below_15m_emas and rvol_check):
            return None

        # Calculate stop loss and take profit
        # SL: above recent swing high or 2 ATR above entry
        atr_15m = helpers.calculate_atr(df_15m, 14).iloc[-1]
        swing_high = df_15m['high'].iloc[-10:].max()

        sl_atr = current_price + (2.0 * atr_15m)
        sl_swing = swing_high * 1.005  # 0.5% above swing high

        stop_loss = min(sl_atr, sl_swing)  # Use tighter stop

        # Enforce minimum stop distance (Fast Stop Manager safety rail)
        min_stop_distance = current_price * self.config.min_stop_pct_core
        actual_stop_distance = stop_loss - current_price
        if actual_stop_distance < min_stop_distance:
            stop_loss = current_price + min_stop_distance

        # TP: 2R and 4R targets (downward)
        risk_per_unit = stop_loss - current_price
        tp_2r = current_price - (risk_per_unit * 2)
        tp_4r = current_price - (risk_per_unit * 4)

        # Return signal
        return {
            'symbol': symbol,
            'side': 'short',
            'engine': 'short',
            'score': score,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'tp_2r': tp_2r,
            'tp_4r': tp_4r,
            'rvol': rvol,
            'rsi_1h': rsi_1h,
            'momentum_1h': momentum_1h,
            'funding_rate': funding_rate,
            'regime': regime
        }
