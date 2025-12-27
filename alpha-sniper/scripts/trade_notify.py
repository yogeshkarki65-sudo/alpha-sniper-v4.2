#!/usr/bin/env python3
"""
Trade Notification Formatter

Formats trade events and sends them to Telegram via telegram_notify helper.
"""
import argparse
import os
import sys

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_notify import send_telegram


def format_trade_message(args):
    """Format a trade event message"""

    # Determine emoji based on event
    event_emojis = {
        'opened': '🟢',
        'closed': '🔴',
        'stop': '🛑',
        'tp': '💚',
        'timeout': '⏰'
    }
    emoji = event_emojis.get(args.event.lower(), '🔵')

    # Build message
    context = args.context.upper()
    event_text = args.event.upper().replace('_', ' ')

    message = f"{emoji} [{context}] TRADE {event_text}\n"

    if args.symbol:
        message += f"Symbol: {args.symbol}\n"
    if args.side:
        message += f"Side: {args.side}\n"
    if args.engine:
        message += f"Engine: {args.engine}\n"
    if args.regime:
        message += f"Regime: {args.regime}\n"
    if args.entry:
        message += f"Entry: {args.entry}\n"
    if args.exit:
        message += f"Exit: {args.exit}\n"
    if args.pnl_usd:
        message += f"PnL: ${args.pnl_usd}\n"
    if args.pnl_pct:
        message += f"PnL %: {args.pnl_pct}%\n"
    if args.r_multiple:
        message += f"R-multiple: {args.r_multiple}R\n"
    if args.hold:
        message += f"Hold time: {args.hold}\n"
    if args.reason:
        message += f"Reason: {args.reason}\n"

    return message.strip()

def main():
    parser = argparse.ArgumentParser(description='Send trade notification to Telegram')
    parser.add_argument('--context', required=True, help='Context (LIVE/SIM)')
    parser.add_argument('--event', required=True, help='Event (opened/closed/stop/tp/timeout)')
    parser.add_argument('--symbol', help='Trading symbol')
    parser.add_argument('--side', help='Trade side (long/short)')
    parser.add_argument('--engine', help='Engine name')
    parser.add_argument('--regime', help='Market regime')
    parser.add_argument('--entry', help='Entry price')
    parser.add_argument('--exit', help='Exit price')
    parser.add_argument('--pnl-usd', help='PnL in USD')
    parser.add_argument('--pnl-pct', help='PnL percentage')
    parser.add_argument('--r-multiple', help='R-multiple')
    parser.add_argument('--hold', help='Hold time')
    parser.add_argument('--reason', help='Reason for exit')

    args = parser.parse_args()

    message = format_trade_message(args)
    success = send_telegram(message)

    if success:
        print("Trade notification sent successfully")
    else:
        print("Failed to send trade notification", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
