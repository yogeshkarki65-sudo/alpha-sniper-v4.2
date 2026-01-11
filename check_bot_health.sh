#!/bin/bash
# Quick health check for Alpha Sniper
# Usage: bash check_bot_health.sh

echo "========================================"
echo "  Alpha Sniper Health Check"
echo "========================================"
echo ""

# Check service status
echo "1. Service Status:"
if sudo systemctl is-active --quiet alpha-sniper-async.service; then
    echo "   ✅ Service is RUNNING"
else
    echo "   ❌ Service is STOPPED"
    echo ""
    echo "To start: sudo systemctl start alpha-sniper-async.service"
    exit 1
fi
echo ""

# Check recent activity
echo "2. Recent Activity (last 5 minutes):"
SCANS=$(sudo journalctl -u alpha-sniper-async.service --since "5 minutes ago" --no-pager | grep -c "SCAN #" || echo "0")
CANDIDATES=$(sudo journalctl -u alpha-sniper-async.service --since "5 minutes ago" --no-pager | grep -c "EARLY_TOP" || echo "0")
OPENED=$(sudo journalctl -u alpha-sniper-async.service --since "5 minutes ago" --no-pager | grep -c "EAGER.*OPENED" || echo "0")
CLOSED=$(sudo journalctl -u alpha-sniper-async.service --since "5 minutes ago" --no-pager | grep -c "CLOSED" || echo "0")

echo "   📊 Scans completed: $SCANS"
echo "   🎯 Candidates found: $CANDIDATES"
echo "   ✅ Positions opened: $OPENED"
echo "   ❌ Positions closed: $CLOSED"
echo ""

# Check for errors
echo "3. Recent Errors:"
ERRORS=$(sudo journalctl -u alpha-sniper-async.service --since "10 minutes ago" --no-pager | grep -c "ERROR" || echo "0")
if [ "$ERRORS" -eq 0 ]; then
    echo "   ✅ No errors in last 10 minutes"
else
    echo "   ⚠️  Found $ERRORS errors - checking details..."
    sudo journalctl -u alpha-sniper-async.service --since "10 minutes ago" --no-pager | grep "ERROR" | tail -3
fi
echo ""

# Check LIVE_TEST_MODE
echo "4. Configuration:"
TEST_MODE=$(sudo journalctl -u alpha-sniper-async.service --since "30 minutes ago" --no-pager | grep "LIVE_TEST_MODE" | tail -1 | grep -o "LIVE_TEST_MODE: [A-Za-z]*" || echo "LIVE_TEST_MODE: Unknown")
echo "   $TEST_MODE"

# Check recent trade caps
CAPPED=$(sudo journalctl -u alpha-sniper-async.service --since "30 minutes ago" --no-pager | grep "\[LIVE_TEST\].*capped" | tail -1)
if [ -n "$CAPPED" ]; then
    echo "   ✅ Size capping active"
    echo "      Latest: $CAPPED"
else
    echo "   ℹ️  No size caps in last 30 min (normal if no trades)"
fi
echo ""

# Show last trade
echo "5. Last Trade Activity:"
LAST_OPEN=$(sudo journalctl -u alpha-sniper-async.service --since "1 hour ago" --no-pager | grep "OPENED" | tail -1)
LAST_CLOSE=$(sudo journalctl -u alpha-sniper-async.service --since "1 hour ago" --no-pager | grep "CLOSED" | tail -1)

if [ -n "$LAST_OPEN" ]; then
    echo "   Last OPEN: $LAST_OPEN"
else
    echo "   Last OPEN: None in last hour"
fi

if [ -n "$LAST_CLOSE" ]; then
    echo "   Last CLOSE: $LAST_CLOSE"
else
    echo "   Last CLOSE: None in last hour"
fi
echo ""

# Overall status
echo "========================================"
if sudo systemctl is-active --quiet alpha-sniper-async.service && [ "$ERRORS" -eq 0 ] && [ "$SCANS" -gt 0 ]; then
    echo "  Overall Status: ✅ HEALTHY"
    echo ""
    echo "  Bot is scanning, finding candidates,"
    echo "  and trading within test mode limits."
else
    echo "  Overall Status: ⚠️  NEEDS ATTENTION"
    echo ""
    if [ "$SCANS" -eq 0 ]; then
        echo "  No scans detected in last 5 minutes."
        echo "  Service may have just started."
        echo "  Wait 60 seconds and run again."
    fi
fi
echo "========================================"
echo ""

echo "To watch live activity:"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep -E 'SCAN|EAGER|OPENED|CLOSED'"
echo ""
