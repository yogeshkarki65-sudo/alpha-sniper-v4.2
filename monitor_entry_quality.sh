#!/bin/bash
# monitor_entry_quality.sh - Entry Quality Performance Dashboard
# Usage: ./monitor_entry_quality.sh [time_window]
# Example: ./monitor_entry_quality.sh "6 hours ago"
#          ./monitor_entry_quality.sh "2 hours ago"

since="${1:-6 hours ago}"

echo "========================================"
echo "ENTRY QUALITY MONITORING DASHBOARD"
echo "Time Window: $since"
echo "========================================"

# A) Filter Effectiveness
echo ""
echo "---- FILTER REJECTION BREAKDOWN ----"
rejection_counts=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep -E '\[EAGER_FILTERS\]' \
 | awk -F'REJECT=' '{print $2}' | awk '{print $1}' \
 | sort | uniq -c | sort -nr)

if [ -z "$rejection_counts" ]; then
    echo "No filter rejections found (filters may not be active or no candidates)"
else
    echo "$rejection_counts"
    total_rejects=$(echo "$rejection_counts" | awk '{sum+=$1} END {print sum}')
    echo "Total Rejections: $total_rejects"
fi

echo ""
echo "---- CURRENT THRESHOLDS ----"
threshold_log=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep '\[EAGER_THRESHOLDS\]' | tail -1)

if [ -z "$threshold_log" ]; then
    echo "No threshold logs found (EAGER may not be running)"
else
    echo "$threshold_log"
fi

echo ""
echo "---- AUTOTUNE STATUS ----"
autotune_logs=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep -E 'AUTOTUNE_PRO|WINRATE_ADJUST' | tail -5)

if [ -z "$autotune_logs" ]; then
    echo "✅ No AUTOTUNE activity (oscillation stopped - good!)"
else
    echo "$autotune_logs"
fi

# B) Flow Metrics
echo ""
echo "---- ENTRY FLOW RATES ----"
flow_stats=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep 'eager_candidates=' \
 | awk -F'eager_candidates=| eager_attempted=| eager_opened=' '{
     c+=$2; a+=$3; o+=$4; n++
   } END {
     if (n > 0) {
         cand = c/n;
         ar = (c > 0) ? 100*a/c : 0;
         or = (a > 0) ? 100*o/a : 0;
         printf "Cycles: %d\nCandidates/cycle: %.2f\nAttempt rate: %.1f%%\nOpen rate: %.1f%%\n", n, cand, ar, or
     } else {
         print "No flow data found"
     }
   }')

if [ -z "$flow_stats" ]; then
    echo "No EAGER flow data found (check if EAGER is enabled)"
else
    echo "$flow_stats"
fi

# C) Trade Performance
echo ""
echo "---- TRADE PERFORMANCE ----"
db_path="/opt/alpha-sniper/data/alpha_async.db"

if [ ! -f "$db_path" ]; then
    echo "Database not found at $db_path"
else
    trade_stats=$(sqlite3 "$db_path" "
SELECT
  COUNT(*)                              AS trades,
  ROUND(100.0*SUM(pnl_usd>0)/COUNT(*),1) AS winrate_pct,
  ROUND(AVG(pnl_usd),4)                 AS avg_pnl,
  ROUND(AVG(CASE WHEN pnl_usd>0 THEN pnl_usd END),4) AS avg_winner,
  ROUND(AVG(CASE WHEN pnl_usd<=0 THEN pnl_usd END),4) AS avg_loser,
  ROUND(AVG(hold_time_hours*60),1)      AS avg_hold_min
FROM trades
WHERE closed_at > strftime('%s','now','-${since}');
" 2>/dev/null)

    if [ -z "$trade_stats" ]; then
        echo "No trades found in time window"
    else
        echo "$trade_stats" | awk -F'|' '{
            printf "Trades: %s\n", $1
            printf "Win Rate: %s%%\n", $2
            printf "Avg P&L: $%s\n", $3
            printf "Avg Winner: $%s\n", $4
            printf "Avg Loser: $%s\n", $5
            printf "Avg Hold Time: %s min\n", $6
        }'
    fi
fi

# D) Regime Detection
echo ""
echo "---- REGIME ADJUSTMENTS ----"
regime_logs=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep 'REGIME=' | tail -10)

if [ -z "$regime_logs" ]; then
    echo "No regime adjustments detected (ENTRY_REGIME_AWARE_ENABLE may be off or BTC neutral)"
else
    echo "$regime_logs"
fi

# E) Sizing Issues
echo ""
echo "---- SIZING & RESERVE CLAMPS ----"
sizing_logs=$(sudo journalctl -u alpha-sniper-async.service --since "$since" -o cat \
 | grep -E 'capped by reserve|unaffordable after clamp' | tail -10)

if [ -z "$sizing_logs" ]; then
    echo "No sizing clamps detected (good - sufficient balance)"
else
    echo "$sizing_logs"
fi

echo ""
echo "========================================"
echo "MONITORING COMPLETE"
echo "========================================"
echo ""
echo "💡 Interpretation Guide:"
echo "  • Filter Mix: High WICK/EMA_TREND rejections = avoiding fakeouts (good)"
echo "  • Flow: Target cand/cycle 0.3-1.0, attempt_rate 20-60%, open_rate 40-90%"
echo "  • Performance: Target win rate ≥30% with avg_winner ≥ |avg_loser|"
echo "  • Regime: STRICT mode in BTC downtrends, LOOSE in uptrends"
echo ""
echo "📊 Quick Actions:"
echo "  • Winrate <25% but enough attempts → Tighten ret5m or vspike"
echo "  • Winrate >35% but too few trades → Loosen vspike first"
echo "  • Low open_rate <25% → Increase EAGER_EPS_PCT"
echo "  • Good winrate ≥30% → Scale up RISK_PER_TRADE gradually"
echo ""
