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

        # Pump debug toggle - directly access config attribute
        self.debug_enabled = config.pump_debug_logging if hasattr(config, 'pump_debug_logging') else False

        # Log debug status on initialization
        if self.debug_enabled:
            self.logger.info("[PUMP_DEBUG] Debug logging ENABLED for pump engine")

    def generate_signals(self, market_data: dict, regime: str, open_positions=None) -> list:
        """
        Generate pump signals from market data using regime-aware thresholds
        """
        signals = []

        if not self.config.pump_engine_enabled:
            return signals

        # Get regime-specific thresholds
        thresholds = self.config.get_pump_thresholds(regime)

        # Log active thresholds for this regime
        if self.debug_enabled:
            self.logger.info(
                "[PUMP_DEBUG] Active thresholds (regime=%s): "
                "min_vol=%.0f, min_score=%d, min_rvol=%.1f, min_return=%.2f%%, "
                "max_return=%.1f%%, min_momentum=%.1f, "
                "new_listing_min_rvol=%.1f, new_listing_min_score=%d, new_listing_min_momentum=%.1f",
                regime,
                thresholds.min_24h_quote_volume,
                thresholds.min_score,
                thresholds.min_rvol,
                thresholds.min_24h_return,
                thresholds.max_24h_return,
                thresholds.min_momentum,
                thresholds.new_listing_min_rvol,
                thresholds.new_listing_min_score,
                thresholds.new_listing_min_momentum,
            )

        # Filter valid symbols (exclude leveraged tokens and perps)
        quote = "USDT"
        valid_symbols = [
            s for s in market_data.keys()
            if s.endswith(quote)
            and not s.endswith("3L" + quote)
            and not s.endswith("3S" + quote)
            and "_PERP" not in s
        ]

        # Debug counters
        debug_counts = None
        debug_rejections = None

        if self.debug_enabled:
            debug_counts = {
                "raw": len(valid_symbols),
                "after_data": 0,
                "after_volume": 0,
                "after_spread": 0,
                "after_score": 0,
                "after_core": 0,
            }
            debug_rejections = []

        for symbol in valid_symbols:
            try:
                result = self._evaluate_symbol(
                    symbol,
                    market_data.get(symbol),
                    regime,
                    open_positions,
                    thresholds=thresholds,
                    debug_counts=debug_counts,
                    debug_rejections=debug_rejections,
                )
                if result is not None:
                    signals.append(result)
            except Exception as e:
                self.logger.debug(f"Error evaluating {symbol} for pump: {e}")

        # Debug summary
        if self.debug_enabled and debug_counts is not None:
            self.logger.info(
                "[PUMP_DEBUG] Scan Summary: raw=%d, after_data=%d, after_volume=%d, "
                "after_spread=%d, after_score=%d, after_core=%d, final_signals=%d",
                debug_counts["raw"],
                debug_counts["after_data"],
                debug_counts["after_volume"],
                debug_counts["after_spread"],
                debug_counts["after_score"],
                debug_counts["after_core"],
                len(signals),
            )

            if debug_rejections:
                sample_count = min(len(debug_rejections), 20)
                self.logger.info(f"[PUMP_DEBUG] Sample rejections (first {sample_count}):")
                for msg in debug_rejections[:20]:
                    self.logger.info(f"[PUMP_DEBUG]   {msg}")

        return signals

    def _evaluate_symbol(
        self,
        symbol: str,
        data: dict,
        regime: str,
        open_positions,
        thresholds,
        debug_counts=None,
        debug_rejections=None,
    ):
        """
        Evaluate whether a single symbol meets pump entry criteria for the given regime and, if so, construct a pump signal dictionary.
        
        Performs data validation and regime-aware gating (volume, spread, RVOL, 1h momentum, 24h return), supports aggressive-mode and new-listing overrides, computes stop loss and target prices, and determines maximum hold time. If the symbol fails any eligibility checks, returns None.
        
        Parameters:
            symbol (str): Ticker symbol to evaluate.
            data (dict): Market payload expected to contain 'ticker' (with 'quoteVolume'), 'df_15m' (DataFrame), 'df_1h' (DataFrame), and optionally 'spread_pct'.
            regime (str): Active regime name used to select thresholds and behavior.
            open_positions: Current open positions context (may influence decision logic; pass-through).
            thresholds: Regime-specific thresholds object with fields used for gating and scoring.
            debug_counts (dict, optional): Mutable counters updated for debugging phases (e.g., "after_data", "after_volume", "after_spread", "after_score", "after_core").
            debug_rejections (list, optional): If provided, rejection reasons are appended to this list for sampling/logging.
        
        Returns:
            dict or None: A signal dictionary on success containing keys
                'symbol', 'side', 'engine', 'score', 'entry_price', 'stop_loss', 'tp_2r', 'tp_4r',
                'rvol', 'momentum_1h', 'return_24h', 'volume_24h', 'max_hold_hours', and 'regime';
            returns None if the symbol does not meet pump entry criteria.
        """
        # Get data
        ticker = data.get('ticker') if data else None
        df_15m = data.get('df_15m') if data else None
        df_1h = data.get('df_1h') if data else None
        volume_24h = ticker.get('quoteVolume', 0) if ticker else 0
        spread_pct = data.get('spread_pct', 999) if data else 999

        # Data validation
        if df_15m is None or len(df_15m) < 20:
            if debug_rejections is not None:
                debug_rejections.append(f"{symbol}: INSUFFICIENT_DATA (15m)")
            return None
        if df_1h is None or len(df_1h) < 20:
            if debug_rejections is not None:
                debug_rejections.append(f"{symbol}: INSUFFICIENT_DATA (1h)")
            return None

        if debug_counts is not None:
            debug_counts["after_data"] += 1

        # Pump volume filter - use regime-aware threshold
        min_volume = thresholds.min_24h_quote_volume

        if volume_24h < min_volume:
            if debug_rejections is not None:
                debug_rejections.append(
                    f"{symbol}: VOLUME_TOO_LOW (24h=${volume_24h:,.0f} < min=${min_volume:,.0f})"
                )
            return None

        if debug_counts is not None:
            debug_counts["after_volume"] += 1

        # Pump spread filter (slightly looser than standard)
        max_spread_pct = 1.5
        if spread_pct > max_spread_pct:
            if debug_rejections is not None:
                debug_rejections.append(
                    f"{symbol}: SPREAD_TOO_WIDE ({spread_pct:.2f}% > {max_spread_pct:.2f}%)"
                )
            return None

        if debug_counts is not None:
            debug_counts["after_spread"] += 1

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

        # Check if this is a new listing (bypass stricter filters if enabled)
        is_new_listing = False
        if self.config.pump_new_listing_bypass:
            # Check if symbol is newly listed using RVOL spike as proxy
            # RVOL >= 5.0 often indicates new listing activity
            if rvol >= 5.0:
                is_new_listing = True

        # Apply thresholds: aggressive mode overrides regime thresholds if enabled
        if self.config.pump_aggressive_mode:
            # Use aggressive mode thresholds (override regime-based)
            rvol_check = rvol >= self.config.pump_aggressive_min_rvol
            momentum_check = momentum_1h >= self.config.pump_aggressive_min_momentum
            volume_check = volume_24h >= self.config.pump_aggressive_min_24h_quote_volume
            return_check = self.config.pump_aggressive_min_24h_return <= return_24h <= self.config.pump_aggressive_max_24h_return

            # Additional aggressive filters (if configured)
            if self.config.pump_aggressive_price_above_ema1m and len(df_15m) >= 15:
                ema_1m = df_15m['close'].ewm(span=60, adjust=False).mean().iloc[-1]
                if current_price < ema_1m:
                    if debug_rejections is not None:
                        debug_rejections.append(
                            f"{symbol}: AGGRESSIVE_PRICE_BELOW_EMA1M (price={current_price:.6f} < ema1m={ema_1m:.6f})"
                        )
                    return None

            # Volume check for aggressive mode
            if not volume_check:
                if debug_rejections is not None:
                    debug_rejections.append(
                        f"{symbol}: AGGRESSIVE_VOLUME_LOW (24h=${volume_24h:,.0f} < min=${self.config.pump_aggressive_min_24h_quote_volume:,.0f})"
                    )
                return None
        elif is_new_listing:
            # Use relaxed new listing thresholds
            rvol_check = rvol >= thresholds.new_listing_min_rvol
            momentum_check = momentum_1h >= thresholds.new_listing_min_momentum
            # No return check for new listings (can be any size move)
            return_check = True
        else:
            # Use standard regime thresholds
            rvol_check = rvol >= thresholds.min_rvol
            momentum_check = momentum_1h >= thresholds.min_momentum
            return_check = thresholds.min_24h_return <= return_24h <= thresholds.max_24h_return

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

        # Volume quality bonus (relative to configured minimum)
        if volume_24h > (min_volume * 2):
            score += 10
        elif volume_24h > min_volume:
            score += 5

        # Check minimum score using regime-aware thresholds
        if is_new_listing:
            min_score = thresholds.new_listing_min_score
        else:
            min_score = thresholds.min_score

        if score < min_score:
            if debug_rejections is not None:
                listing_tag = " [NEW_LISTING]" if is_new_listing else ""
                debug_rejections.append(
                    f"{symbol}: SCORE_TOO_LOW{listing_tag} (score={score:.1f} < min={min_score}, "
                    f"rvol={rvol:.2f}, mom={momentum_1h:.1f}, ret_24h={return_24h:.1f}%)"
                )
            return None

        if debug_counts is not None:
            debug_counts["after_score"] += 1

        # Check all core conditions
        if not (rvol_check and momentum_check and return_check):
            if debug_rejections is not None:
                failed = []
                if not rvol_check:
                    failed.append(f"RVOL_TOO_LOW ({rvol:.2f})")
                if not momentum_check:
                    failed.append(f"MOMENTUM_TOO_WEAK ({momentum_1h:.1f})")
                if not return_check:
                    failed.append(f"RETURN_24H_OUT_OF_RANGE ({return_24h:.1f}%)")
                listing_tag = " [NEW_LISTING]" if is_new_listing else ""
                debug_rejections.append(
                    f"{symbol}: CORE_CONDITIONS_FAILED{listing_tag} ({', '.join(failed)})"
                )
            return None

        if debug_counts is not None:
            debug_counts["after_core"] += 1

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
            # PUMP-ONLY MODE: Extended hold time for better winners
            max_hold_hours = 3.0
        else:
            # NORMAL MODE: Standard hold time
            max_hold_hours = 6

        # Create signal dict
        signal = {
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

        # Log successful signal if debug enabled
        if self.debug_enabled:
            try:
                # Cast all values to Python float to avoid numpy formatting issues
                self.logger.info(
                    f"[PUMP_DEBUG] {symbol}: ✅ SIGNAL (score={float(score):.1f}, rvol={float(rvol):.2f}, "
                    f"mom={float(momentum_1h):.1f}, ret_24h={float(return_24h):.1f}%, vol_24h=${float(volume_24h):.0f})"
                )
            except Exception as e:
                # Logging must never crash signal generation
                self.logger.error(f"[PUMP_DEBUG] Failed to log signal for {symbol}: {e}")

        return signal