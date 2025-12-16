"""
Production logging setup with rotating file handlers

Logs to:
  - /var/log/alpha-sniper/alpha-sniper-{mode}.log (INFO+)
  - /var/log/alpha-sniper/alpha-sniper-{mode}-debug.log (DEBUG+)
  - Console (INFO+)

For local dev:
  - Falls back to ./logs/ if /var/log/alpha-sniper/ doesn't exist
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger_production(mode: str = "sim") -> logging.Logger:
    """
    Setup production-grade logging with rotation

    Args:
        mode: 'sim' or 'live' (affects log file names)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("alpha_sniper")

    # Clear any existing handlers (avoid duplicates)
    logger.handlers.clear()

    # Set logger to DEBUG so handlers can filter
    logger.setLevel(logging.DEBUG)

    # Determine log directory
    prod_log_dir = Path("/var/log/alpha-sniper")
    dev_log_dir = Path("./logs")

    if prod_log_dir.exists() and os.access(prod_log_dir, os.W_OK):
        log_dir = prod_log_dir
        is_production = True
    else:
        log_dir = dev_log_dir
        log_dir.mkdir(exist_ok=True)
        is_production = False

    # Log file paths
    info_log = log_dir / f"alpha-sniper-{mode}.log"
    debug_log = log_dir / f"alpha-sniper-{mode}-debug.log"

    # Rotating file handler for INFO logs (50MB max, 5 backups)
    fh_info = RotatingFileHandler(
        info_log,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=5,
        encoding='utf-8'
    )
    fh_info.setLevel(logging.INFO)

    # Rotating file handler for DEBUG logs (100MB max, 3 backups)
    fh_debug = RotatingFileHandler(
        debug_log,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=3,
        encoding='utf-8'
    )
    fh_debug.setLevel(logging.DEBUG)

    # Console handler (INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter with more detail for production
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    fh_info.setFormatter(formatter)
    fh_debug.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers
    logger.addHandler(fh_info)
    logger.addHandler(fh_debug)
    logger.addHandler(ch)

    # Log where we're logging to
    location = "PRODUCTION" if is_production else "DEVELOPMENT"
    logger.info(f"📝 Logging initialized [{location}]")
    logger.info(f"   INFO:  {info_log}")
    logger.info(f"   DEBUG: {debug_log}")

    return logger


def setup_logger():
    """
    Backwards compatibility wrapper for existing code

    This allows main.py to continue using utils.setup_logger()
    without changes, but it will use the production logger in
    production environment.
    """
    # Detect if we're in production
    prod_log_dir = Path("/var/log/alpha-sniper")
    if prod_log_dir.exists() and os.access(prod_log_dir, os.W_OK):
        # In production, use default sim mode
        # (run.py will call setup_logger_production directly with correct mode)
        return setup_logger_production(mode="sim")
    else:
        # Local dev: use original simple logger
        from utils.logger import setup_logger as setup_logger_original
        return setup_logger_original()
