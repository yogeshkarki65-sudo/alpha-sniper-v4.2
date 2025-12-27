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
            self.logger.info(f"📱 Telegram notifications enabled (chat_id={self.chat_id})")
            # Send test message on startup
            self.send_test_message()
        else:
            self.logger.info("📱 Telegram notifications disabled (no token/chat_id in config)")

    def send(self, msg: str, description: str = "Message") -> bool:
        """
        Send message to Telegram with robust error handling

        Args:
            msg: Message text to send
            description: Short description for logging (e.g., "Startup", "Trade Open")

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False

        try:
            msg = truncate_message(msg, max_length=4000)
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"}
            resp = requests.post(url, json=payload, timeout=5)

            if resp.status_code == 200:
                self.logger.info(f"[TELEGRAM] ✅ {description} sent successfully")
                return True
            else:
                self.logger.error(
                    f"[TELEGRAM] ❌ {description} failed: HTTP {resp.status_code} - {resp.text[:200]}"
                )
                return False

        except requests.exceptions.Timeout:
            self.logger.error(f"[TELEGRAM] ❌ {description} failed: Request timeout (>5s)")
            return False
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"[TELEGRAM] ❌ {description} failed: Connection error - {str(e)[:100]}")
            return False
        except Exception as e:
            self.logger.error(f"[TELEGRAM] ❌ {description} failed: {type(e).__name__} - {str(e)[:100]}")
            return False

    def send_message(self, msg: str) -> bool:
        """
        Convenience method for sending plain messages (backward compatible)

        Args:
            msg: Message text to send

        Returns:
            True if sent successfully, False otherwise
        """
        return self.send(msg, description="Alert")

    def send_test_message(self) -> bool:
        """
        Send a test message to verify Telegram is working

        Returns:
            True if test message sent successfully, False otherwise
        """
        from datetime import datetime, timezone
        msg = (
            f"🧪 <b>Telegram Test</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Alpha Sniper Telegram is configured correctly!\n"
            f"Chat ID: {self.chat_id}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        result = self.send(msg, description="Test message")
        if result:
            self.logger.info("[TELEGRAM] Test message sent successfully - Telegram is working!")
        else:
            self.logger.error("[TELEGRAM] Test message failed - check bot token and chat ID!")
        return result


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
