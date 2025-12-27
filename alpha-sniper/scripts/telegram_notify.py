#!/usr/bin/env python3
"""
Telegram Notification Helper

Simple helper to send messages to Telegram.
Can read credentials from env vars or /etc/alpha-sniper/alpha-sniper-live.env
"""
import os
import re
import sys

import requests


def load_env_file(filepath="/etc/alpha-sniper/alpha-sniper-live.env"):
    """Load environment variables from a file"""
    env_vars = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Remove inline comments
                line = re.sub(r'\s*#.*$', '', line)
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return env_vars

def get_telegram_credentials():
    """Get Telegram bot token and chat ID"""
    # Try environment variables first
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')

    # If not in env, try loading from file
    if not bot_token or not chat_id:
        env_vars = load_env_file()
        bot_token = bot_token or env_vars.get('TELEGRAM_BOT_TOKEN')
        chat_id = chat_id or env_vars.get('TELEGRAM_CHAT_ID')

    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    return bot_token, chat_id

def send_telegram(message, parse_mode="Markdown"):
    """
    Send a message to Telegram

    Args:
        message: Message text to send
        parse_mode: Parse mode (Markdown or HTML)
    """
    try:
        bot_token, chat_id = get_telegram_credentials()

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    # CLI usage
    if len(sys.argv) < 2:
        print("Usage: telegram_notify.py <message>")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    success = send_telegram(message)
    sys.exit(0 if success else 1)
