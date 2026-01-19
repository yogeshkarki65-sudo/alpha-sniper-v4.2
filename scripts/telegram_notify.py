#!/usr/bin/env python3
"""
Telegram Notification Module for Alpha Sniper v4.2

Sends status updates and alerts to Telegram chat.

Setup:
1. Create a bot via @BotFather on Telegram
2. Get your bot token
3. Get your chat ID (send /start to bot, check https://api.telegram.org/bot<token>/getUpdates)
4. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your_bot_token"
   export TELEGRAM_CHAT_ID="your_chat_id"

Usage:
    python scripts/telegram_notify.py "Message text"
    python scripts/telegram_notify.py --severity info "Info message"
    python scripts/telegram_notify.py --severity warning "Warning message"
    python scripts/telegram_notify.py --severity critical "Critical alert"
"""

import argparse
import os
import sys
from datetime import datetime
import requests


def send_telegram_message(text: str, severity: str = "info") -> bool:
    """
    Send message to Telegram.

    Args:
        text: Message text
        severity: Message severity (info, warning, critical)

    Returns:
        True if sent successfully, False otherwise
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        # Silent fail if not configured
        return False

    # Add emoji prefix based on severity
    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
        "success": "✅",
        "trade": "💰",
        "tune": "⚙️"
    }
    emoji = emoji_map.get(severity, "📊")

    # Format message with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{emoji} **Alpha Sniper**\n\n{text}\n\n_{timestamp}_"

    # Send via Telegram API
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": formatted_message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        # Silent fail
        return False


def main():
    parser = argparse.ArgumentParser(description="Send Telegram notification")
    parser.add_argument("message", help="Message text to send")
    parser.add_argument(
        "--severity",
        choices=["info", "warning", "critical", "success", "trade", "tune"],
        default="info",
        help="Message severity level"
    )

    args = parser.parse_args()

    success = send_telegram_message(args.message, args.severity)

    if not success:
        # Exit silently - don't break automation if Telegram fails
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
