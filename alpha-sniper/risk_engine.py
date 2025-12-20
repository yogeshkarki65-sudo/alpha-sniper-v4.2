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

    # === UPGRADE E: Correlation-Aware Portfolio Heat ===
    # Static bucket mapping for crypto assets
    CORRELATION_BUCKETS = {
        # MEME coins
        'DOGE/USDT': 'MEME',
        'SHIB/USDT': 'MEME',
        'PEPE/USDT': 'MEME',
        'FLOKI/USDT': 'MEME',
        'BONK/USDT': 'MEME',
        'WIF/USDT': 'MEME',

        # Layer 1 blockchains
        'ETH/USDT': 'L1',
        'BNB/USDT': 'L1',
        'SOL/USDT': 'L1',
        'ADA/USDT': 'L1',
        'AVAX/USDT': 'L1',
        'DOT/USDT': 'L1',
        'ATOM/USDT': 'L1',
        'NEAR/USDT': 'L1',
        'FTM/USDT': 'L1',
        'ALGO/USDT': 'L1',

        # Layer 2 / Scaling
        'MATIC/USDT': 'L2',
        'ARB/USDT': 'L2',
        'OP/USDT': 'L2',
        'IMX/USDT': 'L2',
        'LRC/USDT': 'L2',

        # DeFi / DEX
        'UNI/USDT': 'DEX',
        'SUSHI/USDT': 'DEX',
        'CAKE/USDT': 'DEX',
        'DYDX/USDT': 'DEX',
        'GMX/USDT': 'DEX',
        'AAVE/USDT': 'DEFI',
        'COMP/USDT': 'DEFI',
        'CRV/USDT': 'DEFI',
        'SNX/USDT': 'DEFI',
        'MKR/USDT': 'DEFI',

        # AI / Data
        'FET/USDT': 'AI',
        'AGIX/USDT': 'AI',
        'RNDR/USDT': 'AI',
        'GRT/USDT': 'DATA',
        'LINK/USDT': 'ORACLE',

        # Gaming / Metaverse
        'SAND/USDT': 'GAMING',
        'MANA/USDT': 'GAMING',
        'AXS/USDT': 'GAMING',
        'GALA/USDT': 'GAMING',

        # Legacy / Payment
        'LTC/USDT': 'LEGACY',
        'BCH/USDT': 'LEGACY',
        'ETC/USDT': 'LEGACY',
        'XRP/USDT': 'PAYMENT',
        'XLM/USDT': 'PAYMENT',

        # Storage / Infrastructure
        'FIL/USDT': 'STORAGE',
        'AR/USDT': 'STORAGE',
    }

    def __init__(self, config, exchange, logger, telegram, alert_mgr=None):
        self.config = config
        self.exchange = exchange
        self.logger = logger
        self.telegram = telegram
        self.alert_mgr = alert_mgr

        # Regime state
        self.current_regime = None
        self.last_regime_update = 0
        self.regime_update_interval = 3600  # 1 hour

        # Equity tracking
        # In SIM mode: use config.starting_equity as baseline
        # In LIVE mode: will be set to actual MEXC balance on first sync (session_start_equity)
        self.starting_equity = config.starting_equity  # Config baseline (used only in SIM)
        self.session_start_equity = None  # Actual MEXC balance at session start (LIVE only)
        self.current_equity = config.starting_equity
        self.daily_pnl = 0.0
        self.daily_reset_time = self._get_next_utc_midnight()

        # Open positions
        self.open_positions = []

        # Position tracking for daily loss and reporting
        self.closed_trades_today = []
        self.daily_loss_alert_sent = False  # Track if alert already sent today
        self.signals_today = 0  # Track signals generated today
        self.pumps_today = 0  # Track pump signals today

        # Anti-repeat cooldown: track symbols with losing trades
        # Format: {(symbol, side): timestamp_of_loss}
        self.cooldown_tracker = {}
        self.cooldown_duration = 4 * 3600  # 4 hours in seconds

        # Daily loss limit flag
        self.daily_loss_limit_hit = False

        self.logger.info(f"💰 RiskEngine initialized | Starting equity: ${self.starting_equity:.2f}")

    def update_equity(self, new_equity: float):
        """
        Update current equity (used in LIVE mode to sync with MEXC balance)

        Args:
            new_equity: New equity value from exchange
        """
        if new_equity is None or new_equity <= 0:
            self.logger.warning(f"Invalid equity value received: {new_equity}, keeping current: ${self.current_equity:.2f}")
            return

        old_equity = self.current_equity
        self.current_equity = new_equity

        # First sync in LIVE mode: set session_start_equity
        if self.session_start_equity is None and not self.config.sim_mode:
            self.session_start_equity = new_equity
            self.logger.info(f"💰 Session equity baseline set from MEXC: ${self.session_start_equity:.2f}")

        # Log equity changes (but not too frequently)
        equity_change_pct = ((new_equity - old_equity) / old_equity * 100) if old_equity > 0 else 0
        if abs(equity_change_pct) > 0.1:  # Only log if change > 0.1%
            self.logger.info(f"💰 Equity updated: ${old_equity:.2f} → ${new_equity:.2f} ({equity_change_pct:+.2f}%)")

    def get_symbol_bucket(self, symbol: str) -> str:
        """
        === UPGRADE E: Correlation-Aware Portfolio Heat ===
        Get correlation bucket for a symbol
        Returns: bucket name (str) or 'OTHER' if not found
        """
        return self.CORRELATION_BUCKETS.get(symbol, 'OTHER')

    def _get_next_utc_midnight(self) -> float:
        """Get timestamp of next UTC midnight"""
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = tomorrow.timestamp() + 86400  # Next day
        return tomorrow

    def get_pump_allocation_slice(self) -> tuple[float, float]:
        """
        === UPGRADE C: Pump Engine Allocation Feedback Loop ===

        Dynamically adjust pump allocation based on recent pump performance.

        Returns: (min_allocation, max_allocation) as fractions (0.0-1.0)
        """
        if not self.config.pump_feedback_enabled:
            # Return base allocations if feedback disabled
            return (self.config.pump_allocation_min, self.config.pump_allocation_max)

        try:
            import os
            import csv

            trade_log_path = 'logs/v4_trade_scores.csv'

            # Check if log file exists
            if not os.path.exists(trade_log_path):
                self.logger.debug("[PumpFeedback] Trade log not found, using base allocation")
                return (self.config.pump_allocation_min_base, self.config.pump_allocation_max_base)

            # Read last N pump trades
            pump_trades = []
            with open(trade_log_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('engine', '').lower() == 'pump':
                        try:
                            r_multiple = float(row.get('r_multiple', 0) or 0)
                            pump_trades.append(r_multiple)
                        except (ValueError, TypeError):
                            continue

            # Get last N trades
            lookback = self.config.pump_feedback_lookback
            recent_pump_trades = pump_trades[-lookback:] if len(pump_trades) > lookback else pump_trades

            # Not enough data yet
            if len(recent_pump_trades) < lookback:
                self.logger.debug(
                    f"[PumpFeedback] Only {len(recent_pump_trades)}/{lookback} trades, "
                    f"using base allocation"
                )
                return (self.config.pump_allocation_min_base, self.config.pump_allocation_max_base)

            # Calculate average R
            avg_r = sum(recent_pump_trades) / len(recent_pump_trades)

            # Adjust allocation based on performance
            base_min = self.config.pump_allocation_min_base
            base_max = self.config.pump_allocation_max_base
            floor = self.config.pump_allocation_min_floor
            ceil = self.config.pump_allocation_max_ceil

            if avg_r < self.config.pump_feedback_low_r_thres:
                # Cold performance - reduce allocation
                adjustment = (self.config.pump_feedback_low_r_thres - avg_r) / self.config.pump_feedback_low_r_thres
                adjustment = min(adjustment, 1.0)  # Cap at 100% reduction

                min_alloc = max(floor, base_min - (base_min - floor) * adjustment)
                max_alloc = max(floor, base_max - (base_max - floor) * adjustment)

            elif avg_r > self.config.pump_feedback_high_r_thres:
                # Hot performance - increase allocation
                adjustment = (avg_r - self.config.pump_feedback_high_r_thres) / self.config.pump_feedback_high_r_thres
                adjustment = min(adjustment, 1.0)  # Cap at 100% increase

                min_alloc = min(ceil, base_min + (ceil - base_min) * adjustment)
                max_alloc = min(ceil, base_max + (ceil - base_max) * adjustment)

            else:
                # Neutral performance - use base
                min_alloc = base_min
                max_alloc = base_max

            self.logger.info(
                f"[PumpFeedback] avg_R={avg_r:.2f} ({len(recent_pump_trades)} trades) | "
                f"slice={min_alloc:.0%}-{max_alloc:.0%}"
            )

            return (min_alloc, max_alloc)

        except Exception as e:
            self.logger.error(f"[PumpFeedback] Error calculating allocation: {e}")
            return (self.config.pump_allocation_min_base, self.config.pump_allocation_max_base)

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
                # Default to SIDEWAYS for edge cases (log for analysis)
                self.logger.debug(
                    f"Regime detection fallback to SIDEWAYS: "
                    f"price={current_price:.2f}, ema200={ema200:.2f}, "
                    f"return_30d={return_30d:.1f}%, rsi={rsi:.1f}"
                )
                regime = "SIDEWAYS"

            # Check if regime changed
            if regime != self.current_regime:
                old_regime = self.current_regime if self.current_regime else "UNKNOWN"
                self.logger.info(f"📊 Regime changed: {old_regime} → {regime}")

                # Send focused Telegram notification for regime change
                alert_msg = (
                    f"📊 REGIME CHANGE: {old_regime} → {regime}\n"
                    f"Price: ${current_price:.2f}\n"
                    f"RSI: {rsi:.1f}\n"
                    f"30d Return: {return_30d:+.1f}%"
                )
                self.logger.info(f"[TELEGRAM] Sending regime change notification")
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

        base_size = helpers.calculate_position_size_from_risk(
            self.current_equity,
            risk_pct,
            entry_price,
            stop_loss_price
        )

        # === UPGRADE D: Liquidity-Aware Position Sizing ===
        if self.config.liquidity_sizing_enabled:
            try:
                symbol = signal.get('symbol')
                liquidity = self.exchange.get_liquidity_metrics(symbol)

                spread_pct = liquidity.get('spread_pct', 0.5)
                depth_usd = liquidity.get('depth_usd', 10000)

                # Calculate liquidity factors
                spread_factor = max(0.0, min(1.0, 1.0 - (spread_pct / self.config.liquidity_spread_soft_limit)))
                depth_factor = max(0.0, min(1.0, depth_usd / self.config.liquidity_depth_good_level))

                # Combined liquidity factor (take minimum of both)
                liquidity_factor = max(self.config.liquidity_min_factor, min(spread_factor, depth_factor))

                # Apply scaling
                final_size = base_size * liquidity_factor

                # Only log if actually scaling down significantly
                if liquidity_factor < 0.95:
                    self.logger.info(
                        f"[LiquidityGuard] SCALE DOWN symbol={symbol} | "
                        f"requested_size=${base_size:.2f} | adjusted_size=${final_size:.2f} | "
                        f"spread={spread_pct:.2f}% | depth=${depth_usd:.0f} | "
                        f"factor={liquidity_factor:.2f}"
                    )
                else:
                    self.logger.debug(
                        f"[LiquiditySizing] {symbol} base=${base_size:.2f}, "
                        f"spread={spread_pct:.2f}%, depth=${depth_usd:.0f}, "
                        f"factor={liquidity_factor:.2f}, final=${final_size:.2f}"
                    )

                return final_size

            except Exception as e:
                self.logger.error(f"[LiquiditySizing] Error: {e}, using base size")
                # Fall through to score scaling

        # === PHASE 2C: SCORE-BASED POSITION SCALING ===
        # Scale position size based on signal quality (score)
        final_size = base_size
        if getattr(self.config, 'position_scale_with_score', False):
            try:
                score = signal.get('score', 0.75)
                min_score = getattr(self.config, 'min_score_pump', 0.75)
                max_scale = getattr(self.config, 'position_scale_max', 1.5)

                # Calculate scale factor (1.0 at min_score, up to max_scale at score=1.0)
                if score >= min_score and min_score > 0:
                    # Linear scaling from 1.0 to max_scale
                    score_range = 1.0 - min_score
                    score_excess = score - min_score
                    scale_factor = 1.0 + ((score_excess / score_range) * (max_scale - 1.0))
                    scale_factor = min(scale_factor, max_scale)  # Cap at max_scale

                    final_size = base_size * scale_factor

                    if scale_factor > 1.05:  # Only log significant scaling
                        self.logger.info(
                            f"[ScoreScaling] {signal.get('symbol')} | "
                            f"score={score:.2f} base=${base_size:.2f} → ${final_size:.2f} "
                            f"(x{scale_factor:.2f})"
                        )
            except Exception as e:
                self.logger.error(f"[ScoreScaling] Error: {e}, using base size")
                final_size = base_size

        return final_size

    def can_open_new_position(self, signal: Dict) -> tuple[bool, Optional[str]]:
        """
        Check if we can open a new position
        Returns: (can_open, reason_if_not)
        """
        symbol = signal.get('symbol')
        side = signal.get('side')

        # Check hard daily loss limit (-2% of session equity)
        if self.session_start_equity and self.session_start_equity > 0:
            session_pnl_pct = self.daily_pnl / self.session_start_equity
            if session_pnl_pct <= -0.02:  # -2% hard limit
                if not self.daily_loss_limit_hit:
                    try:
                        self.logger.info(f"[RISK] Daily loss limit HIT: {float(session_pnl_pct)*100:.2f}%")
                    except:
                        pass
                    self.daily_loss_limit_hit = True
                return False, "Daily loss limit -2%"

        # Check anti-repeat cooldown (symbol+side specific)
        if symbol and side:
            cooldown_key = (symbol, side)
            if cooldown_key in self.cooldown_tracker:
                cooldown_end = self.cooldown_tracker[cooldown_key]
                now = time.time()
                if now < cooldown_end:
                    remaining_hours = (cooldown_end - now) / 3600
                    try:
                        self.logger.info(f"[RISK] Cooldown active for {symbol} {side}: {float(remaining_hours):.1f}h remaining")
                    except:
                        pass
                    return False, f"Cooldown {remaining_hours:.1f}h"
                else:
                    # Cooldown expired, remove from tracker
                    del self.cooldown_tracker[cooldown_key]

        # Check daily loss limit (original env-based check)
        if self.config.enable_daily_loss_limit:
            daily_loss_pct = self.daily_pnl / self.starting_equity if self.starting_equity > 0 else 0
            if daily_loss_pct <= -self.config.max_daily_loss_pct:
                # Send enhanced alert first time it's hit
                if not self.daily_loss_alert_sent:
                    self.logger.info(f"[TELEGRAM] Sending daily loss limit notification")
                    if self.alert_mgr:
                        self.alert_mgr.send_daily_loss_limit_hit(
                            loss_pct=daily_loss_pct * 100,
                            max_loss_pct=self.config.max_daily_loss_pct * 100
                        )
                    else:
                        # Fallback to simple notification
                        mode = "SIM" if self.config.sim_mode else "LIVE"
                        self.telegram.send(
                            f"⛔ DAILY LOSS LIMIT HIT\n"
                            f"Mode: {mode}\n"
                            f"Loss today: ${self.daily_pnl:.2f} ({daily_loss_pct*100:.2f}%)\n"
                            f"Limit: {self.config.max_daily_loss_pct*100:.1f}%\n"
                            f"No new trades will be opened until next daily reset."
                        )
                    self.daily_loss_alert_sent = True
                return False, f"Daily loss limit hit ({daily_loss_pct*100:.2f}%)"

        # === UPGRADE E: Correlation-Aware Portfolio Heat ===
        # Check correlation bucket limits
        if self.config.correlation_limit_enabled:
            symbol = signal.get('symbol')
            bucket = self.get_symbol_bucket(symbol)

            # Count positions in this bucket
            bucket_count = sum(
                1 for p in self.open_positions
                if self.get_symbol_bucket(p.get('symbol', '')) == bucket
            )

            if bucket_count >= self.config.max_correlated_positions:
                # Get existing symbols in this bucket
                bucket_symbols = [p.get('symbol') for p in self.open_positions if self.get_symbol_bucket(p.get('symbol', '')) == bucket]
                self.logger.info(
                    f"[CorrelationGuard] REJECT symbol={symbol} | "
                    f"bucket={bucket} already has {bucket_count} positions {bucket_symbols} | "
                    f"max={self.config.max_correlated_positions}"
                )
                return False, f"Bucket {bucket} limit reached ({bucket_count}/{self.config.max_correlated_positions})"

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

        # Send Telegram notification for trade open
        try:
            if self.alert_mgr:
                # Calculate R multiple for display
                entry_price = position.get('entry_price', 0)
                stop_loss = position.get('stop_loss', 0)
                target = position.get('target', None)

                # Calculate expected R multiple
                r_multiple = None
                if entry_price > 0 and stop_loss > 0 and target:
                    side = position.get('side', 'long')
                    if side == 'long':
                        risk_dist = entry_price - stop_loss
                        reward_dist = target - entry_price
                    else:
                        risk_dist = stop_loss - entry_price
                        reward_dist = entry_price - target

                    if risk_dist > 0:
                        r_multiple = reward_dist / risk_dist

                self.alert_mgr.send_trade_open(
                    symbol=position['symbol'],
                    side=position['side'].upper(),
                    engine=position.get('engine', 'unknown').upper(),
                    regime=position.get('regime', 'unknown'),
                    size=position.get('qty', 0),
                    entry=position['entry_price'],
                    stop=position['stop_loss'],
                    target=position.get('target'),
                    leverage=1.0,  # Spot trading, no leverage
                    risk_pct=(position.get('initial_risk_usd', 0) / self.current_equity * 100) if self.current_equity > 0 else 0,
                    r_multiple=r_multiple
                )
                self.logger.info(f"[TELEGRAM] Sent trade open notification for {position['symbol']}")
        except Exception as e:
            self.logger.warning(f"[TELEGRAM] Failed to send trade open notification: {e}")

    def close_position(self, position: Dict, exit_price: float, reason: str):
        """
        Close a position and update PnL
        FIX: Use qty for accurate PnL, use initial_risk_usd for R-multiple
        """
        entry_price = position['entry_price']
        qty = position.get('qty', 0)
        side = position['side']
        initial_risk_usd = position.get('initial_risk_usd', 0)

        # Calculate PnL using qty (FIXED)
        if side == 'long':
            pnl_usd = (exit_price - entry_price) * qty
        else:  # short
            pnl_usd = (entry_price - exit_price) * qty

        # Calculate PnL percentage (relative to size_usd at entry)
        size_usd = position.get('size_usd', 0)
        pnl_pct = (pnl_usd / size_usd) * 100 if size_usd > 0 else 0

        # Calculate R-multiple (FIXED: use initial_risk_usd)
        if initial_risk_usd > 0:
            r_multiple = pnl_usd / initial_risk_usd
        else:
            # Fallback to old method if initial_risk_usd not set
            sl_price = position['stop_loss']
            if side == 'long':
                risk_pct_price = abs((entry_price - sl_price) / entry_price)
            else:
                risk_pct_price = abs((sl_price - entry_price) / entry_price)
            r_multiple = pnl_pct / (risk_pct_price * 100) if risk_pct_price > 0 else 0

        # Update equity and daily PnL
        self.current_equity += pnl_usd
        self.daily_pnl += pnl_usd

        # Anti-repeat cooldown: If trade lost money, block this symbol+side for 4 hours
        if pnl_usd < 0:
            symbol = position.get('symbol')
            side = position.get('side')
            if symbol and side:
                cooldown_key = (symbol, side)
                cooldown_end = time.time() + self.cooldown_duration
                self.cooldown_tracker[cooldown_key] = cooldown_end
                try:
                    self.logger.info(f"[RISK] Cooldown activated for {symbol} {side}: 4h block after loss")
                except:
                    pass

        # Hold time
        hold_time_sec = time.time() - position['timestamp_open']
        hold_time_hours = hold_time_sec / 3600

        # Detailed SIM logging
        if self.config.sim_mode:
            self.logger.info(
                f"🔴 [SIM-CLOSE] {position['symbol']} {position['side']} | "
                f"exit={exit_price:.6f} | "
                f"pnl_usd=${pnl_usd:.2f} | "
                f"pnl_pct={pnl_pct:.2f}% | "
                f"risk_usd=${initial_risk_usd:.2f} | "
                f"R={r_multiple:.2f}R | "
                f"hold={hold_time_hours:.1f}h | "
                f"reason={reason}"
            )
        else:
            self.logger.info(
                f"🔴 Position closed | {position['symbol']} {position['side']} | "
                f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%) | R: {r_multiple:.2f}R | "
                f"Hold: {hold_time_hours:.1f}h | Reason: {reason}"
            )

        # Send enhanced Telegram notification for ALL trade closes
        try:
            # Format hold time
            hold_hours = int(hold_time_hours)
            hold_mins = int((hold_time_hours - hold_hours) * 60)
            hold_time_str = f"{hold_hours}h {hold_mins}m"

            if self.alert_mgr:
                # Use enhanced alert manager
                self.alert_mgr.send_trade_close(
                    symbol=position['symbol'],
                    side=position['side'].upper(),
                    engine=position.get('engine', 'unknown').upper(),
                    regime=position.get('regime', 'unknown'),
                    entry=entry_price,
                    exit_price=exit_price,
                    size=qty,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    r_multiple=r_multiple,
                    hold_time=hold_time_str,
                    reason=reason
                )
                self.logger.info(f"[TELEGRAM] Sent enhanced trade close notification for {position['symbol']}")
            else:
                # Fallback to simple notification
                mode = "SIM" if self.config.sim_mode else "LIVE"
                telegram_msg = (
                    f"🔴 [{mode}] TRADE CLOSED\n"
                    f"Symbol: {position['symbol']}\n"
                    f"Side: {position['side']}\n"
                    f"Engine: {position.get('engine', 'unknown')}\n"
                    f"Regime: {position.get('regime', 'unknown')}\n"
                    f"Entry: {entry_price:.6f}\n"
                    f"Exit: {exit_price:.6f}\n"
                    f"PnL: ${pnl_usd:.2f} ({pnl_pct:.1f}%)\n"
                    f"R-multiple: {r_multiple:.2f}R\n"
                    f"Hold time: {hold_time_hours:.1f}h\n"
                    f"Reason: {reason}"
                )
                self.logger.info(f"[TELEGRAM] Sending trade close notification for {position['symbol']}")
                self.telegram.send(telegram_msg)
        except Exception as e:
            self.logger.warning(f"[TELEGRAM] Failed to send trade close notification: {e}")

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

        # Persist to /var/run/alpha-sniper/trades_today.json
        self._save_daily_trades()

        # Log to CSV
        try:
            helpers.log_trade_to_csv(closed_trade)
        except Exception as e:
            self.logger.error(f"Error logging trade to CSV: {e}")

        # Remove from open positions
        if position in self.open_positions:
            self.open_positions.remove(position)

    def check_daily_reset(self):
        """
        Check if we need to reset daily counters (at UTC midnight)
        """
        current_time = time.time()
        if current_time >= self.daily_reset_time:
            mode = "SIM" if self.config.sim_mode else "LIVE"
            self.logger.info(f"🌅 Daily reset | PnL today: ${self.daily_pnl:.2f}")

            # Send enhanced daily summary if configured
            if self.config.telegram_daily_report_enabled:
                if self.closed_trades_today:
                    wins = sum(1 for t in self.closed_trades_today if t['pnl_usd'] > 0)
                    losses = sum(1 for t in self.closed_trades_today if t['pnl_usd'] <= 0)
                    try:
                        if self.alert_mgr:
                            # Use enhanced alert manager with trades list
                            self.alert_mgr.send_daily_summary(
                                final_equity=self.current_equity,
                                open_positions=len(self.open_positions),
                                trades_list=self.closed_trades_today
                            )
                        else:
                            # Fallback to simple notification
                            self.telegram.send(
                                f"📊 [{mode}] Daily Summary\n"
                                f"PnL: ${self.daily_pnl:.2f}\n"
                                f"Trades: {len(self.closed_trades_today)} (W:{wins} L:{losses})\n"
                                f"Equity: ${self.current_equity:.2f}"
                            )
                    except Exception as e:
                        self.logger.warning(f"[TELEGRAM] Failed to send daily summary: {e}")

            # Send daily reset notification (especially important if daily loss limit was hit)
            if self.daily_loss_alert_sent:
                try:
                    self.telegram.send(
                        f"🌅 [{mode}] DAILY RESET\n"
                        f"Daily loss counter has been reset.\n"
                        f"New entries are now allowed.\n"
                        f"Current equity: ${self.current_equity:.2f}"
                    )
                    self.logger.info(f"[TELEGRAM] Sent daily reset notification")
                except Exception as e:
                    self.logger.warning(f"[TELEGRAM] Failed to send daily reset notification: {e}")

            # Reset
            self.daily_pnl = 0.0
            self.closed_trades_today = []
            self.daily_loss_alert_sent = False  # Reset alert flag
            self.signals_today = 0  # Reset signal counter
            self.pumps_today = 0  # Reset pump counter
            self.daily_reset_time = self._get_next_utc_midnight()

            # Clear daily trades file
            self._save_daily_trades()

    def save_positions(self, filepath: str):
        """
        Save open positions to JSON
        Handles PermissionError gracefully - logs warning but doesn't crash

        Args:
            filepath: Full path to positions file (from config.positions_file_path)
        """
        try:
            helpers.save_json_atomic(filepath, self.open_positions)
        except PermissionError as e:
            self.logger.error(f"❌ Permission error writing positions file at {filepath}: {e}")
            self.logger.error("Bot will continue but positions may not persist across restarts")
            # Optionally send Telegram alert (rate-limited)
            if hasattr(self, 'telegram') and self.telegram:
                try:
                    self.telegram.send_message(
                        f"⚠️ Permission error writing positions file:\n{filepath}\n\n"
                        f"Bot continues but positions may not persist."
                    )
                except:
                    pass
        except Exception as e:
            self.logger.warning(f"Failed to save positions to {filepath}: {e}")

    def load_positions(self, filepath: str):
        """
        Load open positions from JSON

        Args:
            filepath: Full path to positions file (from config.positions_file_path)
        """
        import os

        # Try to load positions
        self.open_positions = helpers.load_json(filepath, default=[])

        # Detect permission issues: file exists but we got default (empty list)
        if not self.open_positions and os.path.exists(filepath):
            try:
                # Try to read file to check permissions
                with open(filepath, 'r') as f:
                    pass
            except PermissionError:
                self.logger.error(f"❌ Permission error reading positions file at {filepath}")
                self.logger.error("Fix with: sudo chown alpha-sniper:alpha-sniper <filepath>")
                # Send Telegram alert
                if hasattr(self, 'telegram') and self.telegram:
                    try:
                        self.telegram.send_message(
                            f"⚠️ Permission error reading positions file:\n{filepath}\n\n"
                            f"Bot will start without previous positions."
                        )
                    except:
                        pass

        if self.open_positions:
            self.logger.info(f"📂 Loaded {len(self.open_positions)} open positions from {filepath}")

    def _save_daily_trades(self):
        """
        Persist today's closed trades to /var/run/alpha-sniper/trades_today.json
        This file is used for daily reporting and gets cleared at UTC midnight.
        """
        import os
        import json

        try:
            # Ensure directory exists
            os.makedirs('/var/run/alpha-sniper', exist_ok=True)

            filepath = '/var/run/alpha-sniper/trades_today.json'

            # Save trades with atomic write
            helpers.save_json_atomic(filepath, self.closed_trades_today)

        except Exception as e:
            self.logger.warning(f"Failed to save daily trades to /var/run/alpha-sniper/trades_today.json: {e}")
