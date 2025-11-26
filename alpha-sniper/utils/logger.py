import logging
import os

def setup_logger():
    """
    Set up logger with console + file handlers
    - Console: INFO+
    - logs/bot.log: INFO+
    - logs/bot_debug.log: DEBUG+
    """
    logger = logging.getLogger("alpha_sniper")

    if not logger.hasHandlers():
        # Ensure logs folder exists
        os.makedirs("logs", exist_ok=True)

        # Set logger to DEBUG so handlers can filter
        logger.setLevel(logging.DEBUG)

        # INFO file handler
        fh_info = logging.FileHandler("logs/bot.log")
        fh_info.setLevel(logging.INFO)

        # DEBUG file handler
        fh_debug = logging.FileHandler("logs/bot_debug.log")
        fh_debug.setLevel(logging.DEBUG)

        # Console handler (INFO+)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            "%Y-%m-%d %H:%M:%S"
        )
        fh_info.setFormatter(formatter)
        fh_debug.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh_info)
        logger.addHandler(fh_debug)
        logger.addHandler(ch)

    return logger
