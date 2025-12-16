#!/usr/bin/env python3
"""
Telegram Chat ID Helper

This script helps you find your Telegram chat ID to configure
Alpha Sniper's Telegram notifications.

Usage:
1. Start your bot on Telegram by sending /start to @thisisversionfourbot
2. Run this script with your bot token
3. It will show your chat ID
4. Update TELEGRAM_CHAT_ID in /etc/alpha-sniper/alpha-sniper-live.env
"""

import requests
import sys

def get_chat_id(bot_token):
    """Get chat ID from Telegram bot updates"""

    print("=" * 60)
    print("Telegram Chat ID Helper")
    print("=" * 60)
    print()

    # Step 1: Verify bot token
    print("[1/3] Verifying bot token...")
    url = f"https://api.telegram.org/bot{bot_token}/getMe"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"❌ ERROR: Invalid bot token")
            print(f"   HTTP {resp.status_code}: {resp.text}")
            return None

        bot_info = resp.json()
        if not bot_info.get('ok'):
            print(f"❌ ERROR: {bot_info.get('description', 'Unknown error')}")
            return None

        bot_name = bot_info['result']['username']
        print(f"✅ Bot verified: @{bot_name}")
        print()

    except Exception as e:
        print(f"❌ ERROR: Failed to connect to Telegram API: {e}")
        return None

    # Step 2: Get updates
    print("[2/3] Fetching recent messages...")
    print(f"   💡 Make sure you've sent /start to @{bot_name} on Telegram!")
    print()

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"❌ ERROR: Failed to get updates")
            print(f"   HTTP {resp.status_code}: {resp.text}")
            return None

        data = resp.json()
        if not data.get('ok'):
            print(f"❌ ERROR: {data.get('description', 'Unknown error')}")
            return None

        updates = data.get('result', [])

        if not updates:
            print("❌ No messages found!")
            print()
            print("To fix this:")
            print(f"1. Open Telegram and search for @{bot_name}")
            print("2. Send /start to the bot")
            print("3. Run this script again")
            print()
            return None

        # Step 3: Extract chat IDs
        print("[3/3] Found messages! Here are your chat IDs:")
        print()

        chat_ids = set()
        for update in updates:
            if 'message' in update:
                chat = update['message']['chat']
                chat_id = chat['id']
                chat_type = chat['type']
                chat_title = chat.get('title', chat.get('first_name', 'Unknown'))

                chat_ids.add((chat_id, chat_type, chat_title))

        if not chat_ids:
            print("❌ No chat IDs found in updates")
            return None

        print("Found the following chats:")
        print()

        for chat_id, chat_type, chat_title in sorted(chat_ids):
            print(f"  Chat ID: {chat_id}")
            print(f"  Type:    {chat_type}")
            print(f"  Name:    {chat_title}")
            print()

        # Return the most recent chat_id
        most_recent = updates[-1]['message']['chat']['id']

        print("=" * 60)
        print("✅ RECOMMENDED CHAT ID TO USE:")
        print(f"   {most_recent}")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Update your env file:")
        print(f"   sudo nano /etc/alpha-sniper/alpha-sniper-live.env")
        print(f"   Change: TELEGRAM_CHAT_ID={most_recent}")
        print()
        print("2. Restart the bot:")
        print("   sudo systemctl restart alpha-sniper-live.service")
        print()
        print("3. You should receive a test message on Telegram!")
        print()

        return most_recent

    except Exception as e:
        print(f"❌ ERROR: Failed to process updates: {e}")
        return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 get_telegram_chat_id.py <BOT_TOKEN>")
        print()
        print("Example:")
        print("  python3 get_telegram_chat_id.py 8580299772:AAH33xHkEhpl9SnEbiXtRq21ItlzazlicvU")
        print()
        sys.exit(1)

    bot_token = sys.argv[1]
    get_chat_id(bot_token)
