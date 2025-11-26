"""
Telegram alert module for Alpha Sniper V4.2
"""
import requests
from utils.helpers import truncate_message


class TelegramNotifier:
    """
    Simple Telegram notification wrapper
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.enabled = False

        if config.telegram_bot_token and config.telegram_chat_id:
            self.bot_token = config.telegram_bot_token
            self.chat_id = config.telegram_chat_id
            self.enabled = True
            self.logger.info("📱 Telegram notifications enabled")
        else:
            self.logger.info("📱 Telegram notifications disabled (no token/chat_id in config)")

    def send(self, msg: str):
        """
        Send message to Telegram
        """
        if not self.enabled:
            return

        try:
            msg = truncate_message(msg, max_length=4000)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"}
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code != 200:
                self.logger.debug(f"Telegram send failed: {resp.status_code} {resp.text}")
        except Exception as e:
            self.logger.debug(f"Telegram error: {e}")


# Legacy function for backward compatibility
def send_telegram(msg: str):
    """
    Legacy send function (requires environment variables)
    """
    import os
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return

    try:
        msg = truncate_message(msg, max_length=4000)
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg}
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass
