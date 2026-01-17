#!/usr/bin/env bash
# alpha_autotune.sh - Autonomous 6-hour parameter tuner
# Run via cron: 0 */6 * * * /opt/alpha-sniper/scripts/alpha_autotune.sh

set -euo pipefail

DB_PATH="/opt/alpha-sniper/data/alpha_async.db"
OVERRIDES_CLI="/opt/alpha-sniper/scripts/overrides_cli.py"
TELEGRAM_NOTIFY="/opt/alpha-sniper/scripts/telegram_notify.py"
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

# Decision logic - Enhanced for all scenarios
if [ "$n" -ge 20 ]; then
    # Enough data to judge quality
    if (( $(echo "$wr < 25" | bc -l) )); then
        # Low winrate: tighten aggressively
        new_ret=$(echo "$current_ret + $RET_STEP" | bc)
        new_vsp=$(echo "$current_vsp + $VSP_STEP" | bc)
        action="TUNE:TIGHTEN"

        # Clamp - if already at max ret, reduce risk instead
        if (( $(echo "$new_ret > $RET_MAX" | bc -l) )); then
            new_ret=$RET_MAX
            if [ "$sizing_auto" = "true" ]; then
                new_risk=$(echo "$current_risk - $RISK_STEP" | bc)
                if (( $(echo "$new_risk < $RISK_MIN" | bc -l) )); then new_risk=$RISK_MIN; fi
                action="TUNE:TIGHTEN+RISK_DOWN"
            fi
        fi
        if (( $(echo "$new_vsp > $VSP_MAX" | bc -l) )); then new_vsp=$VSP_MAX; fi

    elif (( $(echo "$wr >= 25" | bc -l) )) && (( $(echo "$wr < 30" | bc -l) )); then
        # 25-30% winrate zone: check profitability
        if (( $(echo "$avg_pnl > 0" | bc -l) )); then
            # Profitable despite medium WR - hold or slight loosen
            if [ "$n" -ge 40 ]; then
                new_ret=$(echo "$current_ret - $RET_STEP" | bc)
                action="TUNE:LOOSEN_GENTLE"
                if (( $(echo "$new_ret < $RET_MIN" | bc -l) )); then new_ret=$RET_MIN; fi
            else
                action="HOLD:WR_25-30_PROFITABLE"
            fi
        else
            # Not profitable - slight tighten
            new_ret=$(echo "$current_ret + $RET_STEP" | bc)
            action="TUNE:TIGHTEN_GENTLE"
            if (( $(echo "$new_ret > $RET_MAX" | bc -l) )); then new_ret=$RET_MAX; fi
        fi

    elif (( $(echo "$wr >= 30" | bc -l) )) && (( $(echo "$wr < 35" | bc -l) )); then
        # 30-35% winrate zone: check profitability
        if (( $(echo "$avg_pnl > 0" | bc -l) )); then
            # Profitable and decent WR - slight loosen to increase flow
            new_ret=$(echo "$current_ret - $RET_STEP" | bc)
            action="TUNE:LOOSEN_GENTLE"
            if (( $(echo "$new_ret < $RET_MIN" | bc -l) )); then new_ret=$RET_MIN; fi
        else
            # Not profitable despite decent WR - check R-ratio
            action="HOLD:WR_30-35_CHECK_RATIO"
        fi

    elif (( $(echo "$wr >= 35" | bc -l) )) && (( $(echo "$wr < 40" | bc -l) )); then
        # 35-40% winrate zone: good performance
        if (( $(echo "$avg_pnl > 0" | bc -l) )); then
            # Happy zone - hold current settings
            action="HOLD:WR_35-40_OPTIMAL"
        else
            # Good WR but losing money - tighten slightly (R-ratio issue)
            new_ret=$(echo "$current_ret + $RET_STEP" | bc)
            action="TUNE:TIGHTEN_GENTLE"
            if (( $(echo "$new_ret > $RET_MAX" | bc -l) )); then new_ret=$RET_MAX; fi
        fi

    elif (( $(echo "$wr >= 40" | bc -l) )); then
        # Excellent winrate: loosen to increase trade volume
        new_ret=$(echo "$current_ret - $RET_STEP" | bc)
        action="TUNE:LOOSEN"

        # Clamp
        if (( $(echo "$new_ret < $RET_MIN" | bc -l) )); then new_ret=$RET_MIN; fi
    fi

elif [ "$n" -ge 10 ]; then
    # 10-19 trades: some data but not enough to judge quality
    if (( $(echo "$wr < 20" | bc -l) )); then
        # Very low winrate with limited data - tighten
        new_ret=$(echo "$current_ret + $RET_STEP" | bc)
        action="TUNE:TIGHTEN_LIMITED_DATA"
        if (( $(echo "$new_ret > $RET_MAX" | bc -l) )); then new_ret=$RET_MAX; fi
    else
        # Seed more flow by lowering vspike
        new_vsp=$(echo "$current_vsp - $VSP_STEP" | bc)
        action="TUNE:SEED_FLOW_LIMITED"
        if (( $(echo "$new_vsp < $VSP_MIN" | bc -l) )); then new_vsp=$VSP_MIN; fi
    fi

else
    # < 10 trades: seed flow by lowering vspike
    new_vsp=$(echo "$current_vsp - $VSP_STEP" | bc)
    action="TUNE:SEED_FLOW"

    # Clamp - if already at min, can't loosen more
    if (( $(echo "$new_vsp < $VSP_MIN" | bc -l) )); then
        new_vsp=$VSP_MIN
        action="HOLD:VSP_AT_MIN"
    fi
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

# Send Telegram notification for significant events
notify_telegram() {
    local msg="$1"
    local severity="${2:-info}"
    if [ -f "$TELEGRAM_NOTIFY" ]; then
        source "$VENV"
        python "$TELEGRAM_NOTIFY" --severity "$severity" "$msg" 2>/dev/null || true
        deactivate
    fi
}

# Build notification message
telegram_msg=""
telegram_severity="tune"

if [ "$changed" -eq 1 ]; then
    # Parameter change notification
    case "$action" in
        TUNE:TIGHTEN|TUNE:TIGHTEN+RISK_DOWN)
            telegram_msg="🔴 AUTO-TUNE: Tightening filters
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚙️ New settings: ret5m=${new_ret} vsp=${new_vsp} risk=${new_risk}
📉 Action: $action"
            telegram_severity="warning"
            ;;
        TUNE:LOOSEN|TUNE:LOOSEN_GENTLE)
            telegram_msg="🟢 AUTO-TUNE: Loosening filters
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚙️ New settings: ret5m=${new_ret} vsp=${new_vsp} risk=${new_risk}
📈 Action: $action"
            telegram_severity="success"
            ;;
        TUNE:SEED_FLOW*)
            telegram_msg="🟡 AUTO-TUNE: Seeding trade flow
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚙️ New settings: ret5m=${new_ret} vsp=${new_vsp} risk=${new_risk}
💧 Action: $action"
            telegram_severity="info"
            ;;
        *)
            telegram_msg="⚙️ AUTO-TUNE: Parameters adjusted
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚙️ New settings: ret5m=${new_ret} vsp=${new_vsp} risk=${new_risk}
🔧 Action: $action"
            telegram_severity="tune"
            ;;
    esac
elif [[ "$action" == HOLD:WR_35-40_OPTIMAL ]]; then
    # Optimal performance notification (every 6h when in sweet spot)
    telegram_msg="✅ AUTO-TUNE: System performing optimally
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚙️ Current settings: ret5m=${new_ret} vsp=${new_vsp} risk=${new_risk}
🎯 Status: No changes needed"
    telegram_severity="success"
elif [[ "$action" == HOLD:VSP_AT_MIN ]]; then
    # Critical: vspike at minimum but still not enough trades
    telegram_msg="🚨 AUTO-TUNE: Low trade volume (vspike at minimum)
📊 Performance (6h): $n trades, ${wr}% WR, P&L \$$avg_pnl
⚠️ Current settings: ret5m=${new_ret} vsp=${new_vsp} (MIN) risk=${new_risk}
🔍 Status: Check market conditions or filter rejections"
    telegram_severity="critical"
fi

# Send notification if message was built
if [ -n "$telegram_msg" ]; then
    notify_telegram "$telegram_msg" "$telegram_severity"
fi

# Restart service if parameters changed (requires systemd)
if [ "$changed" -eq 1 ]; then
    if command -v systemctl >/dev/null 2>&1; then
        systemctl restart alpha-sniper-async.service 2>/dev/null || true
        echo "alpha_autotune: n=$n wr=$wr avg_pnl=$avg_pnl ret=$new_ret vsp=$new_vsp risk=$new_risk action=$action [SERVICE_RESTARTED]"
    else
        echo "alpha_autotune: n=$n wr=$wr avg_pnl=$avg_pnl ret=$new_ret vsp=$new_vsp risk=$new_risk action=$action [NO_SYSTEMD]"
    fi
else
    echo "alpha_autotune: n=$n wr=$wr avg_pnl=$avg_pnl ret=$new_ret vsp=$new_vsp risk=$new_risk action=$action"
fi

exit 0
