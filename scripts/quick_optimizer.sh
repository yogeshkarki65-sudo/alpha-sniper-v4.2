#!/bin/bash
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     ALPHA SNIPER QUICK OPTIMIZER                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Extract trade data efficiently
TRADES=$(sudo journalctl -u alpha-sniper-live.service --since "7 days ago" --no-pager | grep "Position closed")
TOTAL=$(echo "$TRADES" | wc -l)

if [ $TOTAL -eq 0 ]; then
    echo "❌ No trades found"
    exit 1
fi

echo "📊 PERFORMANCE ANALYSIS (Last 7 Days)"
echo "======================================================================"
echo "Total Trades: $TOTAL"
echo ""

# Win/Loss Analysis
WINS=$(echo "$TRADES" | grep -c "PnL: \$[0-9]" || echo "0")
LOSSES=$(echo "$TRADES" | grep -c "PnL: \$-" || echo "0")
WIN_RATE=$(echo "scale=1; $WINS * 100 / $TOTAL" | bc)

echo "Win Rate: ${WIN_RATE}% (${WINS}W / ${LOSSES}L)"
echo ""

# Exit Reasons
echo "EXIT REASONS:"
echo "$TRADES" | grep -oP 'Reason: \K[^$]+' | sort | uniq -c | sort -rn | head -5
echo ""

# Hold Time Analysis  
echo "HOLD TIME ANALYSIS:"
AVG_HOLD=$(echo "$TRADES" | grep -oP 'Hold: \K[\d.]+' | awk '{sum+=$1; count++} END {printf "%.1f", sum/count}')
MAX_HOLD=$(echo "$TRADES" | grep -oP 'Hold: \K[\d.]+' | sort -n | tail -1)
echo "Average Hold: ${AVG_HOLD}h"
echo "Max Hold: ${MAX_HOLD}h"
echo ""

# Check if mostly hitting max time
MAX_TIME_COUNT=$(echo "$TRADES" | grep -c "Max hold time" || echo "0")
MAX_TIME_PCT=$(echo "scale=0; $MAX_TIME_COUNT * 100 / $TOTAL" | bc)

echo "======================================================================"
echo "🤖 INTELLIGENT RECOMMENDATIONS"
echo "======================================================================"

# Recommendation 1: Max Hold Time
if [ $MAX_TIME_PCT -gt 50 ]; then
    echo "🔴 CRITICAL: MAX_HOLD_HOURS_PUMP"
    echo "   Current:     1.5-3h"
    echo "   Recommended: 24h"
    echo "   Reason:      ${MAX_TIME_PCT}% of trades hit time limit before targets"
    echo ""
fi

# Recommendation 2: Win Rate
if [ $(echo "$WIN_RATE < 45" | bc) -eq 1 ]; then
    echo "🟠 HIGH: MIN_SCORE_PUMP"
    echo "   Current:     0.7"
    echo "   Recommended: 0.75"
    echo "   Reason:      Win rate ${WIN_RATE}% is low - increase signal quality"
    echo ""
fi

# Recommendation 3: Pump-only mode
PUMP_TRADES=$(echo "$TRADES" | grep -ic "pump" || echo "0")
if [ $PUMP_TRADES -eq 0 ]; then
    echo "🟠 HIGH: PUMP_ONLY mode not active"
    echo "   Current:     Mixed engines (LONG/SHORT/etc)"
    echo "   Recommended: PUMP_ONLY=true"
    echo "   Reason:      No pump trades detected - verify pump-only mode"
    echo ""
fi

echo "======================================================================"
echo "📝 TO APPLY RECOMMENDATIONS:"
echo ""
echo "1. Edit env: sudo nano /etc/alpha-sniper/alpha-sniper-live.env"
echo "2. Make changes above"
echo "3. Restart: sudo systemctl restart alpha-sniper-live.service"
echo "======================================================================"
