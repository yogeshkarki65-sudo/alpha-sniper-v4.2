"""
Settings Configuration for Alpha Sniper v4.2 (Async)

Uses pydantic-settings v2 for type-safe configuration with .env support.
All settings have sensible defaults and can be overridden via environment variables.
"""

from __future__ import annotations

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with .env file support.

    Environment variables should be prefixed with ALPHA_
    Example: ALPHA_EXCHANGE_ID=mexc
    """

    # === EXCHANGE SETTINGS ===
    EXCHANGE_ID: str = Field(default="mexc", description="Exchange ID (mexc, binance, etc.)")
    API_KEY: Optional[str] = Field(default=None, description="Exchange API key")
    API_SECRET: Optional[str] = Field(default=None, description="Exchange API secret")
    TESTNET: bool = Field(default=False, description="Use testnet/sandbox mode")

    # === SCAN SETTINGS ===
    SCAN_CONCURRENCY: int = Field(default=5, ge=1, le=20, description="Max concurrent OHLCV fetches")
    SCAN_INTERVAL_SECONDS: int = Field(default=300, ge=10, description="Scan interval (seconds)")
    TIMEFRAME: str = Field(default="1m", description="Default OHLCV timeframe")

    # === UNIVERSE SETTINGS ===
    UNIVERSE_SIZE: int = Field(default=80, ge=10, le=500, description="Max symbols in universe")
    UNIVERSE_BASE_QUOTE: str = Field(default="USDT", description="Quote currency filter")
    UNIVERSE_MIN_QUOTE_VOLUME: float = Field(default=50000.0, ge=0, description="Min 24h quote volume")
    UNIVERSE_CACHE_TTL: int = Field(default=300, ge=60, description="Universe cache TTL (seconds)")

    # === DATABASE SETTINGS ===
    DB_PATH: str = Field(default="./data/alpha.db", description="SQLite database path")

    # === TELEGRAM SETTINGS ===
    TELEGRAM_TOKEN: Optional[str] = Field(default=None, description="Telegram bot token")
    TELEGRAM_CHAT_ID: Optional[str] = Field(default=None, description="Telegram chat ID")
    TELEGRAM_ENABLED: bool = Field(default=True, description="Enable Telegram notifications")
    TELEGRAM_MAX_QUEUE: int = Field(default=500, ge=10, description="Max queued messages")

    # === MODE SETTINGS ===
    MODE: str = Field(default="LIVE", description="Trading mode: LIVE or SIM")
    SIM_STARTING_EQUITY: float = Field(default=1000.0, ge=100, description="Starting equity for SIM mode")

    # === RISK MANAGEMENT ===
    MAX_PORTFOLIO_HEAT: float = Field(default=0.012, ge=0.001, le=0.1, description="Max portfolio heat")
    MAX_CONCURRENT_POSITIONS: int = Field(default=5, ge=1, le=20, description="Max concurrent positions")
    RISK_PER_TRADE: float = Field(default=0.0025, ge=0.0001, le=0.05, description="Risk per trade")

    # === PUMP ENGINE SETTINGS ===
    PUMP_ONLY_MODE: bool = Field(default=True, description="Only trade pump signals")
    PUMP_MAX_AGE_HOURS: int = Field(default=129, ge=1, description="Max age for pump signals (hours)")
    MIN_SCORE: int = Field(default=28, ge=0, le=100, description="Min pump score")
    MIN_24H_QUOTE_VOLUME: float = Field(default=47000.0, ge=0, description="Min 24h quote volume")

    # === ORDER VIABILITY (v4.2.3) ===
    MIN_VIABLE_TRADE_USD: float = Field(default=5.0, ge=1.0, description="Min viable trade size USD")
    MAX_SPREAD_PCT_ORDER: float = Field(default=0.30, ge=0.01, description="Max spread % for orders")
    MIN_DEPTH_MULTIPLE: float = Field(default=200.0, ge=10, description="Min depth multiple")
    MIN_DEPTH_USD: float = Field(default=0.0, ge=0, description="Min absolute depth USD (0=disabled)")

    # === LIQUIDITY GUARD ===
    MIN_LIQ_FACTOR: float = Field(default=0.4, ge=0.1, le=1.0, description="Min liquidity factor")
    MIN_ADJUSTED_USD: float = Field(default=5.0, ge=1.0, description="Min adjusted size USD")

    # === LOGGING ===
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    LOG_FORMAT: str = Field(default="json", description="Log format (json, text)")
    LOG_FILE: Optional[str] = Field(default="./logs/bot.log", description="Log file path")

    # === PERFORMANCE ===
    INDICATOR_CACHE_ENABLED: bool = Field(default=True, description="Enable indicator caching")
    MARKET_DATA_CACHE_TTL: int = Field(default=60, ge=10, description="Market data cache TTL (seconds)")

    # === HEALTH CHECK ===
    HEALTH_CHECK_ENABLED: bool = Field(default=False, description="Enable /healthz HTTP endpoint")
    HEALTH_CHECK_PORT: int = Field(default=8080, ge=1024, le=65535, description="Health check HTTP port")

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALPHA_",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra env vars
    )

    @property
    def is_live(self) -> bool:
        """Check if running in LIVE mode."""
        return self.MODE.upper() == "LIVE"

    @property
    def is_sim(self) -> bool:
        """Check if running in SIM mode."""
        return self.MODE.upper() == "SIM"

    def validate_required_for_live(self):
        """
        Validate that required settings are present for LIVE mode.

        Raises:
            ValueError: If required settings are missing
        """
        if self.is_live:
            if not self.API_KEY or not self.API_SECRET:
                raise ValueError(
                    "LIVE mode requires ALPHA_API_KEY and ALPHA_API_SECRET"
                )

    def __repr__(self) -> str:
        return (
            f"Settings(mode={self.MODE}, exchange={self.EXCHANGE_ID}, "
            f"universe_size={self.UNIVERSE_SIZE}, concurrency={self.SCAN_CONCURRENCY})"
        )


# Global settings instance (singleton pattern)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get or create global settings instance.

    Returns:
        Settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.validate_required_for_live()
    return _settings


def reload_settings() -> Settings:
    """
    Force reload settings from .env file.

    Returns:
        Fresh Settings instance
    """
    global _settings
    _settings = Settings()
    _settings.validate_required_for_live()
    return _settings
