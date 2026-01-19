#!/bin/bash
# auto_tune_service.sh - Automatic parameter tuning based on performance data
# This script runs periodically and auto-adjusts entry thresholds based on results
# Usage: Run via cron every 4-6 hours

set -e

LOG_FILE="/opt/alpha-sniper/logs/auto_tune.log"
LOOKBACK="${1:-6 hours ago}"
MIN_TRADES=10  # Minimum trades before making adjustments
DB_PATH="/opt/alpha-sniper/data/alpha_async.db"

# Ensure log directory exists
mkdir -p /opt/alpha-sniper/logs

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=========================================="
log "AUTO-TUNE SERVICE STARTED"
log "Lookback: $LOOKBACK"
log "=========================================="

# Check if we have enough data
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Get trade stats
trade_data=$(sqlite3 "$DB_PATH" "
SELECT
  COUNT(*) as trades,
  ROUND(100.0*SUM(pnl_usd>0)/COUNT(*),1) as winrate,
  ROUND(AVG(pnl_usd),4) as avg_pnl
FROM trades
WHERE closed_at > strftime('%s','now','-${LOOKBACK}');
" 2>/dev/null)

trades=$(echo "$trade_data" | cut -d'|' -f1)
winrate=$(echo "$trade_data" | cut -d'|' -f2)
avg_pnl=$(echo "$trade_data" | cut -d'|' -f3)

log "Performance: $trades trades, ${winrate}% win rate, \$${avg_pnl} avg P&L"

# Check if we have enough data
if [ "$trades" -lt "$MIN_TRADES" ]; then
    log "INFO: Only $trades trades (need $MIN_TRADES minimum). Skipping auto-tune."
    exit 0
fi

# Get flow stats
flow_data=$(sudo journalctl -u alpha-sniper-async.service --since "$LOOKBACK" -o cat \
 | grep 'eager_candidates=' \
 | awk -F'eager_candidates=| eager_attempted=| eager_opened=' '{
     c+=$2; a+=$3; o+=$4; n++
   } END {
     cand = (n > 0) ? c/n : 0;
     ar = (c > 0) ? 100*a/c : 0;
     or = (a > 0) ? 100*o/a : 0;
     printf "%.2f|%.1f|%.1f\n", cand, ar, or
   }')

cand_per_cycle=$(echo "$flow_data" | cut -d'|' -f1)
attempt_rate=$(echo "$flow_data" | cut -d'|' -f2)
open_rate=$(echo "$flow_data" | cut -d'|' -f3)

log "Flow: ${cand_per_cycle} cand/cycle, ${attempt_rate}% attempt rate, ${open_rate}% open rate"

# Get current settings
cd /opt/alpha-sniper
source venv/bin/activate

current_ret5m=$(python scripts/overrides_cli.py get --key EARLY_RET_5M_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_vspike=$(python scripts/overrides_cli.py get --key EARLY_VOL_SPIKE_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_risk=$(python scripts/overrides_cli.py get --key RISK_PER_TRADE 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_eps=$(python scripts/overrides_cli.py get --key EAGER_EPS_PCT 2>/dev/null | grep -oP '[\d.]+' | head -1)

# Default values if not set
: ${current_ret5m:=0.018}
: ${current_vspike:=2.0}
: ${current_risk:=0.0020}
: ${current_eps:=0.0010}
: ${winrate:=0}
: ${cand_per_cycle:=0}
: ${attempt_rate:=0}
: ${open_rate:=0}

log "Current: ret5m=${current_ret5m}, vspike=${current_vspike}, risk=${current_risk}, eps=${current_eps}"

# Adjustment flags
made_adjustment=0

# SCENARIO A: Low win rate (<25%) - TIGHTEN
if (( $(echo "$winrate < 25" | bc -l 2>/dev/null || echo 0) )); then
    log "⚠️  DETECTED: Low win rate ($winrate% < 25%)"

    # Tighten momentum threshold by 0.2%
    new_ret5m=$(echo "$current_ret5m + 0.002" | bc)

    # Safety check: don't go above 3.5%
    if (( $(echo "$new_ret5m <= 0.035" | bc -l) )); then
        log "ACTION: Tightening EARLY_RET_5M_MIN: $current_ret5m → $new_ret5m"
        python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value "$new_ret5m"
        made_adjustment=1
    else
        log "SKIP: ret5m already at max (${current_ret5m})"
    fi
fi

# SCENARIO B: Too few trades (<0.2 cand/cycle) but good winrate (>35%) - LOOSEN
if (( $(echo "$cand_per_cycle < 0.2" | bc -l 2>/dev/null || echo 0) )) && (( $(echo "$winrate > 35" | bc -l 2>/dev/null || echo 0) )); then
    log "⚠️  DETECTED: Too few trades ($cand_per_cycle cand/cycle < 0.2) with good winrate ($winrate%)"

    # Loosen volume requirement by 0.2x
    new_vspike=$(echo "$current_vspike - 0.2" | bc)

    # Safety check: don't go below 1.5x
    if (( $(echo "$new_vspike >= 1.5" | bc -l) )); then
        log "ACTION: Loosening EARLY_VOL_SPIKE_MIN: $current_vspike → $new_vspike"
        python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value "$new_vspike"
        made_adjustment=1
    else
        log "SKIP: vspike already at min (${current_vspike})"
    fi
fi

# SCENARIO C: Low open rate (<25%) - INCREASE EPSILON
if (( $(echo "$open_rate < 25" | bc -l 2>/dev/null || echo 0) )) && (( $(echo "$attempt_rate > 10" | bc -l 2>/dev/null || echo 0) )); then
    log "⚠️  DETECTED: Low open rate ($open_rate% < 25%)"

    # Increase trigger epsilon by 0.03%
    new_eps=$(echo "$current_eps + 0.0003" | bc)

    # Safety check: don't go above 0.3%
    if (( $(echo "$new_eps <= 0.003" | bc -l) )); then
        log "ACTION: Increasing EAGER_EPS_PCT: $current_eps → $new_eps"
        python scripts/overrides_cli.py set --key EAGER_EPS_PCT --value "$new_eps"
        made_adjustment=1
    else
        log "SKIP: epsilon already at max (${current_eps})"
    fi
fi

# SCENARIO D: Good win rate (>=30%) and stable - SCALE UP RISK
if (( $(echo "$winrate >= 30" | bc -l 2>/dev/null || echo 0) )) && [ "$trades" -ge 15 ]; then
    log "✅ DETECTED: Good win rate ($winrate% >= 30%) with $trades trades"

    # Increase risk by 0.05%
    new_risk=$(echo "$current_risk + 0.0005" | bc)

    # Safety check: don't go above 0.5%
    if (( $(echo "$new_risk <= 0.005" | bc -l) )); then
        log "ACTION: Scaling up RISK_PER_TRADE: $current_risk → $new_risk"
        python scripts/overrides_cli.py set --key RISK_PER_TRADE --value "$new_risk"
        made_adjustment=1
    else
        log "SKIP: risk already at max (${current_risk})"
    fi
fi

# SCENARIO E: Winrate recovering (20-30%) after tightening - HOLD STEADY
if (( $(echo "$winrate >= 20 && $winrate < 30" | bc -l 2>/dev/null || echo 0) )); then
    log "📊 INFO: Win rate recovering ($winrate%). Holding parameters steady."
fi

deactivate

if [ "$made_adjustment" -eq 0 ]; then
    log "✅ NO ADJUSTMENTS NEEDED - System operating within targets"
fi

log "AUTO-TUNE SERVICE COMPLETED"
log "=========================================="
log ""

exit 0
