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

        # Debug counters
        debug_stats = {
            'raw_candidates': 0,
            'after_data_validation': 0,
            'after_volume_filter': 0,
            'after_spread_filter': 0,
            'after_rsi_ema_check': 0,
            'after_score_filter': 0,
            'after_core_conditions': 0,
            'final_signals': 0,
            'rejection_details': []
        }

        for symbol, data in market_data.items():
            debug_stats['raw_candidates'] += 1
            try:
                signal, rejection_reason = self._evaluate_symbol(symbol, data, regime, debug_stats)
                if signal:
                    signals.append(signal)
                    debug_stats['final_signals'] += 1
                elif self.config.pump_debug_logging and rejection_reason:
                    # Store rejection details for top candidates (limit to 20)
                    if len(debug_stats['rejection_details']) < 20:
                        debug_stats['rejection_details'].append({
                            'symbol': symbol,
                            'reason': rejection_reason
                        })
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for pump: {e}")

        # Debug summary
        if self.config.pump_debug_logging:
            self.logger.info(f"[PUMP_DEBUG] Scan Summary:")
            self.logger.info(f"  Raw candidates: {debug_stats['raw_candidates']}")
            self.logger.info(f"  After data validation: {debug_stats['after_data_validation']}")
            self.logger.info(f"  After volume filter: {debug_stats['after_volume_filter']}")
            self.logger.info(f"  After spread filter: {debug_stats['after_spread_filter']}")
            self.logger.info(f"  After RSI/EMA check: {debug_stats['after_rsi_ema_check']}")
            self.logger.info(f"  After score filter: {debug_stats['after_score_filter']}")
            self.logger.info(f"  After core conditions: {debug_stats['after_core_conditions']}")
            self.logger.info(f"  Final signals: {debug_stats['final_signals']}")

            if debug_stats['rejection_details']:
                self.logger.info(f"\n[PUMP_DEBUG] Sample Rejection Reasons (first 20):")
                for detail in debug_stats['rejection_details']:
                    self.logger.info(f"  {detail['symbol']}: {detail['reason']}")

        return signals

    def _evaluate_symbol(self, symbol: str, data: dict, regime: str, debug_stats: dict = None) -> tuple:
        """
        Evaluate a single symbol for pump entry

        Returns:
            tuple: (signal_dict or None, rejection_reason or None)
        """
        # Get data
        ticker = data.get('ticker')
        df_15m = data.get('df_15m')
        df_1h = data.get('df_1h')
        volume_24h = ticker.get('quoteVolume', 0) if ticker else 0
        spread_pct = data.get('spread_pct', 999)

        if df_15m is None or len(df_15m) < 20:
            return (None, "INSUFFICIENT_DATA_15m")
        if df_1h is None or len(df_1h) < 20:
            return (None, "INSUFFICIENT_DATA_1h")

        if debug_stats is not None:
            debug_stats['after_data_validation'] += 1

        # Pump-specific volume filter (varies by mode)
        if self.config.pump_only_mode and self.config.pump_aggressive_mode:
            # AGGRESSIVE PUMP MODE: Looser volume requirement
            min_volume = self.config.pump_aggressive_min_24h_quote_volume
        elif self.config.pump_only_mode:
            # PUMP-ONLY MODE: Stricter volume requirement
            min_volume = self.config.pump_min_24h_quote_volume
        else:
            # NORMAL MODE: Standard requirement
            min_volume = self.config.min_24h_quote_volume

        if volume_24h < min_volume:
            if self.config.pump_debug_logging:
                self.logger.debug(f"[PUMP_DEBUG] {symbol}: VOLUME_TOO_LOW (24h vol: ${volume_24h:,.0f} < ${min_volume:,.0f})")
            return (None, f"VOLUME_TOO_LOW (${volume_24h:,.0f} < ${min_volume:,.0f})")

        if debug_stats is not None:
            debug_stats['after_volume_filter'] += 1

        # Pump spread filter (slightly looser than standard)
        if spread_pct > 1.5:
            if self.config.pump_debug_logging:
                self.logger.debug(f"[PUMP_DEBUG] {symbol}: SPREAD_TOO_WIDE ({spread_pct:.2f}% > 1.5%)")
            return (None, f"SPREAD_TOO_WIDE ({spread_pct:.2f}% > 1.5%)")

        if debug_stats is not None:
            debug_stats['after_spread_filter'] += 1

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

        # Pump filters (varies by mode)
        if self.config.pump_only_mode and self.config.pump_aggressive_mode:
            # AGGRESSIVE PUMP MODE: Looser filters for more signals
            rvol_check = rvol >= self.config.pump_aggressive_min_rvol
            momentum_check = momentum_1h >= 20  # Looser momentum requirement
            return_check = self.config.pump_aggressive_min_24h_return <= return_24h <= self.config.pump_aggressive_max_24h_return

            # Optional: Check RSI 5m if enabled
            rsi_check = True
            if hasattr(self.config, 'pump_aggressive_momentum_rsi_5m'):
                df_5m = data.get('df_5m')
                if df_5m is not None and len(df_5m) >= 15:
                    rsi_5m = helpers.calculate_rsi(df_5m, 14).iloc[-1]
                    rsi_check = rsi_5m >= self.config.pump_aggressive_momentum_rsi_5m

            # Optional: Check price above EMA 1m
            ema_check = True
            if self.config.pump_aggressive_price_above_ema1m:
                df_1m = data.get('df_1m')
                if df_1m is not None and len(df_1m) >= 50:
                    ema_50 = df_1m['close'].iloc[-50:].mean()
                    ema_check = current_price > ema_50

            # Combine all aggressive checks
            if not (rsi_check and ema_check):
                if self.config.pump_debug_logging:
                    failed_checks = []
                    if not rsi_check:
                        failed_checks.append("RSI_5m_TOO_LOW")
                    if not ema_check:
                        failed_checks.append("PRICE_BELOW_EMA1m")
                    self.logger.debug(f"[PUMP_DEBUG] {symbol}: AGGRESSIVE_CHECKS_FAILED ({', '.join(failed_checks)})")
                return (None, f"AGGRESSIVE_CHECKS_FAILED ({'RSI' if not rsi_check else 'EMA'})")

        if debug_stats is not None:
            debug_stats['after_rsi_ema_check'] += 1

        elif self.config.pump_only_mode:
            # PUMP-ONLY MODE: Use stricter filters
            rvol_check = rvol >= self.config.pump_min_rvol
            momentum_check = momentum_1h >= self.config.pump_min_momentum_1h
            return_check = self.config.pump_min_24h_return <= return_24h <= self.config.pump_max_24h_return
        else:
            # NORMAL MODE: Standard pump filters
            rvol_check = rvol >= 2.0
            momentum_check = momentum_1h >= 25
            return_check = 30 <= return_24h <= 400  # Not too early, not too late

        # For non-aggressive modes, update RSI/EMA counter (they don't have that check)
        if debug_stats is not None and not (self.config.pump_only_mode and self.config.pump_aggressive_mode):
            debug_stats['after_rsi_ema_check'] += 1

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
            if self.config.pump_debug_logging:
                self.logger.debug(f"[PUMP_DEBUG] {symbol}: SCORE_TOO_LOW (score: {score} < min: {min_score}, rvol: {rvol:.2f}, momentum: {momentum_1h:.1f}, return_24h: {return_24h:.1f}%)")
            return (None, f"SCORE_TOO_LOW ({score} < {min_score})")

        if debug_stats is not None:
            debug_stats['after_score_filter'] += 1

        # Check all core conditions
        if not (rvol_check and momentum_check and return_check):
            if self.config.pump_debug_logging:
                failed_conditions = []
                if not rvol_check:
                    failed_conditions.append(f"RVOL:{rvol:.2f}")
                if not momentum_check:
                    failed_conditions.append(f"MOMENTUM:{momentum_1h:.1f}")
                if not return_check:
                    failed_conditions.append(f"RETURN_24H:{return_24h:.1f}%")
                self.logger.debug(f"[PUMP_DEBUG] {symbol}: CORE_CONDITIONS_FAILED ({', '.join(failed_conditions)})")
            return (None, f"CORE_CONDITIONS_FAILED")

        if debug_stats is not None:
            debug_stats['after_core_conditions'] += 1

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

        # Max hold hours (varies by mode)
        if self.config.pump_only_mode and self.config.pump_aggressive_mode:
            # AGGRESSIVE PUMP MODE: Very short hold time (minutes)
            max_hold_hours = self.config.pump_aggressive_max_hold_minutes / 60.0
        elif self.config.pump_only_mode:
            # PUMP-ONLY MODE: Short hold time
            max_hold_hours = self.config.pump_max_hold_hours
        else:
            # NORMAL MODE: Standard hold time
            max_hold_hours = 6

        # Log successful signal if debug enabled
        if self.config.pump_debug_logging:
            self.logger.info(f"[PUMP_DEBUG] {symbol}: ✅ SIGNAL_GENERATED (score: {score}, rvol: {rvol:.2f}, momentum: {momentum_1h:.1f}, return_24h: {return_24h:.1f}%, vol: ${volume_24h:,.0f})")

        # Return signal
        return ({
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
        }, None)
