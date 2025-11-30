import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        self.sim_mode = self.parse_bool(os.getenv("SIM_MODE", "true"))
        self.sim_data_source = os.getenv("SIM_DATA_SOURCE", "FAKE").upper()  # FAKE or LIVE_DATA
        self.mexc_api_key = os.getenv("MEXC_API_KEY", "")
        self.mexc_secret_key = os.getenv("MEXC_SECRET_KEY", "")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.starting_equity = float(os.getenv("STARTING_EQUITY", 1000))
        self.scan_interval_seconds = int(os.getenv("SCAN_INTERVAL_SECONDS", 300))
        self.max_portfolio_heat = float(os.getenv("MAX_PORTFOLIO_HEAT", 0.012))
        self.max_concurrent_positions = int(os.getenv("MAX_CONCURRENT_POSITIONS", 5))
        self.max_spread_pct = float(os.getenv("MAX_SPREAD_PCT", 0.9))
        self.enable_daily_loss_limit = self.parse_bool(os.getenv("ENABLE_DAILY_LOSS_LIMIT", "true"))
        self.max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", 0.03))
        self.exchange_outage_grace_minutes = int(os.getenv("EXCHANGE_OUTAGE_GRACE_MINUTES", 30))
        self.risk_per_trade_bull = float(os.getenv("RISK_PER_TRADE_BULL", 0.0025))
        self.risk_per_trade_sideways = float(os.getenv("RISK_PER_TRADE_SIDEWAYS", 0.0025))
        self.risk_per_trade_mild_bear = float(os.getenv("RISK_PER_TRADE_MILD_BEAR", 0.0018))
        self.risk_per_trade_deep_bear = float(os.getenv("RISK_PER_TRADE_DEEP_BEAR", 0.0015))
        self.pump_engine_enabled = self.parse_bool(os.getenv("PUMP_ENGINE_ENABLED", "true"))
        self.pump_risk_per_trade = float(os.getenv("PUMP_RISK_PER_TRADE", 0.0010))
        self.pump_allocation_min = float(os.getenv("PUMP_ALLOCATION_MIN", 0.20))
        self.pump_allocation_max = float(os.getenv("PUMP_ALLOCATION_MAX", 0.35))
        self.pump_max_concurrent = int(os.getenv("PUMP_MAX_CONCURRENT", 2))
        self.min_score = int(os.getenv("MIN_SCORE", 80))
        self.min_24h_quote_volume = float(os.getenv("MIN_24H_QUOTE_VOLUME", 50000))
        self.max_funding_8h_short = float(os.getenv("MAX_FUNDING_8H_SHORT", 0.00035))

        # === V4.2 ADDITIVE OVERLAYS ===

        # UPGRADE A: Sideways Coiled Volatility Boost
        self.sideways_coil_enabled = self.parse_bool(os.getenv("SIDEWAYS_COIL_ENABLED", "true"))
        self.sideways_coil_atr_mult = float(os.getenv("SIDEWAYS_COIL_ATR_MULT", 1.5))
        self.sideways_rsi_divergence_enabled = self.parse_bool(os.getenv("SIDEWAYS_RSI_DIVERGENCE_ENABLED", "true"))
        self.sideways_coil_score_boost = int(os.getenv("SIDEWAYS_COIL_SCORE_BOOST", 10))

        # UPGRADE B: Short Funding Overlay
        self.short_funding_overlay_enabled = self.parse_bool(os.getenv("SHORT_FUNDING_OVERLAY_ENABLED", "true"))
        self.short_min_funding_8h = float(os.getenv("SHORT_MIN_FUNDING_8H", 0.00025))

        # UPGRADE C: Pump Engine Allocation Feedback Loop
        self.pump_feedback_enabled = self.parse_bool(os.getenv("PUMP_FEEDBACK_ENABLED", "true"))
        self.pump_feedback_lookback = int(os.getenv("PUMP_FEEDBACK_LOOKBACK", 20))
        self.pump_feedback_low_r_thres = float(os.getenv("PUMP_FEEDBACK_LOW_R_THRES", 0.5))
        self.pump_feedback_high_r_thres = float(os.getenv("PUMP_FEEDBACK_HIGH_R_THRES", 1.0))
        self.pump_allocation_min_base = float(os.getenv("PUMP_ALLOCATION_MIN_BASE", 0.20))
        self.pump_allocation_max_base = float(os.getenv("PUMP_ALLOCATION_MAX_BASE", 0.35))
        self.pump_allocation_min_floor = float(os.getenv("PUMP_ALLOCATION_MIN_FLOOR", 0.15))
        self.pump_allocation_max_ceil = float(os.getenv("PUMP_ALLOCATION_MAX_CEIL", 0.40))

        # UPGRADE D: Liquidity-Aware Position Sizing
        self.liquidity_sizing_enabled = self.parse_bool(os.getenv("LIQUIDITY_SIZING_ENABLED", "true"))
        self.liquidity_spread_soft_limit = float(os.getenv("LIQUIDITY_SPREAD_SOFT_LIMIT", 0.7))
        self.liquidity_depth_good_level = float(os.getenv("LIQUIDITY_DEPTH_GOOD_LEVEL", 20000))
        self.liquidity_min_factor = float(os.getenv("LIQUIDITY_MIN_FACTOR", 0.25))

        # UPGRADE E: Correlation-Aware Portfolio Heat
        self.correlation_limit_enabled = self.parse_bool(os.getenv("CORRELATION_LIMIT_ENABLED", "true"))
        self.max_correlated_positions = int(os.getenv("MAX_CORRELATED_POSITIONS", 2))

        # Dynamic Filter Engine (DFE)
        self.dfe_enabled = self.parse_bool(os.getenv("DFE_ENABLED", "false"))

        # Pump engine age limit (managed by DFE if enabled)
        self.pump_max_age_hours = int(os.getenv("PUMP_MAX_AGE_HOURS", 72))

        if not self.sim_mode:
            if not self.mexc_api_key or not self.mexc_secret_key:
                raise Exception("Live mode requires MEXC_API_KEY and MEXC_SECRET_KEY in the environment")

    @staticmethod
    def parse_bool(value):
        return value.lower() in ("true", "1", "yes")

def get_config():
    return Config()
