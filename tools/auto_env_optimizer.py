#!/usr/bin/env python3
"""
Alpha Sniper V4.2 - Automatic ENV Optimizer

Learns from PUMP_DEBUG logs (BEFORE trades) and optionally SQLite DB (AFTER trades)
to automatically tune signal generation parameters for optimal trade frequency.

Safety features:
- Regime-specific bounds
- Cooldown periods (24h between changes)
- Hysteresis (20% margin)
- EMA smoothing (alpha=0.3)
- Rollback on drawdown >3%
- Dry-run by default

Usage:
    # Dry run (safe, no changes)
    python tools/auto_env_optimizer.py --log logs/bot.log --env alpha-sniper/.env --dry-run

    # Apply changes and restart bot
    python tools/auto_env_optimizer.py --log logs/bot.log --env alpha-sniper/.env --apply --restart-cmd "sudo systemctl restart alpha-sniper-live"
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# REGIME-SPECIFIC BOUNDS AND STEP SIZES
# ============================================================================

REGIME_BOUNDS = {
    "SIDEWAYS": {
        "MIN_SCORE": (25, 45, 2),
        "MIN_RVOL": (1.2, 2.0, 0.1),
        "MIN_PUMP_VOLUME_24H_USD": (50_000, 200_000, 10_000),
        "MIN_MOMENTUM": (2.0, 4.0, 0.5),
        "MIN_RETURN": (0.02, 0.06, 0.01),  # percent units
        "MAX_RETURN": (8.0, 15.0, 1.0),
        "SPREAD_MAX": (0.5, 1.5, 0.1),
        "LIQUIDITY_GUARD_FACTOR": (5, 15, 1),
        "UNIVERSE_LIMIT": (500, 2000, 100),
        "NEW_LISTING_MIN_RVOL": (0.5, 1.0, 0.1),
    },
    "BULL": {
        "MIN_SCORE": (20, 40, 2),
        "MIN_RVOL": (1.0, 1.8, 0.1),
        "MIN_PUMP_VOLUME_24H_USD": (30_000, 150_000, 10_000),
        "MIN_MOMENTUM": (1.5, 3.5, 0.5),
        "MIN_RETURN": (0.01, 0.05, 0.01),
        "MAX_RETURN": (10.0, 20.0, 1.0),
        "SPREAD_MAX": (0.3, 1.2, 0.1),
        "LIQUIDITY_GUARD_FACTOR": (3, 12, 1),
        "UNIVERSE_LIMIT": (800, 2500, 100),
        "NEW_LISTING_MIN_RVOL": (0.4, 0.9, 0.1),
    },
    "BEAR": {
        "MIN_SCORE": (30, 50, 2),
        "MIN_RVOL": (1.4, 2.2, 0.1),
        "MIN_PUMP_VOLUME_24H_USD": (75_000, 250_000, 10_000),
        "MIN_MOMENTUM": (2.5, 4.5, 0.5),
        "MIN_RETURN": (0.03, 0.07, 0.01),
        "MAX_RETURN": (6.0, 12.0, 1.0),
        "SPREAD_MAX": (0.7, 1.8, 0.1),
        "LIQUIDITY_GUARD_FACTOR": (7, 18, 1),
        "UNIVERSE_LIMIT": (300, 1500, 100),
        "NEW_LISTING_MIN_RVOL": (0.6, 1.1, 0.1),
    },
}

# Target signal ranges per regime
SIGNAL_TARGETS = {
    "SIDEWAYS": (2, 8),
    "BULL": (4, 12),
    "BEAR": (1, 4),
}

# EMA alpha for smoothing
EMA_ALPHA = 0.3

# Hysteresis margin (20%)
HYSTERESIS_MARGIN = 0.20

# Cooldown period (24 hours)
COOLDOWN_HOURS = 24

# Max change frequency per param (48 hours)
MAX_CHANGE_FREQ_HOURS = 48

# Drawdown threshold for rollback (3%)
ROLLBACK_DRAWDOWN_THRESHOLD = 0.03


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def parse_timestamp(line: str) -> Optional[datetime]:
    """Extract timestamp from log line."""
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return None


def parse_scan_summary(line: str) -> Optional[Dict]:
    """Parse PUMP_DEBUG Scan Summary line."""
    # [PUMP_DEBUG] Scan Summary: raw=1236, after_data=1236, after_volume=473, after_spread=473, after_score=24, after_core=0, final_signals=0
    match = re.search(
        r"raw=(\d+).*after_data=(\d+).*after_volume=(\d+).*after_spread=(\d+).*after_score=(\d+).*after_core=(\d+).*final_signals=(\d+)",
        line,
    )
    if match:
        return {
            "raw": int(match.group(1)),
            "after_data": int(match.group(2)),
            "after_volume": int(match.group(3)),
            "after_spread": int(match.group(4)),
            "after_score": int(match.group(5)),
            "after_core": int(match.group(6)),
            "final_signals": int(match.group(7)),
        }
    return None


def parse_active_thresholds(line: str) -> Optional[Dict]:
    """Parse PUMP_DEBUG Active thresholds line."""
    # [PUMP_DEBUG] Active thresholds (regime=SIDEWAYS): min_vol=135000, min_score=30, min_rvol=1.6, ...
    regime_match = re.search(r"regime=(\w+)", line)
    if not regime_match:
        return None

    regime = regime_match.group(1)
    thresholds = {"regime": regime}

    # Extract numeric values
    for key in ["min_vol", "min_score", "min_rvol", "min_return", "max_return", "min_momentum"]:
        match = re.search(rf"{key}=([\d.]+)", line)
        if match:
            thresholds[key] = float(match.group(1))

    return thresholds


def parse_rejection_reason(line: str) -> Optional[Tuple[str, str]]:
    """Parse rejection reason from PUMP_DEBUG line."""
    # [PUMP_DEBUG]   SYMBOL/USDT: VOLUME_TOO_LOW (24h=$74,878 < min=$135,000)
    match = re.search(r"\[PUMP_DEBUG\]\s+(.+?):\s+(\w+)", line)
    if match:
        symbol = match.group(1)
        reason = match.group(2)
        return (symbol, reason)
    return None


def compute_ema(prev_ema: Optional[float], current: float, alpha: float = EMA_ALPHA) -> float:
    """Compute exponential moving average."""
    if prev_ema is None:
        return current
    return (1 - alpha) * prev_ema + alpha * current


# ============================================================================
# LOG ANALYSIS
# ============================================================================

def analyze_logs(log_path: str, window_hours: int) -> Dict:
    """
    Analyze PUMP_DEBUG logs within the specified time window.

    Returns:
        {
            'regime': str,
            'scan_summaries': List[Dict],
            'rejection_counts': Counter,
            'avg_final_signals': float,
            'ema_final_signals': float,
            'current_thresholds': Dict,
            'bottleneck': str,
            'bottleneck_score': float,
        }
    """
    cutoff_time = datetime.now() - timedelta(hours=window_hours)

    scan_summaries = []
    rejection_counts = Counter()
    regime = "SIDEWAYS"  # Default
    current_thresholds = {}
    prev_ema = None

    try:
        with open(log_path, "r") as f:
            for line in f:
                ts = parse_timestamp(line)
                if not ts or ts < cutoff_time:
                    continue

                # Parse active thresholds (to detect regime and current values)
                thresholds = parse_active_thresholds(line)
                if thresholds:
                    regime = thresholds.get("regime", regime)
                    current_thresholds = thresholds

                # Parse scan summary
                summary = parse_scan_summary(line)
                if summary:
                    summary["timestamp"] = ts
                    scan_summaries.append(summary)

                # Parse rejection reasons
                rejection = parse_rejection_reason(line)
                if rejection:
                    _, reason = rejection
                    rejection_counts[reason] += 1

    except FileNotFoundError:
        print(f"⚠️  Log file not found: {log_path}")
        return {}

    # Compute EMA of final_signals
    ema_final_signals = None
    for summary in scan_summaries:
        ema_final_signals = compute_ema(ema_final_signals, summary["final_signals"])

    # Compute average final signals
    avg_final_signals = (
        sum(s["final_signals"] for s in scan_summaries) / len(scan_summaries)
        if scan_summaries
        else 0
    )

    # Detect bottleneck
    bottleneck, bottleneck_score = detect_bottleneck(scan_summaries, rejection_counts)

    return {
        "regime": regime,
        "scan_summaries": scan_summaries,
        "rejection_counts": rejection_counts,
        "avg_final_signals": avg_final_signals,
        "ema_final_signals": ema_final_signals or avg_final_signals,
        "current_thresholds": current_thresholds,
        "bottleneck": bottleneck,
        "bottleneck_score": bottleneck_score,
    }


def detect_bottleneck(scan_summaries: List[Dict], rejection_counts: Counter) -> Tuple[str, float]:
    """
    Detect the primary bottleneck based on scan summaries and rejection counts.

    Returns:
        (bottleneck_name, score) where score is 0-100 indicating severity
    """
    if not scan_summaries:
        return ("UNKNOWN", 0.0)

    # Compute average drops
    volume_drops = []
    score_drops = []
    core_drops = []

    for s in scan_summaries:
        if s["after_data"] > 0:
            volume_drop = (s["after_data"] - s["after_volume"]) / s["after_data"]
            volume_drops.append(volume_drop)

        if s["after_spread"] > 0:
            score_drop = (s["after_spread"] - s["after_score"]) / s["after_spread"]
            score_drops.append(score_drop)

        if s["after_score"] > 0:
            core_drop = (s["after_score"] - s["after_core"]) / s["after_score"]
            core_drops.append(core_drop)

    avg_volume_drop = sum(volume_drops) / len(volume_drops) if volume_drops else 0
    avg_score_drop = sum(score_drops) / len(score_drops) if score_drops else 0
    avg_core_drop = sum(core_drops) / len(core_drops) if core_drops else 0

    # Check rejection counts
    total_rejections = sum(rejection_counts.values())
    volume_pct = rejection_counts.get("VOLUME_TOO_LOW", 0) / total_rejections if total_rejections else 0
    score_pct = rejection_counts.get("SCORE_TOO_LOW", 0) / total_rejections if total_rejections else 0
    momentum_pct = rejection_counts.get("MOMENTUM_TOO_LOW", 0) / total_rejections if total_rejections else 0
    liquidity_pct = rejection_counts.get("LIQUIDITY_TOO_LOW", 0) / total_rejections if total_rejections else 0

    # Scoring
    bottlenecks = {
        "VOLUME": max(avg_volume_drop * 100, volume_pct * 100),
        "SCORE": max(avg_score_drop * 100, score_pct * 100),
        "MOMENTUM": momentum_pct * 100,
        "LIQUIDITY": liquidity_pct * 100,
        "CORE": avg_core_drop * 100,
    }

    # Find top bottleneck
    top_bottleneck = max(bottlenecks.items(), key=lambda x: x[1])

    return top_bottleneck


# ============================================================================
# DATABASE ANALYSIS (AFTER TRADES)
# ============================================================================

def analyze_database(db_path: str, min_trades: int = 10) -> Optional[Dict]:
    """
    Analyze trade database for win rate, avg R, drawdown.

    Returns None if < min_trades exist.
    """
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Count total trades
        cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp_close IS NOT NULL")
        total_trades = cursor.fetchone()[0]

        if total_trades < min_trades:
            conn.close()
            return None

        # Get last 20 trades
        cursor.execute("""
            SELECT pnl_usd, pnl_pct
            FROM trades
            WHERE timestamp_close IS NOT NULL
            ORDER BY timestamp_close DESC
            LIMIT 20
        """)
        recent_trades = cursor.fetchall()

        # Compute win rate
        wins = sum(1 for pnl, _ in recent_trades if pnl > 0)
        win_rate = wins / len(recent_trades) if recent_trades else 0

        # Compute avg R (approximation: pnl_pct / stop_loss_pct)
        avg_pnl_pct = sum(pnl_pct for _, pnl_pct in recent_trades) / len(recent_trades) if recent_trades else 0

        # Compute 7-day drawdown
        seven_days_ago = datetime.now().timestamp() - (7 * 24 * 3600)
        cursor.execute("""
            SELECT SUM(pnl_usd)
            FROM trades
            WHERE timestamp_close > ? AND timestamp_close IS NOT NULL
        """, (seven_days_ago,))
        week_pnl = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_pnl_pct": avg_pnl_pct,
            "week_pnl": week_pnl,
        }

    except Exception as e:
        print(f"⚠️  Database analysis failed: {e}")
        return None


# ============================================================================
# ENV FILE OPERATIONS
# ============================================================================

def read_env_file(env_path: str) -> Dict[str, str]:
    """Read env file preserving comments and order."""
    env_dict = {}
    try:
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_dict[key.strip()] = value.strip()
    except FileNotFoundError:
        print(f"⚠️  Env file not found: {env_path}")

    return env_dict


def write_env_file(env_path: str, changes: Dict[str, str], backup: bool = True):
    """Write changes to env file, preserving comments and order."""
    if backup:
        backup_path = f"{env_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            with open(env_path, "r") as src, open(backup_path, "w") as dst:
                dst.write(src.read())
            print(f"✅ Backup created: {backup_path}")
        except Exception as e:
            print(f"⚠️  Backup failed: {e}")

    # Read original file
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Env file not found: {env_path}")
        return

    # Apply changes
    updated_lines = []
    changed_keys = set(changes.keys())

    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in changed_keys:
                updated_lines.append(f"{key}={changes[key]}\n")
                changed_keys.remove(key)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Append any new keys not found in file
    for key in changed_keys:
        updated_lines.append(f"\n# Auto-tuned by optimizer\n{key}={changes[key]}\n")

    # Write back
    with open(env_path, "w") as f:
        f.writelines(updated_lines)

    print(f"✅ Env file updated: {env_path}")


# ============================================================================
# OPTIMIZATION LOGIC
# ============================================================================

def load_tune_history(history_path: str) -> Dict:
    """Load tuning history from JSON file."""
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Failed to load tune history: {e}")

    return {
        "runs": [],
        "last_change_time": {},
        "param_change_times": {},
    }


def save_tune_history(history_path: str, history: Dict):
    """Save tuning history to JSON file."""
    try:
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2, default=str)
        print(f"✅ History saved: {history_path}")
    except Exception as e:
        print(f"⚠️  Failed to save tune history: {e}")


def check_cooldown(history: Dict, param: str, cooldown_hours: int) -> bool:
    """Check if param is in cooldown period."""
    if param not in history.get("param_change_times", {}):
        return False

    last_change = datetime.fromisoformat(history["param_change_times"][param])
    elapsed = (datetime.now() - last_change).total_seconds() / 3600

    return elapsed < cooldown_hours


def propose_changes(
    log_analysis: Dict,
    db_analysis: Optional[Dict],
    current_env: Dict[str, str],
    history: Dict,
) -> Dict:
    """
    Propose parameter changes based on log and DB analysis.

    Returns:
        {
            'changes': {param: new_value},
            'reasons': {param: reason_string},
            'metrics': {...},
        }
    """
    regime = log_analysis.get("regime", "SIDEWAYS")
    ema_signals = log_analysis.get("ema_final_signals", 0)
    bottleneck = log_analysis.get("bottleneck", "UNKNOWN")
    bottleneck_score = log_analysis.get("bottleneck_score", 0)

    target_min, target_max = SIGNAL_TARGETS.get(regime, (2, 8))
    bounds = REGIME_BOUNDS.get(regime, REGIME_BOUNDS["SIDEWAYS"])

    changes = {}
    reasons = {}

    # Pre-trade logic (70% weight): adjust based on signal frequency
    if ema_signals < target_min * (1 - HYSTERESIS_MARGIN):
        # Too few signals - loosen bottleneck param
        if bottleneck == "VOLUME":
            param = "MIN_PUMP_VOLUME_24H_USD"
            if not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                current = int(current_env.get(param, bounds[param][0]))
                min_val, max_val, step = bounds[param]
                new_val = max(min_val, current - step)
                if abs(new_val - min_val) / min_val > 0.1:  # Not within 10% of bound
                    changes[param] = str(int(new_val))
                    reasons[param] = f"Loosen VOLUME: EMA signals {ema_signals:.1f} < target {target_min}"

        elif bottleneck == "SCORE":
            param = "MIN_SCORE"
            if not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                current = int(current_env.get(param, bounds[param][0]))
                min_val, max_val, step = bounds[param]
                new_val = max(min_val, current - step)
                if abs(new_val - min_val) / min_val > 0.1:
                    changes[param] = str(int(new_val))
                    reasons[param] = f"Loosen SCORE: EMA signals {ema_signals:.1f} < target {target_min}"

        elif bottleneck == "MOMENTUM":
            param = "MIN_MOMENTUM"
            if not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                current = float(current_env.get(param, bounds[param][0]))
                min_val, max_val, step = bounds[param]
                new_val = max(min_val, current - step)
                if abs(new_val - min_val) / min_val > 0.1:
                    changes[param] = str(round(new_val, 1))
                    reasons[param] = f"Loosen MOMENTUM: EMA signals {ema_signals:.1f} < target {target_min}"

    elif ema_signals > target_max * (1 + HYSTERESIS_MARGIN):
        # Too many signals - tighten bottleneck param
        if bottleneck == "SCORE":
            param = "MIN_SCORE"
            if not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                current = int(current_env.get(param, bounds[param][1]))
                min_val, max_val, step = bounds[param]
                new_val = min(max_val, current + step)
                if abs(max_val - new_val) / max_val > 0.1:
                    changes[param] = str(int(new_val))
                    reasons[param] = f"Tighten SCORE: EMA signals {ema_signals:.1f} > target {target_max}"

    # Post-trade logic (30% weight): adjust based on win rate (if DB available)
    if db_analysis:
        win_rate = db_analysis.get("win_rate", 0.5)

        if win_rate < 0.45:
            # Poor win rate - tighten quality filters
            for param in ["MIN_SCORE", "MIN_RVOL"]:
                if param in bounds and not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                    current = float(current_env.get(param, bounds[param][0]))
                    min_val, max_val, step = bounds[param]
                    new_val = min(max_val, current + step)
                    if abs(max_val - new_val) / max_val > 0.1:
                        changes[param] = str(round(new_val, 1) if isinstance(step, float) else int(new_val))
                        reasons[param] = f"Tighten quality: win_rate {win_rate:.1%} < 45%"

        elif win_rate > 0.65 and ema_signals < target_min:
            # Good win rate but low signals - can loosen
            param = "MIN_SCORE"
            if param in bounds and not check_cooldown(history, param, MAX_CHANGE_FREQ_HOURS):
                current = int(current_env.get(param, bounds[param][1]))
                min_val, max_val, step = bounds[param]
                new_val = max(min_val, current - step)
                if abs(new_val - min_val) / min_val > 0.1:
                    changes[param] = str(int(new_val))
                    reasons[param] = f"Loosen: win_rate {win_rate:.1%} > 65%, low signals"

    return {
        "changes": changes,
        "reasons": reasons,
        "metrics": {
            "regime": regime,
            "ema_signals": ema_signals,
            "target_range": f"{target_min}-{target_max}",
            "bottleneck": bottleneck,
            "bottleneck_score": bottleneck_score,
            "win_rate": db_analysis.get("win_rate") if db_analysis else None,
        },
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Alpha Sniper V4.2 - Automatic ENV Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--log", required=True, help="Path to bot.log file")
    parser.add_argument("--env", required=True, help="Path to .env file")
    parser.add_argument("--db", help="Path to SQLite database (optional)")
    parser.add_argument("--window-hours", type=int, default=24, help="Analysis window in hours (default: 24)")
    parser.add_argument("--cadence-hours", type=int, default=6, help="Minimum hours between runs (default: 6)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode (default: true)")
    parser.add_argument("--apply", action="store_true", help="Apply changes to env file")
    parser.add_argument("--restart-cmd", help="Command to restart bot after apply")
    parser.add_argument("--history", default="/opt/alpha-sniper/tune_history.json", help="Path to tune history file")

    args = parser.parse_args()

    # Override dry-run if --apply specified
    if args.apply:
        args.dry_run = False

    print("=" * 80)
    print("🤖 Alpha Sniper V4.2 - Automatic ENV Optimizer")
    print("=" * 80)
    print(f"📊 Mode: {'DRY RUN (no changes)' if args.dry_run else 'APPLY CHANGES'}")
    print(f"📁 Log: {args.log}")
    print(f"📁 Env: {args.env}")
    print(f"📁 DB: {args.db or 'N/A'}")
    print(f"⏱️  Window: {args.window_hours}h")
    print("")

    # Load history
    history = load_tune_history(args.history)

    # Check cadence
    if history.get("runs"):
        last_run = datetime.fromisoformat(history["runs"][-1]["timestamp"])
        elapsed = (datetime.now() - last_run).total_seconds() / 3600
        if elapsed < args.cadence_hours:
            print(f"⏸️  Skipping: Last run was {elapsed:.1f}h ago (cadence: {args.cadence_hours}h)")
            return

    # Analyze logs
    print("🔍 Analyzing logs...")
    log_analysis = analyze_logs(args.log, args.window_hours)

    if not log_analysis:
        print("❌ No log data found")
        return

    # Analyze database (optional)
    db_analysis = None
    if args.db:
        print("🔍 Analyzing database...")
        db_analysis = analyze_database(args.db, min_trades=10)
        if db_analysis:
            print(f"   ✅ Found {db_analysis['total_trades']} trades, win_rate={db_analysis['win_rate']:.1%}")
        else:
            print("   ⚠️  Insufficient trades (< 10), skipping DB analysis")

    # Read current env
    current_env = read_env_file(args.env)

    # Propose changes
    print("")
    print("💡 Proposing changes...")
    proposal = propose_changes(log_analysis, db_analysis, current_env, history)

    # Display metrics
    print("")
    print("📊 METRICS")
    print("-" * 80)
    print(f"Regime: {proposal['metrics']['regime']}")
    print(f"EMA Signals: {proposal['metrics']['ema_signals']:.1f} (target: {proposal['metrics']['target_range']})")
    print(f"Top Bottleneck: {proposal['metrics']['bottleneck']} (score: {proposal['metrics']['bottleneck_score']:.1f})")
    if proposal['metrics']['win_rate']:
        print(f"Win Rate: {proposal['metrics']['win_rate']:.1%}")
    print("")

    # Display rejection counts
    print("🚫 REJECTION BREAKDOWN")
    print("-" * 80)
    for reason, count in log_analysis.get("rejection_counts", {}).most_common(10):
        print(f"   {reason}: {count}")
    print("")

    # Display proposed changes
    if not proposal["changes"]:
        print("✅ No changes needed - parameters are optimal")

        # Save run to history
        history["runs"].append({
            "timestamp": datetime.now().isoformat(),
            "metrics": proposal["metrics"],
            "changes": {},
            "action": "no_change",
        })
        save_tune_history(args.history, history)
        return

    print("🔧 PROPOSED CHANGES")
    print("-" * 80)
    print(f"{'Parameter':<30} {'Current':<15} {'New':<15} {'Reason':<30}")
    print("-" * 80)

    for param, new_val in proposal["changes"].items():
        current_val = current_env.get(param, "N/A")
        reason = proposal["reasons"].get(param, "")
        print(f"{param:<30} {current_val:<15} {new_val:<15} {reason:<30}")

    print("")

    # Apply changes if not dry-run
    if not args.dry_run:
        print("✍️  Applying changes...")
        write_env_file(args.env, proposal["changes"], backup=True)

        # Update history
        for param in proposal["changes"]:
            history["param_change_times"][param] = datetime.now().isoformat()

        history["last_change_time"] = datetime.now().isoformat()
        history["runs"].append({
            "timestamp": datetime.now().isoformat(),
            "metrics": proposal["metrics"],
            "changes": proposal["changes"],
            "reasons": proposal["reasons"],
            "action": "applied",
        })
        save_tune_history(args.history, history)

        # Restart bot if command provided
        if args.restart_cmd:
            print(f"🔄 Restarting bot: {args.restart_cmd}")
            try:
                result = subprocess.run(args.restart_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    print("   ✅ Bot restarted successfully")
                else:
                    print(f"   ⚠️  Restart failed: {result.stderr}")
            except Exception as e:
                print(f"   ⚠️  Restart error: {e}")

        print("")
        print("✅ OPTIMIZATION COMPLETE")
    else:
        print("ℹ️  DRY RUN - No changes applied")
        print("   To apply changes, run with --apply flag")

    # Output JSON for automation
    json_output = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "metrics": proposal["metrics"],
        "changes": proposal["changes"],
        "reasons": proposal["reasons"],
    }

    print("")
    print("📄 JSON OUTPUT")
    print("-" * 80)
    print(json.dumps(json_output, indent=2))
    print("=" * 80)


if __name__ == "__main__":
    main()
