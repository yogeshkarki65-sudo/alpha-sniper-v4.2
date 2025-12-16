#!/usr/bin/env python3
"""
Crash Notification Script

Sends alert when alpha-sniper-live.service fails.
"""
import sys
import os
import socket

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notify import send_telegram

def main():
    hostname = socket.gethostname()

    message = (
        f"❌ Alpha Sniper LIVE crashed or failed to start\n"
        f"Host: {hostname}\n"
        f"Service: alpha-sniper-live.service\n"
        f"Check logs: journalctl -u alpha-sniper-live.service -n 50"
    )

    success = send_telegram(message)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
