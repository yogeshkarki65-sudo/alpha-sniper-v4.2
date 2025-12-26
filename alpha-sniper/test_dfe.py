#!/usr/bin/env python3
"""
Test script for Dynamic Filter Engine (DFE)

Usage:
    python test_dfe.py
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from utils.dynamic_filters import DynamicFilterEngine
from utils.logger import setup_logger


def test_dfe():
    """Test DFE logic without modifying .env"""
    print("=" * 70)
    print("Testing Dynamic Filter Engine (DFE)")
    print("=" * 70)

    cfg = Config()
    logger = setup_logger()

    # Test 1: Check if trade log exists
    print("\n1. Checking for trade log...")
    dfe = DynamicFilterEngine(cfg, logger)
    trades = dfe._load_trade_data()

    if trades is None:
        print("   ⚠️  No trade log found (logs/v4_trade_scores.csv)")
        print("   This is normal if you haven't run any trades yet.")
        print("   DFE will skip adjustment until enough trades accumulate.")
    else:
        print(f"   ✅ Found {len(trades)} closed trades")

        if len(trades) >= 10:
            # Test 2: Calculate metrics
            print("\n2. Calculating performance metrics...")
            metrics = dfe._calculate_metrics(trades, datetime.utcnow())
            print(f"   Trades/day (14d): {metrics['trades_per_day_14d']:.2f}")
            print(f"   Win rate (last 30): {metrics['win_rate_30']*100:.1f}%")
            print(f"   Avg R (last 30): {metrics['avg_R_30']:.3f}R")

            # Test 3: Load current filters
            print("\n3. Current filter values:")
            current = dfe._load_current_filters()
            for key, val in current.items():
                print(f"   {key} = {val}")

            # Test 4: Calculate new filters (without saving)
            print("\n4. Proposed new filter values:")
            new = dfe._calculate_new_filters(current, metrics)
            for key, val in new.items():
                delta = val - current[key]
                direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
                print(f"   {key} = {val} {direction} ({delta:+.1f})")

            print("\n✅ DFE logic test complete!")
            print("Note: No .env file was modified. This was just a dry run.")
        else:
            print(f"\n   ⚠️  Only {len(trades)} trades found (need at least 10)")
            print("   DFE will activate after more trades accumulate.")

    print("\n" + "=" * 70)
    print("To enable DFE in production, add to .env:")
    print("  DFE_ENABLED=true")
    print("=" * 70)


if __name__ == "__main__":
    test_dfe()
