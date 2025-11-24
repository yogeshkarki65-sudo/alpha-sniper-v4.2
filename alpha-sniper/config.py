import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        self.sim_mode = self.parse_bool(os.getenv("SIM_MODE", "true"))
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

        if not self.sim_mode:
            if not self.mexc_api_key or not self.mexc_secret_key:
                raise Exception("Live mode requires MEXC_API_KEY and MEXC_SECRET_KEY in the environment")

    @staticmethod
    def parse_bool(value):
        return value.lower() in ("true", "1", "yes")

def get_config():
    return Config()
