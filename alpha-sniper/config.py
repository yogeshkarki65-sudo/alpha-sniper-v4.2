import os
from dotenv import load_dotenv

class Config:
    load_dotenv()

    MEXC_API_KEY = os.getenv("MEXC_API_KEY")
    MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    SIM_MODE = os.getenv("SIM_MODE", "false").lower() == "true"
    STARTING_EQUITY = float(os.getenv("STARTING_EQUITY", 1000))

    MAX_PORTFOLIO_HEAT = float(os.getenv("MAX_PORTFOLIO_HEAT", 0.012))
    MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", 5))
    MAX_SPREAD_PCT = float(os.getenv("MAX_SPREAD_PCT", 0.9))
    ENABLE_DAILY_LOSS_LIMIT = os.getenv("ENABLE_DAILY_LOSS_LIMIT", "true").lower() == "true"
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", 0.03))
    EXCHANGE_OUTAGE_GRACE_MINUTES = int(os.getenv("EXCHANGE_OUTAGE_GRACE_MINUTES", 30))

    RISK_PER_TRADE_BULL = float(os.getenv("RISK_PER_TRADE_BULL", 0.0025))
    RISK_PER_TRADE_SIDEWAYS = float(os.getenv("RISK_PER_TRADE_SIDEWAYS", 0.0025))
    RISK_PER_TRADE_MILD_BEAR = float(os.getenv("RISK_PER_TRADE_MILD_BEAR", 0.0018))
    RISK_PER_TRADE_DEEP_BEAR = float(os.getenv("RISK_PER_TRADE_DEEP_BEAR", 0.0015))

    PUMP_ENGINE_ENABLED = os.getenv("PUMP_ENGINE_ENABLED", "true").lower() == "true"
    PUMP_RISK_PER_TRADE = float(os.getenv("PUMP_RISK_PER_TRADE", 0.0010))
    PUMP_ALLOCATION_MIN = float(os.getenv("PUMP_ALLOCATION_MIN", 0.20))
    PUMP_ALLOCATION_MAX = float(os.getenv("PUMP_ALLOCATION_MAX", 0.35))
    PUMP_MAX_CONCURRENT = int(os.getenv("PUMP_MAX_CONCURRENT", 2))

    MIN_SCORE = int(os.getenv("MIN_SCORE", 80))
    MIN_24H_QUOTE_VOLUME = float(os.getenv("MIN_24H_QUOTE_VOLUME", 50000))
    MAX_FUNDING_8H_SHORT = float(os.getenv("MAX_FUNDING_8H_SHORT", 0.00035))
    SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", 300))
