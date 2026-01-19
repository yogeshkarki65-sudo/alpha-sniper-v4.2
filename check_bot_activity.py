#!/usr/bin/env python3
"""
Check Alpha Sniper bot activity over the past 24 hours.

Shows:
- Open positions
- Closed trades
- PnL summary
- Equity snapshots
"""

import asyncio
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path


def check_bot_activity(db_path="/var/lib/alpha-sniper-async/alpha_async.db"):
    """Check bot activity from database."""

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    print("=" * 80)
    print("ALPHA SNIPER BOT ACTIVITY - LAST 24 HOURS")
    print("=" * 80)
    print()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Time boundaries
    now = int(time.time())
    day_ago = now - (24 * 3600)

    # 1. Open Positions
    print("-" * 80)
    print("OPEN POSITIONS")
    print("-" * 80)

    try:
        cursor.execute("SELECT * FROM positions")
        positions = cursor.fetchall()

        if positions:
            cols = [desc[0] for desc in cursor.description]
            for pos in positions:
                pos_dict = dict(zip(cols, pos))
                symbol = pos_dict.get('symbol')
                side = pos_dict.get('side')
                entry = pos_dict.get('entry_price')
                stop = pos_dict.get('stop_loss')
                size = pos_dict.get('size_usd')
                opened = pos_dict.get('timestamp_open', now)
                age_hours = (now - opened) / 3600

                print(f"{symbol} | {side.upper()} | Entry: ${entry:.6f} | Stop: ${stop:.6f} | Size: ${size:.2f} | Age: {age_hours:.1f}h")
        else:
            print("No open positions")
    except Exception as e:
        print(f"Error reading positions: {e}")

    print()

    # 2. Closed Trades (Last 24h)
    print("-" * 80)
    print("CLOSED TRADES (LAST 24H)")
    print("-" * 80)

    try:
        cursor.execute(
            "SELECT * FROM trades WHERE closed_at >= ? ORDER BY closed_at DESC",
            (day_ago,)
        )
        trades = cursor.fetchall()

        if trades:
            cols = [desc[0] for desc in cursor.description]
            total_pnl = 0.0
            winners = 0
            losers = 0

            for trade in trades:
                trade_dict = dict(zip(cols, trade))
                symbol = trade_dict.get('symbol')
                side = trade_dict.get('side')
                entry = trade_dict.get('entry_price')
                exit_price = trade_dict.get('exit_price')
                pnl = trade_dict.get('pnl_usd', 0)
                pnl_pct = trade_dict.get('pnl_pct', 0)
                r_mult = trade_dict.get('r_multiple', 0)
                reason = trade_dict.get('reason')
                closed = trade_dict.get('closed_at')

                total_pnl += pnl
                if pnl > 0:
                    winners += 1
                    emoji = "✅"
                else:
                    losers += 1
                    emoji = "❌"

                closed_dt = datetime.fromtimestamp(closed).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{emoji} {symbol} | {side.upper()} | ${entry:.6f}→${exit_price:.6f} | PnL: ${pnl:.2f} ({pnl_pct:.2f}%) | {r_mult:.2f}R | {reason} | {closed_dt}")

            print()
            print(f"Total Trades: {len(trades)} | Winners: {winners} | Losers: {losers}")
            if len(trades) > 0:
                win_rate = (winners / len(trades)) * 100
                print(f"Win Rate: {win_rate:.1f}%")
            print(f"Total PnL: ${total_pnl:.2f}")
        else:
            print("No trades in last 24 hours")
    except Exception as e:
        print(f"Error reading trades: {e}")

    print()

    # 3. All-Time Stats
    print("-" * 80)
    print("ALL-TIME STATS")
    print("-" * 80)

    try:
        cursor.execute("SELECT COUNT(*), SUM(pnl_usd) FROM trades")
        total_trades, total_pnl = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl_usd > 0")
        all_winners = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl_usd <= 0")
        all_losers = cursor.fetchone()[0]

        print(f"Total Trades: {total_trades or 0}")
        print(f"Total Winners: {all_winners or 0}")
        print(f"Total Losers: {all_losers or 0}")
        if total_trades and total_trades > 0:
            all_win_rate = (all_winners / total_trades) * 100
            print(f"All-Time Win Rate: {all_win_rate:.1f}%")
        print(f"All-Time PnL: ${total_pnl or 0:.2f}")
    except Exception as e:
        print(f"Error reading all-time stats: {e}")

    print()

    # 4. Recent Equity Snapshots
    print("-" * 80)
    print("EQUITY SNAPSHOTS (LAST 10)")
    print("-" * 80)

    try:
        cursor.execute(
            "SELECT * FROM equity_snapshots ORDER BY timestamp DESC LIMIT 10"
        )
        snapshots = cursor.fetchall()

        if snapshots:
            cols = [desc[0] for desc in cursor.description]
            for snap in snapshots:
                snap_dict = dict(zip(cols, snap))
                timestamp = snap_dict.get('timestamp')
                equity = snap_dict.get('equity', 0)
                open_count = snap_dict.get('open_positions_count', 0)
                daily_pnl = snap_dict.get('daily_pnl', 0)

                snap_dt = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{snap_dt} | Equity: ${equity:.2f} | Open: {open_count} | Daily PnL: ${daily_pnl:.2f}")
        else:
            print("No equity snapshots found")
    except Exception as e:
        print(f"Error reading equity snapshots: {e}")

    print()
    print("=" * 80)

    conn.close()


if __name__ == "__main__":
    check_bot_activity()
