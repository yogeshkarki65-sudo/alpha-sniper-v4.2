import os
import re
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv, find_dotenv


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
        # === CONFIG SOURCE DETECTION ===
        # Detect which .env file (if any) will be loaded
        # Systemd EnvironmentFile sets env vars BEFORE Python starts, so they always win
        dotenv_path = find_dotenv()
        dotenv_loaded = False

        # Check if SIM_MODE is already set by systemd (before dotenv)
        sim_mode_from_system = os.getenv("SIM_MODE")

        if dotenv_path:
            # Load dotenv (don't override existing env vars from systemd)
            load_dotenv(dotenv_path, override=False)
            dotenv_loaded = True
            print(f"[CONFIG_INIT] Loaded dotenv from: {dotenv_path}")
        else:
            print(f"[CONFIG_INIT] No .env file found, using system environment only")

        # Detect config source for SIM_MODE
        sim_mode_after_dotenv = os.getenv("SIM_MODE")
        if sim_mode_from_system:
            config_source = "systemd_env"
        elif dotenv_loaded and not sim_mode_from_system:
            config_source = f"dotenv ({dotenv_path})"
        else:
            config_source = "default"

        print(f"[CONFIG_SOURCE] SIM_MODE={sim_mode_after_dotenv} from {config_source}")

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

        # PUMP MAX LOSS GUARANTEE (synthetic watchdog protection)
        # This is the GUARANTEED max loss enforced by synthetic stop watchdog
        # Even if exchange stop placement fails or exchange has minimum distance constraints
        # Supports per-regime overrides: PUMP_MAX_LOSS_PCT_<REGIME> (e.g., PUMP_MAX_LOSS_PCT_SIDEWAYS)
        self.pump_max_loss_pct = float(get_env("PUMP_MAX_LOSS_PCT", "0.02"))  # 2% guaranteed max loss (default)
        self.pump_max_loss_watchdog_interval = float(get_env("PUMP_MAX_LOSS_WATCHDOG_INTERVAL", "1.0"))  # Check every 1 second

        # Entry-DETE (Smart Entry Timing Engine) - execution-level, NOT managed by DFE
        self.entry_dete_enabled = self.parse_bool(get_env("ENTRY_DETE_ENABLED", "false"))
        self.entry_dete_max_wait_seconds = int(get_env("ENTRY_DETE_MAX_WAIT_SECONDS", "180"))
        self.entry_dete_min_triggers = int(get_env("ENTRY_DETE_MIN_TRIGGERS", "2"))
        self.entry_dete_min_dip_pct = float(get_env("ENTRY_DETE_MIN_DIP_PCT", "0.005"))
        self.entry_dete_max_dip_pct = float(get_env("ENTRY_DETE_MAX_DIP_PCT", "0.02"))
        self.entry_dete_volume_multiplier = float(get_env("ENTRY_DETE_VOLUME_MULTIPLIER", "1.1"))

        # === PUMP-ONLY MODE ===
        # Simplified mode that uses ONLY the pump engine with stricter filters
        # Supports both PUMP_ONLY and PUMP_ONLY_MODE env vars (PUMP_ONLY takes precedence)
        pump_only_raw = get_env("PUMP_ONLY", get_env("PUMP_ONLY_MODE", "false"))
        self.pump_only_mode = self.parse_bool(pump_only_raw)

        # Stricter pump filters for pump-only mode (LOWERED DEFAULTS FOR MORE SIGNALS)
        self.pump_min_24h_return = float(get_env("PUMP_MIN_24H_RETURN", "0.02"))
        self.pump_max_24h_return = float(get_env("PUMP_MAX_24H_RETURN", "10.0"))
        self.pump_min_rvol = float(get_env("PUMP_MIN_RVOL", "0.8"))
        self.pump_min_momentum_1h = float(get_env("PUMP_MIN_MOMENTUM_1H", "5.0"))
        self.pump_min_24h_quote_volume = float(get_env("PUMP_MIN_24H_QUOTE_VOLUME", "200000"))
        self.pump_min_score = int(get_env("PUMP_MIN_SCORE", "15"))
        self.pump_max_hold_hours = int(get_env("PUMP_MAX_HOLD_HOURS", "24"))  # 24 hours max hold time

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

        # === POSITION SIZING SAFETY ===
        # Allow bumping position size to meet exchange minimum notional
        # Only enabled if bumped notional stays within risk_budget * tolerance
        self.allow_min_notional_bump = self.parse_bool(get_env("ALLOW_MIN_NOTIONAL_BUMP", "false"))
        self.min_notional_bump_tolerance = float(get_env("MIN_NOTIONAL_BUMP_TOLERANCE", "1.10"))  # 10% over risk budget max

        # === PERFORMANCE OPTIMIZATIONS ===
        # Caching and rate limiting to reduce API calls and improve scan speed
        self.exchange_info_cache_seconds = int(get_env("EXCHANGE_INFO_CACHE_SECONDS", "300"))  # Cache symbol info for 5 min
        self.max_concurrent_api_calls = int(get_env("MAX_CONCURRENT_API_CALLS", "10"))  # Limit concurrent API requests

        # === POSITIONS FILE PATH ===
        self.positions_file_path = get_env("POSITIONS_FILE_PATH", "/var/lib/alpha-sniper/positions.json")

        # === TELEGRAM ENHANCEMENTS ===
        self.telegram_trade_screenshots_enabled = self.parse_bool(get_env("TELEGRAM_TRADE_SCREENSHOTS_ENABLED", "false"))
        self.telegram_daily_report_enabled = self.parse_bool(get_env("TELEGRAM_DAILY_REPORT_ENABLED", "true"))

        # Telegram "full story" message controls
        self.telegram_trade_alerts = self.parse_bool(get_env("TELEGRAM_TRADE_ALERTS", "true"))  # Entry/exit alerts
        self.telegram_scan_summary = self.parse_bool(get_env("TELEGRAM_SCAN_SUMMARY", "true"))  # Scan cycle summary
        self.telegram_why_no_trade = self.parse_bool(get_env("TELEGRAM_WHY_NO_TRADE", "true"))  # Why no trade explanation
        self.telegram_max_msg_len = int(get_env("TELEGRAM_MAX_MSG_LEN", "3500"))  # Max message length (truncate)

        # === SYMBOL BLACKLIST (symbols causing API errors or untradeable) ===
        blacklist_str = get_env("SYMBOL_BLACKLIST", "")
        self.symbol_blacklist = set([s.strip() for s in blacklist_str.split(',') if s.strip()])

        # === VPS PERFORMANCE LIMITS ===
        # For low-memory VPS deployments
        self.scan_universe_max = int(get_env("SCAN_UNIVERSE_MAX", "800"))  # Max symbols to scan
        self.scan_sleep_secs = float(get_env("SCAN_SLEEP_SECS", "0"))  # Optional sleep between scans (pacing)

        # === DRIFT DETECTION ===
        self.drift_detection_enabled = self.parse_bool(get_env("DRIFT_DETECTION_ENABLED", "true"))
        self.drift_max_stall_multiplier = int(get_env("DRIFT_MAX_STALL_MULTIPLIER", "3"))  # max(3 * scan_interval, 600s)

        # === DDL (Decision Layer) Configuration ===
        self.ddl_enabled = self.parse_bool(get_env("DDL_ENABLED", "true"))
        self.ddl_update_interval_seconds = int(get_env("DDL_UPDATE_INTERVAL_SECONDS", "300"))
        self.ddl_min_time_in_mode_seconds = int(get_env("DDL_MIN_TIME_IN_MODE_SECONDS", "900"))
        self.ddl_density_window_seconds = int(get_env("DDL_DENSITY_WINDOW_SECONDS", "7200"))

        # DDL thresholds
        self.ddl_harvest_threshold = float(get_env("DDL_HARVEST_THRESHOLD", "0.70"))
        self.ddl_harvest_exit_threshold = float(get_env("DDL_HARVEST_EXIT_THRESHOLD", "0.55"))
        self.ddl_grind_threshold = float(get_env("DDL_GRIND_THRESHOLD", "0.40"))
        self.ddl_grind_exit_threshold = float(get_env("DDL_GRIND_EXIT_THRESHOLD", "0.30"))
        self.ddl_defense_threshold = float(get_env("DDL_DEFENSE_THRESHOLD", "0.25"))

        # === Quarantine Configuration ===
        self.quarantine_failure_threshold = int(get_env("QUARANTINE_FAILURE_THRESHOLD", "3"))
        self.quarantine_failure_window = int(get_env("QUARANTINE_FAILURE_WINDOW_SECONDS", "1800"))
        self.quarantine_initial_duration = int(get_env("QUARANTINE_INITIAL_DURATION_SECONDS", "7200"))
        self.quarantine_extended_duration = int(get_env("QUARANTINE_EXTENDED_DURATION_SECONDS", "86400"))
        self.quarantine_extended_threshold = int(get_env("QUARANTINE_EXTENDED_THRESHOLD", "3"))

        # === Scratch Exit Configuration ===
        self.scratch_enabled = self.parse_bool(get_env("SCRATCH_ENABLED", "true"))
        self.scratch_timeout_harvest = int(get_env("SCRATCH_TIMEOUT_HARVEST_SECONDS", "30"))
        self.scratch_timeout_grind = int(get_env("SCRATCH_TIMEOUT_GRIND_SECONDS", "60"))
        self.scratch_timeout_defense = int(get_env("SCRATCH_TIMEOUT_DEFENSE_SECONDS", "20"))
        self.scratch_timeout_observe = int(get_env("SCRATCH_TIMEOUT_OBSERVE_SECONDS", "60"))
        self.scratch_min_mfe_pct = float(get_env("SCRATCH_MIN_MFE_PCT", "0.3"))
        self.scratch_max_mae_pct = float(get_env("SCRATCH_MAX_MAE_PCT", "-0.5"))

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
                'min_24h_return': 5.0,  # 5% (percentage format)
                'max_24h_return': 1500.0,  # 1500% max
                'min_momentum': 2.0,
                'new_listing_min_rvol': 1.0,
                'new_listing_min_score': 10,
                'new_listing_min_momentum': 0.5,
            },
            'PUMPY': {  # Alias for STRONG_BULL
                'min_24h_quote_volume': 100000,
                'min_score': 20,
                'min_rvol': 1.5,
                'min_24h_return': 5.0,  # 5%
                'max_24h_return': 1500.0,  # 1500% max
                'min_momentum': 2.0,
                'new_listing_min_rvol': 1.0,
                'new_listing_min_score': 10,
                'new_listing_min_momentum': 0.5,
            },
            'SIDEWAYS': {
                'min_24h_quote_volume': 150000,  # Slightly higher for safety
                'min_score': 35,  # More selective
                'min_rvol': 1.8,  # Require stronger conviction
                'min_24h_return': 5.0,  # 5% (in percentage format to match return_24h calculation)
                'max_24h_return': 400.0,  # 400% max (not 1200%)
                'min_momentum': 4.0,  # Require stronger momentum
                'new_listing_min_rvol': 0.7,
                'new_listing_min_score': 8,
                'new_listing_min_momentum': 0.8,
            },
            'NEUTRAL': {  # Alias for SIDEWAYS
                'min_24h_quote_volume': 150000,
                'min_score': 35,
                'min_rvol': 1.8,
                'min_24h_return': 5.0,  # 5%
                'max_24h_return': 400.0,  # 400% max
                'min_momentum': 4.0,
                'new_listing_min_rvol': 0.7,
                'new_listing_min_score': 8,
                'new_listing_min_momentum': 0.8,
            },
            'MILD_BEAR': {
                'min_24h_quote_volume': 200000,
                'min_score': 40,
                'min_rvol': 2.5,
                'min_24h_return': 7.0,  # 7% (percentage format)
                'max_24h_return': 800.0,  # 800% max
                'min_momentum': 4.0,
                'new_listing_min_rvol': 1.5,
                'new_listing_min_score': 20,
                'new_listing_min_momentum': 1.5,
            },
            'FULL_BEAR': {
                'min_24h_quote_volume': 300000,
                'min_score': 50,
                'min_rvol': 3.0,
                'min_24h_return': 10.0,  # 10% (percentage format)
                'max_24h_return': 500.0,  # 500% max
                'min_momentum': 5.0,
                'new_listing_min_rvol': 2.0,
                'new_listing_min_score': 30,
                'new_listing_min_momentum': 2.0,
            },
            'BEAR': {  # Alias for FULL_BEAR
                'min_24h_quote_volume': 300000,
                'min_score': 50,
                'min_rvol': 3.0,
                'min_24h_return': 10.0,  # 10%
                'max_24h_return': 500.0,  # 500% max
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
                except:
                    pass

            # Try base env var
            base_env_var = f"PUMP_{param_name.upper()}"
            base_value = self._get_env(base_env_var, None)
            if base_value is not None and base_value != '':
                try:
                    return type(default_value)(base_value)
                except:
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

    def get_pump_max_loss_pct(self, regime: str) -> float:
        """
        Get pump max loss percentage with optional per-regime override

        Checks for regime-specific override first (e.g., PUMP_MAX_LOSS_PCT_SIDEWAYS),
        then falls back to default pump_max_loss_pct

        Args:
            regime: Current market regime (e.g., "SIDEWAYS", "STRONG_BULL", "MILD_BEAR")

        Returns:
            Max loss percentage (e.g., 0.02 for 2%)

        Examples:
            PUMP_MAX_LOSS_PCT=0.02 (default 2% for all regimes)
            PUMP_MAX_LOSS_PCT_SIDEWAYS=0.03 (3% for sideways only)
            PUMP_MAX_LOSS_PCT_STRONG_BULL=0.015 (1.5% for strong bull only)
        """
        # Normalize regime name
        regime_upper = regime.upper().replace(' ', '_').replace('-', '_')

        # Check for regime-specific override
        override_key = f"PUMP_MAX_LOSS_PCT_{regime_upper}"
        override_value = self._get_env(override_key, None)

        if override_value:
            try:
                return float(override_value)
            except (ValueError, TypeError):
                # Invalid override value, fall back to default
                pass

        # Fall back to default
        return self.pump_max_loss_pct

    @staticmethod
    def parse_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")

def get_config():
    return Config()
