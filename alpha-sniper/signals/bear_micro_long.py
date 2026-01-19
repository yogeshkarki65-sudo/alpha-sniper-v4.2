"""
Bear Micro-Long Engine for Alpha Sniper V4.2
- Very selective longs in bear markets
- Only active in MILD_BEAR and DEEP_BEAR
- High relative strength vs BTC
"""
from utils import helpers


class BearMicroLongEngine:
    """
    Bear Micro-Long Engine
    - Catches strong relative strength in bear markets
    - Very selective
    - Small position sizing
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def generate_signals(self, market_data: dict, regime: str) -> list:
        """
        Generate bear micro-long signals
        Only active in MILD_BEAR and DEEP_BEAR
        """
        signals = []

        # Only in bear regimes
        if regime not in ['MILD_BEAR', 'DEEP_BEAR']:
            return signals

        for symbol, data in market_data.items():
            try:
                signal = self._evaluate_symbol(symbol, data, regime)
                if signal:
                    signals.append(signal)
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for bear micro-long: {e}")

        return signals

    def _evaluate_symbol(self, symbol: str, data: dict, regime: str) -> dict:
        """
        Evaluate a single symbol for bear micro-long entry
        """
        # Get data
        data.get('ticker')
        df_15m = data.get('df_15m')
        df_1h = data.get('df_1h')
        btc_performance = data.get('btc_performance', 0)  # Performance relative to BTC

        if df_15m is None or len(df_15m) < 50:
            return None
        if df_1h is None or len(df_1h) < 50:
            return None

        # Current price
        current_price = df_15m['close'].iloc[-1]

        # Calculate indicators
        ema_20_15m = helpers.calculate_ema(df_15m, 'close', 20).iloc[-1]
        helpers.calculate_ema(df_15m, 'close', 50).iloc[-1]
        ema_20_1h = helpers.calculate_ema(df_1h, 'close', 20).iloc[-1]
        rsi_1h = helpers.calculate_rsi(df_1h, 'close', 14).iloc[-1]

        # RVOL
        current_volume = df_15m['volume'].iloc[-1]
        avg_volume = df_15m['volume'].iloc[-20:-1].mean()
        rvol = helpers.calculate_rvol(current_volume, avg_volume)

        # Momentum
        momentum_1h = helpers.calculate_momentum(df_1h, 12)
        momentum_24h = helpers.calculate_momentum(df_1h, 24) if len(df_1h) >= 25 else 0

        # Bear micro-long conditions (VERY STRICT)
        # Must show relative strength despite bear market
        price_above_emas = current_price > ema_20_15m and current_price > ema_20_1h
        rsi_strong = rsi_1h > 50  # Holding strength
        rvol_high = rvol >= 1.8  # Very high RVOL
        momentum_positive = momentum_1h > 8 and momentum_24h > 5  # Positive momentum

        # Relative strength vs BTC (if available)
        # If symbol is up while BTC is down, that's strong relative strength
        relative_strength_check = True
        if btc_performance < 0:  # BTC is down
            # Symbol should be up or only slightly down
            symbol_performance = momentum_24h
            if symbol_performance < btc_performance + 5:  # Not outperforming BTC enough
                relative_strength_check = False

        # Calculate score (very high bar in bear markets)
        score = 0

        if price_above_emas:
            score += 25
        if rsi_strong:
            score += 15

        # RVOL scoring
        if rvol >= 2.5:
            score += 30
        elif rvol >= 2.0:
            score += 20
        elif rvol >= 1.8:
            score += 10

        # Momentum scoring
        if momentum_1h > 15 and momentum_24h > 10:
            score += 30
        elif momentum_1h > 10:
            score += 15
        elif momentum_1h > 8:
            score += 5

        # Check minimum score (high threshold for bear markets)
        if score < 85:
            return None

        # Check all core conditions
        if not (price_above_emas and rvol_high and momentum_positive and relative_strength_check):
            return None

        # Calculate stop loss (tight for bear market longs)
        atr_15m = helpers.calculate_atr(df_15m, 14).iloc[-1]
        swing_low = df_15m['low'].iloc[-10:].min()

        # Bear micro SL: tight (1.5 ATR or 2.5% below)
        sl_atr = current_price - (1.5 * atr_15m)
        sl_pct = current_price * 0.975  # 2.5% hard stop

        stop_loss = max(sl_atr, sl_pct, swing_low * 0.995)

        # Enforce minimum stop distance (Fast Stop Manager safety rail for bear_micro)
        min_stop_distance = current_price * self.config.min_stop_pct_bear_micro
        actual_stop_distance = current_price - stop_loss
        if actual_stop_distance < min_stop_distance:
            stop_loss = current_price - min_stop_distance

        # TP: Conservative targets (1.5R and 3R)
        risk_per_unit = current_price - stop_loss
        tp_2r = current_price + (risk_per_unit * 1.5)
        tp_4r = current_price + (risk_per_unit * 3)

        # Return signal
        return {
            'symbol': symbol,
            'side': 'long',
            'engine': 'bear_micro',
            'score': score,
            'entry_price': current_price,
            'stop_loss': stop_loss,
            'tp_2r': tp_2r,
            'tp_4r': tp_4r,
            'rvol': rvol,
            'momentum_1h': momentum_1h,
            'rsi_1h': rsi_1h,
            'regime': regime
        }
