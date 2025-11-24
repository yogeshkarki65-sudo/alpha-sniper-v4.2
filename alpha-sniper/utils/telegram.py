import requests
import logging

class Telegram:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def send_alert(self, message):
        if self.config.TELEGRAM_BOT_TOKEN and self.config.TELEGRAM_CHAT_ID:
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': message
            }
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                self.logger.error(f"Failed to send message: {response.text}")
