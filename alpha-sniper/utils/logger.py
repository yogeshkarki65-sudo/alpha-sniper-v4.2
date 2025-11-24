import logging
import os

def setup_logger():
    logger = logging.getLogger("alpha_sniper")
    
    if not logger.hasHandlers():
        # Ensure logs folder exists
        os.makedirs("logs", exist_ok=True)

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

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
