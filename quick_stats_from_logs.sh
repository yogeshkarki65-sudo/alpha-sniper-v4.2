#!/bin/bash
# Quick stats from logs (if database not accessible)
# Usage: bash quick_stats_from_logs.sh

echo "=========================================="
echo "  Quick Stats from Logs (Last 24h)"
echo "=========================================="
echo ""

# Count trades from logs
OPENED=$(sudo journalctl -u alpha-sniper-async.service --since "24 hours ago" --no-pager -o cat | grep -c "\[EAGER\] OPENED" || echo "0")
CLOSED=$(sudo journalctl -u alpha-sniper-async.service --since "24 hours ago" --no-pager -o cat | grep -c "CLOSED LONG" || echo "0")

echo "📊 LAST 24 HOURS"
echo "----------------------------------------"
echo "Positions Opened: $OPENED"
echo "Positions Closed: $CLOSED"

if [ "$CLOSED" -gt 0 ]; then
    echo ""
    echo "Recent Closed Trades:"
    echo "----------------------------------------"
    sudo journalctl -u alpha-sniper-async.service --since "24 hours ago" --no-pager -o cat | grep -A 4 "CLOSED LONG" | tail -25
fi

echo ""
echo "🎯 RECENT OPENED POSITIONS"
echo "----------------------------------------"
sudo journalctl -u alpha-sniper-async.service --since "24 hours ago" --no-pager -o cat | grep "OPENED" | tail -5

echo ""
echo "📈 RECENT CANDIDATES"
echo "----------------------------------------"
echo "Top candidates in last hour:"
sudo journalctl -u alpha-sniper-async.service --since "1 hour ago" --no-pager -o cat | grep "\[EARLY_TOP\]" | head -10

echo ""
echo "=========================================="
echo ""
echo "For detailed stats with win rate and P&L:"
echo "  bash check_performance.sh"
echo ""
