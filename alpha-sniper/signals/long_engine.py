"""
Standard Long Engine for Alpha Sniper V4.2
- Breakout and trend-following long setups
- Active in all regimes with varying strictness
"""
from utils import helpers


class LongEngine:
    """
    Standard Long Signal Engine
    - 15m + 1h trend alignment
    - High RVOL
    - Price above EMAs
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def generate_signals(self, market_data: dict, regime: str) -> list:
        """
        Generate long signals from market data
        market_data: dict with symbol -> {ticker, ohlcv_15m, ohlcv_1h, ...}
        regime: current market regime
        """
        signals = []

        for symbol, data in market_data.items():
            try:
                signal = self._evaluate_symbol(symbol, data, regime)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for long: {e}")

        return signals

    def _evaluate_symbol(self, symbol: str, data: dict, regime: str) -> dict:
        """
        Evaluate a single symbol for long entry
        """
        # Get data
        ticker = data.get('ticker')
        df_15m = data.get('df_15m')
        df_1h = data.get('df_1h')

        if df_15m is None or len(df_15m) < 50:
            return None
        if df_1h is None or len(df_1h) < 50:
            return None

        # Current price
        current_price = df_15m['close'].iloc[-1]

        # Calculate indicators for 15m
        ema_20_15m = helpers.calculate_ema(df_15m, 'close', 20).iloc[-1]
        ema_50_15m = helpers.calculate_ema(df_15m, 'close', 50).iloc[-1]

        # Calculate indicators for 1h
        ema_20_1h = helpers.calculate_ema(df_1h, 'close', 20).iloc[-1]
        ema_50_1h = helpers.calculate_ema(df_1h, 'close', 50).iloc[-1]

        # RVOL
        current_volume = df_15m['volume'].iloc[-1]
        avg_volume = df_15m['volume'].iloc[-20:-1].mean()
        rvol = helpers.calculate_rvol(current_volume, avg_volume)

        # Momentum
        momentum_1h = helpers.calculate_momentum(df_1h, 12)  # 12 candles = 12h

        # Regime-based RVOL requirements
        rvol_threshold = {
            'BULL': 1.15,
            'SIDEWAYS': 1.3,
            'MILD_BEAR': 1.5,
            'DEEP_BEAR': 1.7
        }.get(regime, 1.3)

        # Entry conditions
        price_above_15m_emas = current_price > ema_20_15m and current_price > ema_50_15m
        price_above_1h_emas = current_price > ema_20_1h and current_price > ema_50_1h
        ema_alignment = ema_20_15m > ema_50_15m  # Short EMA > Long EMA (uptrend)
        rvol_check = rvol >= rvol_threshold
        momentum_check = momentum_1h > 5  # Positive momentum

        # Calculate score (0-100)
        score = 0

        if price_above_15m_emas:
            score += 20
        if price_above_1h_emas:
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

        # Momentum scoring
        if momentum_1h > 15:
            score += 20
        elif momentum_1h > 10:
            score += 10
        elif momentum_1h > 5:
            score += 5

        # === UPGRADE A: Sideways Coiled Volatility Boost ===
        if self.config.sideways_coil_enabled and regime == "SIDEWAYS":
            # Calculate ATR expansion
            atr_current = helpers.calculate_atr(df_15m, 14).iloc[-1]

            # Get 24h of 15m candles = 96 candles
            lookback_24h = min(96, len(df_15m) - 1)
            if lookback_24h >= 20:  # Need enough data
                atr_series = helpers.calculate_atr(df_15m, 14)
                atr_median_24h = atr_series.iloc[-lookback_24h:].median()

                atr_expansion = atr_current >= (self.config.sideways_coil_atr_mult * atr_median_24h)

                # Simple RSI divergence check
                rsi_divergence = False
                if self.config.sideways_rsi_divergence_enabled:
                    rsi_series = helpers.calculate_rsi(df_15m, 'close', 14)

                    # Look back 10-20 bars for divergence
                    lookback_bars = min(20, len(df_15m) - 1)
                    if lookback_bars >= 10:
                        recent_prices = df_15m['close'].iloc[-lookback_bars:]
                        recent_rsi = rsi_series.iloc[-lookback_bars:]

                        # Check if price made new/equal high but RSI didn't
                        price_high = recent_prices.max()
                        price_current = recent_prices.iloc[-1]
                        rsi_high = recent_rsi.max()
                        rsi_current = recent_rsi.iloc[-1]

                        # Price near recent high but RSI is lower
                        if price_current >= price_high * 0.995:  # Within 0.5% of high
                            if rsi_current < rsi_high * 0.95:  # RSI at least 5% below high
                                rsi_divergence = True

                # Apply boost if conditions met
                if atr_expansion and rsi_divergence:
                    score += self.config.sideways_coil_score_boost
                    self.logger.info(
                        f"[CoilBoost] +{self.config.sideways_coil_score_boost} score | "
                        f"symbol={symbol} | regime=SIDEWAYS | "
                        f"ATR_expansion={atr_current/atr_median_24h:.2f}x | RSI_div=True"
                    )

        # Check if meets minimum score
        if score < self.config.min_score:
            return None

        # Check all conditions
        if not (price_above_15m_emas and rvol_check):
            return None

        # Calculate stop loss and take profit
        # SL: below recent swing low or 2 ATR below entry
        atr_15m = helpers.calculate_atr(df_15m, 14).iloc[-1]
        swing_low = df_15m['low'].iloc[-10:].min()

        sl_atr = current_price - (2.0 * atr_15m)
        sl_swing = swing_low * 0.995  # 0.5% below swing low

        stop_loss = max(sl_atr, sl_swing)  # Use tighter stop

        # Enforce minimum stop distance (Fast Stop Manager safety rail)
        min_stop_distance = current_price * config.min_stop_pct_core
        actual_stop_distance = current_price - stop_loss
        if actual_stop_distance < min_stop_distance:
            stop_loss = current_price - min_stop_distance

        # TP: 2R and 4R targets
        risk_per_unit = current_price - stop_loss
        tp_2r = current_price + (risk_per_unit * 2)
        tp_4r = current_price + (risk_per_unit * 4)

        # Return signal
        return {
            'symbol': symbol,
            'side': 'long',
            'engine': 'long',
            'score': score,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'tp_2r': tp_2r,
            'tp_4r': tp_4r,
            'rvol': rvol,
            'momentum_1h': momentum_1h,
            'regime': regime
        }
