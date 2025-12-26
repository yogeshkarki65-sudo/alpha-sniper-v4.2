import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class PumpThresholds:
    """Regime-specific pump signal thresholds"""
    min_24h_quote_volume: float
    min_score: int
    min_rvol: float
    min_24h_return: float
    max_24h_return: float
    min_momentum: float
    new_listing_min_rvol: float
    new_listing_min_score: int
    new_listing_min_momentum: float


class Config:
    def __init__(self):
        load_dotenv()

        # Helper to safely parse env values (strips whitespace and inline comments)
        def get_env(key, default=""):
            value = os.getenv(key, default)
            if isinstance(value, str):
                # Strip inline comments (anything after #)
                value = re.sub(r'\s*#.*$', '', value)
                # Strip whitespace
                value = value.strip()
            return value

        self.sim_mode = self.parse_bool(get_env("SIM_MODE", "true"))
        self.sim_data_source = get_env("SIM_DATA_SOURCE", "FAKE").upper()
        self.mexc_api_key = get_env("MEXC_API_KEY", "")
        self.mexc_secret_key = get_env("MEXC_SECRET_KEY", "")
        self.mexc_spot_enabled = self.parse_bool(get_env("MEXC_SPOT_ENABLED", "true"))
        self.mexc_futures_enabled = self.parse_bool(get_env("MEXC_FUTURES_ENABLED", "false"))
        self.telegram_bot_token = get_env("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = get_env("TELEGRAM_CHAT_ID", "")
        self.starting_equity = float(get_env("STARTING_EQUITY", "1000"))
        self.scan_interval_seconds = int(get_env("SCAN_INTERVAL_SECONDS", "300"))
        self.max_portfolio_heat = float(get_env("MAX_PORTFOLIO_HEAT", "0.012"))
        self.max_concurrent_positions = int(get_env("MAX_CONCURRENT_POSITIONS", "5"))
        self.max_spread_pct = float(get_env("MAX_SPREAD_PCT", "0.9"))
        self.enable_daily_loss_limit = self.parse_bool(get_env("ENABLE_DAILY_LOSS_LIMIT", "true"))
        self.max_daily_loss_pct = float(get_env("MAX_DAILY_LOSS_PCT", "0.03"))
        self.exchange_outage_grace_minutes = int(get_env("EXCHANGE_OUTAGE_GRACE_MINUTES", "30"))
        self.risk_per_trade_bull = float(get_env("RISK_PER_TRADE_BULL", "0.0025"))
        self.risk_per_trade_sideways = float(get_env("RISK_PER_TRADE_SIDEWAYS", "0.0025"))
        self.risk_per_trade_mild_bear = float(get_env("RISK_PER_TRADE_MILD_BEAR", "0.0018"))
        self.risk_per_trade_deep_bear = float(get_env("RISK_PER_TRADE_DEEP_BEAR", "0.0015"))
        self.pump_engine_enabled = self.parse_bool(get_env("PUMP_ENGINE_ENABLED", "true"))
        self.pump_risk_per_trade = float(get_env("PUMP_RISK_PER_TRADE", "0.0010"))
        self.pump_allocation_min = float(get_env("PUMP_ALLOCATION_MIN", "0.20"))
        self.pump_allocation_max = float(get_env("PUMP_ALLOCATION_MAX", "0.35"))
        self.pump_max_concurrent = int(get_env("PUMP_MAX_CONCURRENT", "2"))
        self.min_score = int(get_env("MIN_SCORE", "80"))
        self.min_24h_quote_volume = float(get_env("MIN_24H_QUOTE_VOLUME", "50000"))
        self.max_funding_8h_short = float(get_env("MAX_FUNDING_8H_SHORT", "0.00035"))

        # === V4.2 ADDITIVE OVERLAYS ===

        # UPGRADE A: Sideways Coiled Volatility Boost
        self.sideways_coil_enabled = self.parse_bool(get_env("SIDEWAYS_COIL_ENABLED", "true"))
        self.sideways_coil_atr_mult = float(get_env("SIDEWAYS_COIL_ATR_MULT", "1.5"))
        self.sideways_rsi_divergence_enabled = self.parse_bool(get_env("SIDEWAYS_RSI_DIVERGENCE_ENABLED", "true"))
        self.sideways_coil_score_boost = int(get_env("SIDEWAYS_COIL_SCORE_BOOST", "10"))

        # UPGRADE B: Short Funding Overlay
        self.short_funding_overlay_enabled = self.parse_bool(get_env("SHORT_FUNDING_OVERLAY_ENABLED", "true"))
        self.short_min_funding_8h = float(get_env("SHORT_MIN_FUNDING_8H", "0.00025"))

        # UPGRADE C: Pump Engine Allocation Feedback Loop
        self.pump_feedback_enabled = self.parse_bool(get_env("PUMP_FEEDBACK_ENABLED", "true"))
        self.pump_feedback_lookback = int(get_env("PUMP_FEEDBACK_LOOKBACK", "20"))
        self.pump_feedback_low_r_thres = float(get_env("PUMP_FEEDBACK_LOW_R_THRES", "0.5"))
        self.pump_feedback_high_r_thres = float(get_env("PUMP_FEEDBACK_HIGH_R_THRES", "1.0"))
        self.pump_allocation_min_base = float(get_env("PUMP_ALLOCATION_MIN_BASE", "0.20"))
        self.pump_allocation_max_base = float(get_env("PUMP_ALLOCATION_MAX_BASE", "0.35"))
        self.pump_allocation_min_floor = float(get_env("PUMP_ALLOCATION_MIN_FLOOR", "0.15"))
        self.pump_allocation_max_ceil = float(get_env("PUMP_ALLOCATION_MAX_CEIL", "0.40"))

        # UPGRADE D: Liquidity-Aware Position Sizing
        self.liquidity_sizing_enabled = self.parse_bool(get_env("LIQUIDITY_SIZING_ENABLED", "true"))
        self.liquidity_spread_soft_limit = float(get_env("LIQUIDITY_SPREAD_SOFT_LIMIT", "0.7"))
        self.liquidity_depth_good_level = float(get_env("LIQUIDITY_DEPTH_GOOD_LEVEL", "20000"))
        self.liquidity_min_factor = float(get_env("LIQUIDITY_MIN_FACTOR", "0.25"))

        # UPGRADE E: Correlation-Aware Portfolio Heat
        self.correlation_limit_enabled = self.parse_bool(get_env("CORRELATION_LIMIT_ENABLED", "true"))
        self.max_correlated_positions = int(get_env("MAX_CORRELATED_POSITIONS", "2"))

        # Dynamic Filter Engine (DFE)
        self.dfe_enabled = self.parse_bool(get_env("DFE_ENABLED", "false"))

        # Pump engine age limit (managed by DFE if enabled)
        self.pump_max_age_hours = int(get_env("PUMP_MAX_AGE_HOURS", "72"))

        # Fast Stop Manager (execution-level, NOT managed by DFE)
        self.position_check_interval_seconds = int(get_env("POSITION_CHECK_INTERVAL_SECONDS", "15"))
        self.min_stop_pct_core = float(get_env("MIN_STOP_PCT_CORE", "0.02"))
        self.min_stop_pct_bear_micro = float(get_env("MIN_STOP_PCT_BEAR_MICRO", "0.06"))
        self.min_stop_pct_pump = float(get_env("MIN_STOP_PCT_PUMP", "0.08"))

        # Entry-DETE (Smart Entry Timing Engine) - execution-level, NOT managed by DFE
        self.entry_dete_enabled = self.parse_bool(get_env("ENTRY_DETE_ENABLED", "false"))
        self.entry_dete_max_wait_seconds = int(get_env("ENTRY_DETE_MAX_WAIT_SECONDS", "180"))
        self.entry_dete_min_triggers = int(get_env("ENTRY_DETE_MIN_TRIGGERS", "2"))
        self.entry_dete_min_dip_pct = float(get_env("ENTRY_DETE_MIN_DIP_PCT", "0.005"))
        self.entry_dete_max_dip_pct = float(get_env("ENTRY_DETE_MAX_DIP_PCT", "0.02"))
        self.entry_dete_volume_multiplier = float(get_env("ENTRY_DETE_VOLUME_MULTIPLIER", "1.1"))

        # === PUMP-ONLY MODE ===
        # Simplified mode that uses ONLY the pump engine with stricter filters
        self.pump_only_mode = self.parse_bool(get_env("PUMP_ONLY_MODE", "false"))

        # Stricter pump filters for pump-only mode (LOWERED DEFAULTS FOR MORE SIGNALS)
        self.pump_min_24h_return = float(get_env("PUMP_MIN_24H_RETURN", "0.02"))
        self.pump_max_24h_return = float(get_env("PUMP_MAX_24H_RETURN", "10.0"))
        self.pump_min_rvol = float(get_env("PUMP_MIN_RVOL", "0.8"))
        self.pump_min_momentum_1h = float(get_env("PUMP_MIN_MOMENTUM_1H", "5.0"))
        self.pump_min_24h_quote_volume = float(get_env("PUMP_MIN_24H_QUOTE_VOLUME", "200000"))
        self.pump_min_score = int(get_env("PUMP_MIN_SCORE", "15"))
        self.pump_max_hold_hours = int(get_env("PUMP_MAX_HOLD_HOURS", "4"))

        # === NEW LISTING BYPASS (looser filters for newly listed tokens) ===
        self.pump_new_listing_bypass = self.parse_bool(get_env("PUMP_NEW_LISTING_BYPASS", "false"))
        self.pump_new_listing_max_age_minutes = int(get_env("PUMP_NEW_LISTING_MAX_AGE_MINUTES", "90"))
        self.pump_new_listing_min_rvol = float(get_env("PUMP_NEW_LISTING_MIN_RVOL", "0.5"))
        self.pump_new_listing_min_score = int(get_env("PUMP_NEW_LISTING_MIN_SCORE", "5"))
        self.pump_new_listing_min_momentum = float(get_env("PUMP_NEW_LISTING_MIN_MOMENTUM", "0.3"))

        # Pump ATR-based trailing stop
        self.pump_trail_initial_atr_mult = float(get_env("PUMP_TRAIL_INITIAL_ATR_MULT", "2.0"))
        self.pump_trail_atr_mult = float(get_env("PUMP_TRAIL_ATR_MULT", "1.2"))
        self.pump_trail_start_minutes = int(get_env("PUMP_TRAIL_START_MINUTES", "30"))

        # === FAST MODE (scan every 30s for limited time) ===
        self.fast_mode_enabled = self.parse_bool(get_env("FAST_MODE_ENABLED", "false"))
        self.fast_scan_interval_seconds = int(get_env("FAST_SCAN_INTERVAL_SECONDS", "30"))
        self.fast_mode_max_runtime_hours = int(get_env("FAST_MODE_MAX_RUNTIME_HOURS", "4"))

        # === AGGRESSIVE PUMP MODE (looser filters for more signals) ===
        self.pump_aggressive_mode = self.parse_bool(get_env("PUMP_AGGRESSIVE_MODE", "false"))
        self.pump_aggressive_min_24h_return = float(get_env("PUMP_AGGRESSIVE_MIN_24H_RETURN", "0.10"))
        self.pump_aggressive_max_24h_return = float(get_env("PUMP_AGGRESSIVE_MAX_24H_RETURN", "50.00"))
        self.pump_aggressive_min_rvol = float(get_env("PUMP_AGGRESSIVE_MIN_RVOL", "1.0"))
        self.pump_aggressive_min_momentum = float(get_env("PUMP_AGGRESSIVE_MIN_MOMENTUM", "3.0"))
        self.pump_aggressive_min_24h_quote_volume = float(get_env("PUMP_AGGRESSIVE_MIN_24H_QUOTE_VOLUME", "150000"))
        self.pump_aggressive_momentum_rsi_5m = int(get_env("PUMP_AGGRESSIVE_MOMENTUM_RSI_5M", "40"))
        self.pump_aggressive_price_above_ema1m = self.parse_bool(get_env("PUMP_AGGRESSIVE_PRICE_ABOVE_EMA1M", "false"))
        self.pump_aggressive_max_hold_minutes = int(get_env("PUMP_AGGRESSIVE_MAX_HOLD_MINUTES", "90"))

        # === PUMP DEBUG LOGGING ===
        self.pump_debug_logging = self.parse_bool(get_env("PUMP_DEBUG_LOGGING", "false"))

        # === POSITIONS FILE PATH ===
        self.positions_file_path = get_env("POSITIONS_FILE_PATH", "/var/lib/alpha-sniper/positions.json")

        # === TELEGRAM ENHANCEMENTS ===
        self.telegram_trade_screenshots_enabled = self.parse_bool(get_env("TELEGRAM_TRADE_SCREENSHOTS_ENABLED", "false"))
        self.telegram_daily_report_enabled = self.parse_bool(get_env("TELEGRAM_DAILY_REPORT_ENABLED", "true"))

        # === DRIFT DETECTION ===
        self.drift_detection_enabled = self.parse_bool(get_env("DRIFT_DETECTION_ENABLED", "true"))
        self.drift_max_stall_multiplier = int(get_env("DRIFT_MAX_STALL_MULTIPLIER", "3"))  # max(3 * scan_interval, 600s)

        if not self.sim_mode:
            if not self.mexc_api_key or not self.mexc_secret_key:
                raise Exception("Live mode requires MEXC_API_KEY and MEXC_SECRET_KEY in the environment")

        # Store get_env for use in instance methods
        self._get_env = get_env

    def get_pump_thresholds(self, regime: str) -> PumpThresholds:
        """
        Get regime-specific pump thresholds with fallback logic:
        1. Try regime-specific env var (e.g., PUMP_STRONG_BULL_MIN_SCORE)
        2. Fall back to base env var (e.g., PUMP_MIN_SCORE)
        3. Fall back to regime-based default (Grok's suggestions)

        Supported regimes: STRONG_BULL, SIDEWAYS, MILD_BEAR, FULL_BEAR
        """
        regime_upper = regime.upper().replace(' ', '_')

        # Define regime-based defaults (from Grok's analysis)
        regime_defaults = {
            'STRONG_BULL': {
                'min_24h_quote_volume': 100000,
                'min_score': 20,
                'min_rvol': 1.5,
                'min_24h_return': 0.05,
                'max_24h_return': 15.0,
                'min_momentum': 2.0,
                'new_listing_min_rvol': 1.0,
                'new_listing_min_score': 10,
                'new_listing_min_momentum': 0.5,
            },
            'PUMPY': {  # Alias for STRONG_BULL
                'min_24h_quote_volume': 100000,
                'min_score': 20,
                'min_rvol': 1.5,
                'min_24h_return': 0.05,
                'max_24h_return': 15.0,
                'min_momentum': 2.0,
                'new_listing_min_rvol': 1.0,
                'new_listing_min_score': 10,
                'new_listing_min_momentum': 0.5,
            },
            'SIDEWAYS': {
                'min_24h_quote_volume': 135000,
                'min_score': 30,
                'min_rvol': 1.6,
                'min_24h_return': 0.04,
                'max_24h_return': 12.0,
                'min_momentum': 3.0,
                'new_listing_min_rvol': 0.7,
                'new_listing_min_score': 8,
                'new_listing_min_momentum': 0.8,
            },
            'NEUTRAL': {  # Alias for SIDEWAYS
                'min_24h_quote_volume': 135000,
                'min_score': 30,
                'min_rvol': 1.6,
                'min_24h_return': 0.04,
                'max_24h_return': 12.0,
                'min_momentum': 3.0,
                'new_listing_min_rvol': 0.7,
                'new_listing_min_score': 8,
                'new_listing_min_momentum': 0.8,
            },
            'MILD_BEAR': {
                'min_24h_quote_volume': 200000,
                'min_score': 40,
                'min_rvol': 2.5,
                'min_24h_return': 0.07,
                'max_24h_return': 8.0,
                'min_momentum': 4.0,
                'new_listing_min_rvol': 1.5,
                'new_listing_min_score': 20,
                'new_listing_min_momentum': 1.5,
            },
            'FULL_BEAR': {
                'min_24h_quote_volume': 300000,
                'min_score': 50,
                'min_rvol': 3.0,
                'min_24h_return': 0.10,
                'max_24h_return': 5.0,
                'min_momentum': 5.0,
                'new_listing_min_rvol': 2.0,
                'new_listing_min_score': 30,
                'new_listing_min_momentum': 2.0,
            },
            'BEAR': {  # Alias for FULL_BEAR
                'min_24h_quote_volume': 300000,
                'min_score': 50,
                'min_rvol': 3.0,
                'min_24h_return': 0.10,
                'max_24h_return': 5.0,
                'min_momentum': 5.0,
                'new_listing_min_rvol': 2.0,
                'new_listing_min_score': 30,
                'new_listing_min_momentum': 2.0,
            },
        }

        # Get defaults for this regime (or SIDEWAYS as ultimate fallback)
        defaults = regime_defaults.get(regime_upper, regime_defaults['SIDEWAYS'])

        # Helper to get value with triple fallback: regime-specific → base → default
        def get_threshold(param_name: str, default_value):
            # Try regime-specific env var first
            regime_env_var = f"PUMP_{regime_upper}_{param_name.upper()}"
            regime_value = self._get_env(regime_env_var, None)
            if regime_value is not None and regime_value != '':
                try:
                    return type(default_value)(regime_value)
                except Exception:
                    pass

            # Try base env var
            base_env_var = f"PUMP_{param_name.upper()}"
            base_value = self._get_env(base_env_var, None)
            if base_value is not None and base_value != '':
                try:
                    return type(default_value)(base_value)
                except Exception:
                    pass

            # Use default
            return default_value

        # Build thresholds with fallback logic
        return PumpThresholds(
            min_24h_quote_volume=get_threshold('min_24h_quote_volume', defaults['min_24h_quote_volume']),
            min_score=get_threshold('min_score', defaults['min_score']),
            min_rvol=get_threshold('min_rvol', defaults['min_rvol']),
            min_24h_return=get_threshold('min_24h_return', defaults['min_24h_return']),
            max_24h_return=get_threshold('max_24h_return', defaults['max_24h_return']),
            min_momentum=get_threshold('min_momentum', defaults['min_momentum']),
            new_listing_min_rvol=get_threshold('new_listing_min_rvol', defaults['new_listing_min_rvol']),
            new_listing_min_score=get_threshold('new_listing_min_score', defaults['new_listing_min_score']),
            new_listing_min_momentum=get_threshold('new_listing_min_momentum', defaults['new_listing_min_momentum']),
        )

    @staticmethod
    def parse_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")

def get_config():
    return Config()
