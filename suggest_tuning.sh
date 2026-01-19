#!/bin/bash
# suggest_tuning.sh - Auto-generate tuning suggestions based on performance data
# Usage: ./suggest_tuning.sh [time_window]
# Example: ./suggest_tuning.sh "6 hours ago"

since="${1:-6 hours ago}"
db_path="/opt/alpha-sniper/data/alpha_async.db"

echo "========================================"
echo "AUTO-TUNING SUGGESTIONS"
echo "Time Window: $since"
echo "========================================"

# Get current settings
cd /opt/alpha-sniper
source venv/bin/activate 2>/dev/null

echo ""
echo "---- CURRENT SETTINGS ----"
current_ret5m=$(python scripts/overrides_cli.py get --key EARLY_RET_5M_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_vspike=$(python scripts/overrides_cli.py get --key EARLY_VOL_SPIKE_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_risk=$(python scripts/overrides_cli.py get --key RISK_PER_TRADE 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_eps=$(python scripts/overrides_cli.py get --key EAGER_EPS_PCT 2>/dev/null | grep -oP '[\d.]+' | head -1)
current_depth=$(python scripts/overrides_cli.py get --key EAGER_MIN_DEPTH_USD 2>/dev/null | grep -oP '[\d.]+' | head -1)

echo "EARLY_RET_5M_MIN: ${current_ret5m:-0.018}"
echo "EARLY_VOL_SPIKE_MIN: ${current_vspike:-2.0}"
echo "RISK_PER_TRADE: ${current_risk:-0.0020}"
echo "EAGER_EPS_PCT: ${current_eps:-0.0010}"
echo "EAGER_MIN_DEPTH_USD: ${current_depth:-8000}"

deactivate 2>/dev/null

# Get trade stats
if [ ! -f "$db_path" ]; then
    echo ""
    echo "❌ Database not found at $db_path"
    exit 1
fi

trade_data=$(sqlite3 "$db_path" "
SELECT
  COUNT(*) as trades,
  ROUND(100.0*SUM(pnl_usd>0)/COUNT(*),1) as winrate,
  ROUND(AVG(pnl_usd),4) as avg_pnl
FROM trades
WHERE closed_at > strftime('%s','now','-${since}');
" 2>/dev/null)

trades=$(echo "$trade_data" | cut -d'|' -f1)
winrate=$(echo "$trade_data" | cut -d'|' -f2)
avg_pnl=$(echo "$trade_data" | cut -d'|' -f3)

# Get flow stats
flow_data=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
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

echo ""
echo "---- PERFORMANCE METRICS ----"
echo "Trades: ${trades:-0}"
echo "Win Rate: ${winrate:-0}%"
echo "Avg P&L: \$${avg_pnl:-0}"
echo "Candidates/cycle: ${cand_per_cycle:-0}"
echo "Attempt Rate: ${attempt_rate:-0}%"
echo "Open Rate: ${open_rate:-0}%"

echo ""
echo "========================================"
echo "📊 TUNING RECOMMENDATIONS"
echo "========================================"

# Default values if not set
: ${current_ret5m:=0.018}
: ${current_vspike:=2.0}
: ${current_risk:=0.0020}
: ${current_eps:=0.0010}
: ${current_depth:=8000}
: ${winrate:=0}
: ${trades:=0}
: ${cand_per_cycle:=0}
: ${attempt_rate:=0}
: ${open_rate:=0}

suggestions=0

# Scenario A: Too many losers (winrate < 25%) but still enough attempts
if (( $(echo "$winrate < 25" | bc -l 2>/dev/null || echo 0) )) && (( trades > 5 )); then
    echo ""
    echo "🔴 ISSUE: Low Win Rate (<25%)"
    echo "   Problem: Taking too many losing trades"
    echo ""
    echo "   💡 RECOMMENDATION: Tighten entry thresholds"
    new_ret5m=$(echo "$current_ret5m + 0.002" | bc)
    new_vspike=$(echo "$current_vspike + 0.2" | bc)
    echo "   python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value $new_ret5m"
    echo "   python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value $new_vspike"
    echo "   # Or tighten wick filter:"
    echo "   python scripts/overrides_cli.py set --key ENTRY_WICK_BODY_MIN_PCT --value 0.0007"
    suggestions=$((suggestions + 1))
fi

# Scenario B: Almost no trades (cand/cycle < 0.2) and winrate >= 35%
if (( $(echo "$cand_per_cycle < 0.2" | bc -l 2>/dev/null || echo 0) )) && (( $(echo "$winrate >= 35" | bc -l 2>/dev/null || echo 0) )); then
    echo ""
    echo "🟡 ISSUE: Too Few Trades (cand/cycle < 0.2)"
    echo "   Problem: Filters too strict, missing opportunities"
    echo ""
    echo "   💡 RECOMMENDATION: Loosen thresholds slightly"
    new_vspike=$(echo "$current_vspike - 0.2" | bc)
    new_ret5m=$(echo "$current_ret5m - 0.002" | bc)
    echo "   # Loosen volume first (safer):"
    echo "   python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value $new_vspike"
    echo "   # If still dry, then loosen momentum:"
    echo "   python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value $new_ret5m"
    suggestions=$((suggestions + 1))
fi

# Scenario C: Many attempts but low opens (open_rate < 25%)
if (( $(echo "$open_rate < 25" | bc -l 2>/dev/null || echo 0) )) && (( $(echo "$attempt_rate > 10" | bc -l 2>/dev/null || echo 0) )); then
    echo ""
    echo "🟠 ISSUE: Low Open Rate (<25%)"
    echo "   Problem: Limit orders not filling (IOC rejected)"
    echo ""
    echo "   💡 RECOMMENDATION: Increase trigger epsilon or depth"
    new_eps=$(echo "$current_eps + 0.0003" | bc)
    new_depth=$((current_depth + 2000))
    echo "   # Bump trigger epsilon:"
    echo "   python scripts/overrides_cli.py set --key EAGER_EPS_PCT --value $new_eps"
    echo "   # Or increase depth requirement:"
    echo "   python scripts/overrides_cli.py set --key EAGER_MIN_DEPTH_USD --value $new_depth"
    suggestions=$((suggestions + 1))
fi

# Scenario D: Good winrate (>= 30%) and stable flow
if (( $(echo "$winrate >= 30" | bc -l 2>/dev/null || echo 0) )) && (( trades > 8 )); then
    echo ""
    echo "🟢 STATUS: Good Win Rate (≥30%)"
    echo "   Performance: System working well"
    echo ""
    echo "   💡 RECOMMENDATION: Scale up position sizing gradually"
    new_risk=$(echo "$current_risk + 0.0005" | bc)
    echo "   # Increase risk per trade in small steps:"
    echo "   python scripts/overrides_cli.py set --key RISK_PER_TRADE --value $new_risk"
    echo "   # Monitor for 2-4 hours, then repeat if stable"
    suggestions=$((suggestions + 1))
fi

# Additional suggestions based on filter analysis
echo ""
echo "---- ADDITIONAL CHECKS ----"

# Check for spread issues
spread_rejects=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep 'REJECT=SPREAD' | wc -l)

if [ "$spread_rejects" -gt 10 ]; then
    echo ""
    echo "ℹ️  HIGH SPREAD REJECTIONS ($spread_rejects)"
    echo "   Many trades rejected due to wide spreads (illiquid books)"
    echo "   This is GOOD - protecting from high slippage"
    echo "   Consider: Keep ENTRY_SPREAD_MAX_PCT = 0.0030 (current setting)"
fi

# Check for regime adjustments
regime_strict=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep 'REGIME=STRICT' | wc -l)

regime_loose=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep 'REGIME=LOOSE' | wc -l)

if [ "$regime_strict" -gt 0 ]; then
    echo ""
    echo "ℹ️  REGIME STRICT MODE ACTIVE ($regime_strict times)"
    echo "   BTC in downtrend - thresholds automatically tightened"
    echo "   This is normal during market weakness"
fi

if [ "$regime_loose" -gt 0 ]; then
    echo ""
    echo "ℹ️  REGIME LOOSE MODE ACTIVE ($regime_loose times)"
    echo "   BTC in uptrend - thresholds automatically loosened"
    echo "   Riding beta tailwind (expected in bull market)"
fi

if [ "$suggestions" -eq 0 ]; then
    echo ""
    echo "✅ NO MAJOR ISSUES DETECTED"
    echo "   System appears to be operating within acceptable parameters"
    echo "   Continue monitoring. Run again in 2-4 hours."
fi

echo ""
echo "========================================"
echo "📚 NEXT STEPS"
echo "========================================"
echo "1. Review recommendations above"
echo "2. Apply ONE change at a time"
echo "3. Monitor for 2-4 hours after each change"
echo "4. Re-run this script to validate impact"
echo ""
echo "⚠️  CAUTION: Do not apply multiple changes simultaneously"
echo "   This makes it impossible to isolate which change helped/hurt"
echo ""
