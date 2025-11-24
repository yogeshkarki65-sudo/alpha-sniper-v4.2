import logging
import os

def setup_logger():
    # Ensure logs folder exists
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger("AlphaSniper")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler("logs/bot.log")
    fh.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
