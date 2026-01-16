#!/bin/bash
# quick_monitor.sh - Quick 2-minute activity check

echo "=== MONITORING LAST 2 MINUTES ==="
echo ""

# Check for threshold logging
echo "📊 Current Thresholds:"
sudo journalctl -u alpha-sniper-async.service --since "2 minutes ago" -o cat \
| grep 'EAGER_THRESHOLDS' | tail -1

echo ""
echo "🎯 Candidates Per Cycle:"
sudo journalctl -u alpha-sniper-async.service --since "2 minutes ago" -o cat \
| grep 'eager_candidates=' | tail -3

echo ""
echo "🚀 Trades Opened:"
count=$(sudo journalctl -u alpha-sniper-async.service --since "2 minutes ago" -o cat | grep -c 'OPENED LONG' || echo 0)
if [ "$count" -gt 0 ]; then
    echo "✅ $count trades opened in last 2 minutes:"
    sudo journalctl -u alpha-sniper-async.service --since "2 minutes ago" -o cat | grep 'OPENED LONG'
else
    echo "⏳ No trades yet in last 2 minutes"
fi

echo ""
echo "❌ Filter Rejections (last 2 min):"
sudo journalctl -u alpha-sniper-async.service --since "2 minutes ago" -o cat \
| grep 'EAGER_FILTERS' | awk -F'REJECT=' '{print $2}' | awk '{print $1}' | sort | uniq -c | sort -rn

echo ""
echo "=== DONE ==="
echo ""
echo "Run again: ./quick_monitor.sh"
echo "Live tail: sudo journalctl -u alpha-sniper-async.service -f | grep -E 'OPENED LONG|EAGER_THRESHOLDS'"
echo ""
