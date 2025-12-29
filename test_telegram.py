#!/usr/bin/env python3
"""
Test Telegram notification for async bot.
Run this to verify Telegram is configured correctly.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent / "alpha-sniper"))

# Load .env.async file manually before importing settings
env_file = Path(__file__).parent / "alpha-sniper" / ".env.async"
if env_file.exists():
    print(f"Loading environment from {env_file}...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
else:
    print(f"⚠️  Warning: {env_file} not found, using default .env")

from config.settings import get_settings
from notify.telegram_async import AsyncTelegram


async def test_telegram():
    """Test Telegram notification."""
    print("=" * 70)
    print("🔔 Telegram Notification Test")
    print("=" * 70)
    print()

    # Load settings
    print("Loading settings...")
    settings = get_settings()

    print(f"TELEGRAM_TOKEN: {'✅ Present' if settings.TELEGRAM_TOKEN else '❌ Missing'}")
    print(f"TELEGRAM_CHAT_ID: {settings.TELEGRAM_CHAT_ID if settings.TELEGRAM_CHAT_ID else '❌ Missing'}")
    print(f"TELEGRAM_ENABLED: {settings.TELEGRAM_ENABLED}")
    print()

    if not settings.TELEGRAM_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print("❌ Telegram not configured in .env.async")
        print()
        print("Required settings:")
        print("  ALPHA_TELEGRAM_TOKEN=your_bot_token")
        print("  ALPHA_TELEGRAM_CHAT_ID=your_chat_id")
        return

    # Initialize Telegram
    print("Initializing Telegram...")
    telegram = AsyncTelegram(
        token=settings.TELEGRAM_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID,
    )

    # Start sender task
    print("Starting Telegram sender task...")
    await telegram.start()
    print()

    # Send test message
    print("Sending test message...")
    await telegram.send(
        "🧪 **Telegram Test**\n\n"
        "✅ Alpha Sniper async bot can send notifications!\n\n"
        "This is a test message from `test_telegram.py`",
        parse_mode="Markdown"
    )

    print("✅ Test message queued!")
    print()
    print("Waiting 3 seconds for message to send...")
    await asyncio.sleep(3)

    # Close
    print("Closing Telegram...")
    await telegram.close()

    print()
    print("=" * 70)
    print("✅ Test complete!")
    print("=" * 70)
    print()
    print("Check your Telegram app for the test message.")
    print("If you didn't receive it, check:")
    print("  1. Bot token is correct (from @BotFather)")
    print("  2. Chat ID is correct (your Telegram user ID)")
    print("  3. You've sent /start to the bot first")


if __name__ == "__main__":
    asyncio.run(test_telegram())
