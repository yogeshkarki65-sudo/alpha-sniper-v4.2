#!/usr/bin/env bash
# alpha_autotune.sh - Autonomous 6-hour parameter tuner
# Run via cron: 0 */6 * * * /opt/alpha-sniper/scripts/alpha_autotune.sh

set -euo pipefail

DB_PATH="/opt/alpha-sniper/data/alpha_async.db"
OVERRIDES_CLI="/opt/alpha-sniper/scripts/overrides_cli.py"
VENV="/opt/alpha-sniper/venv/bin/activate"

# Lookback window (6 hours)
LOOKBACK_SECONDS=$((6 * 3600))

# Safe bounds
RET_MIN=0.014
RET_MAX=0.035
RET_STEP=0.001

VSP_MIN=1.60
VSP_MAX=4.00
VSP_STEP=0.10

RISK_MIN=0.0010
RISK_MAX=0.0030
RISK_STEP=0.0002

cd /opt/alpha-sniper
source "$VENV"

# Read current settings
get_setting() {
    python "$OVERRIDES_CLI" get --key "$1" 2>/dev/null | grep -oP '[\d.]+' | head -1 || echo "$2"
}

current_ret=$(get_setting "EARLY_RET_5M_MIN" "0.019")
current_vsp=$(get_setting "EARLY_VOL_SPIKE_MIN" "1.8")
current_eps=$(get_setting "EAGER_EPS_PCT" "0.0012")
current_risk=$(get_setting "RISK_PER_TRADE" "0.0020")
sizing_auto=$(get_setting "SIZING_AUTOPILOT_ENABLE" "false")

# Query recent trades
if [ ! -f "$DB_PATH" ]; then
    echo "alpha_autotune: DB not found, skipping"
    deactivate
    exit 0
fi

now=$(date +%s)
cutoff=$((now - LOOKBACK_SECONDS))

read -r n wr avg_pnl <<< $(sqlite3 "$DB_PATH" "
SELECT
  COUNT(*) as n,
  ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as wr,
  ROUND(AVG(pnl_usd), 4) as avg_pnl
FROM trades
WHERE closed_at >= $cutoff
" 2>/dev/null | tr '|' ' ' || echo "0 0 0")

action="HOLD"
new_ret="$current_ret"
new_vsp="$current_vsp"
new_risk="$current_risk"

# Decision logic
if [ "$n" -ge 20 ]; then
    # Enough data to judge quality
    if (( $(echo "$wr < 25" | bc -l) )); then
        # Low winrate: tighten
        new_ret=$(echo "$current_ret + $RET_STEP" | bc)
        new_vsp=$(echo "$current_vsp + $VSP_STEP" | bc)
        action="TUNE:TIGHTEN"

        # Clamp
        if (( $(echo "$new_ret > $RET_MAX" | bc -l) )); then new_ret=$RET_MAX; fi
        if (( $(echo "$new_vsp > $VSP_MAX" | bc -l) )); then new_vsp=$VSP_MAX; fi

    elif [ "$n" -ge 30 ] && (( $(echo "$wr >= 40" | bc -l) )); then
        # Good winrate with volume: slightly loosen ret
        new_ret=$(echo "$current_ret - $RET_STEP" | bc)
        action="TUNE:LOOSEN"

        # Clamp
        if (( $(echo "$new_ret < $RET_MIN" | bc -l) )); then new_ret=$RET_MIN; fi
    fi
else
    # Not enough trades: seed flow by lowering vspike
    new_vsp=$(echo "$current_vsp - $VSP_STEP" | bc)
    action="TUNE:SEED_FLOW"

    # Clamp
    if (( $(echo "$new_vsp < $VSP_MIN" | bc -l) )); then new_vsp=$VSP_MIN; fi
fi

# Risk sizing auto-adjust (only if enabled and enough data)
if [ "$sizing_auto" = "true" ] && [ "$n" -ge 10 ]; then
    if (( $(echo "$wr >= 35" | bc -l) )); then
        # Scale up
        new_risk=$(echo "$current_risk + $RISK_STEP" | bc)
        if (( $(echo "$new_risk > $RISK_MAX" | bc -l) )); then new_risk=$RISK_MAX; fi
        action="${action}+RISK_UP"
    elif (( $(echo "$wr <= 20" | bc -l) )); then
        # Scale down
        new_risk=$(echo "$current_risk - $RISK_STEP" | bc)
        if (( $(echo "$new_risk < $RISK_MIN" | bc -l) )); then new_risk=$RISK_MIN; fi
        action="${action}+RISK_DOWN"
    fi
fi

# Apply changes if different
changed=0

if [ "$new_ret" != "$current_ret" ]; then
    python "$OVERRIDES_CLI" set --key EARLY_RET_5M_MIN --value "$new_ret" >/dev/null 2>&1
    changed=1
fi

if [ "$new_vsp" != "$current_vsp" ]; then
    # Set both vspike keys (CLI auto-syncs but be explicit)
    python "$OVERRIDES_CLI" set --key EARLY_VOL_SPIKE_MIN --value "$new_vsp" >/dev/null 2>&1
    python "$OVERRIDES_CLI" set --key EAGER_VSPIKE_MIN --value "$new_vsp" >/dev/null 2>&1
    changed=1
fi

if [ "$new_risk" != "$current_risk" ]; then
    python "$OVERRIDES_CLI" set --key RISK_PER_TRADE --value "$new_risk" >/dev/null 2>&1
    changed=1
fi

# Ensure critical filters are enabled
python "$OVERRIDES_CLI" set --key ENTRY_TREND_EMA_CHECK_ENABLE --value true >/dev/null 2>&1
python "$OVERRIDES_CLI" set --key ENTRY_ACCEL_ENABLE --value true >/dev/null 2>&1
python "$OVERRIDES_CLI" set --key ENTRY_WICK_FILTER_ENABLE --value true >/dev/null 2>&1
python "$OVERRIDES_CLI" set --key BTC_GUARD_ENABLE --value true >/dev/null 2>&1

# Ensure autotune settings
python "$OVERRIDES_CLI" set --key AUTOTUNE_MIN_DWELL_MIN --value 60 >/dev/null 2>&1
python "$OVERRIDES_CLI" set --key AUTOTUNE_FLOW_ENABLE --value false >/dev/null 2>&1
python "$OVERRIDES_CLI" set --key WINRATE_ADJUST_ENABLE --value true >/dev/null 2>&1

deactivate

# Log summary
echo "alpha_autotune: n=$n wr=$wr ret=$new_ret vsp=$new_vsp risk=$new_risk action=$action"

exit 0
