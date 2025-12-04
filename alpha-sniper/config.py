import os
import re
from dotenv import load_dotenv

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

        # Stricter pump filters for pump-only mode
        self.pump_min_24h_return = float(get_env("PUMP_MIN_24H_RETURN", "0.80"))
        self.pump_max_24h_return = float(get_env("PUMP_MAX_24H_RETURN", "3.50"))
        self.pump_min_rvol = float(get_env("PUMP_MIN_RVOL", "2.8"))
        self.pump_min_momentum_1h = float(get_env("PUMP_MIN_MOMENTUM_1H", "40"))
        self.pump_min_24h_quote_volume = float(get_env("PUMP_MIN_24H_QUOTE_VOLUME", "800000"))
        self.pump_min_score = int(get_env("PUMP_MIN_SCORE", "85"))
        self.pump_max_hold_hours = int(get_env("PUMP_MAX_HOLD_HOURS", "4"))

        # Pump ATR-based trailing stop
        self.pump_trail_initial_atr_mult = float(get_env("PUMP_TRAIL_INITIAL_ATR_MULT", "2.0"))
        self.pump_trail_atr_mult = float(get_env("PUMP_TRAIL_ATR_MULT", "1.2"))
        self.pump_trail_start_minutes = int(get_env("PUMP_TRAIL_START_MINUTES", "30"))

        if not self.sim_mode:
            if not self.mexc_api_key or not self.mexc_secret_key:
                raise Exception("Live mode requires MEXC_API_KEY and MEXC_SECRET_KEY in the environment")

    @staticmethod
    def parse_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")

def get_config():
    return Config()
