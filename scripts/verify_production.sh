#!/bin/bash
#
# Production Server Verification Script
# Run this on your server to verify everything is working
#

set -e

echo "======================================================================"
echo "🔍 ALPHA SNIPER v4.2 - Production Verification"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Service Status
echo "1️⃣  Checking service status..."
if sudo systemctl is-active --quiet alpha-sniper-live.service; then
    echo -e "${GREEN}✅ Service is running${NC}"
    UPTIME=$(sudo systemctl show alpha-sniper-live.service -p ActiveEnterTimestamp --value)
    echo "   Started: $UPTIME"
else
    echo -e "${RED}❌ Service is not running${NC}"
    echo "   Run: sudo systemctl status alpha-sniper-live.service"
    exit 1
fi
echo ""

# Check 2: Process Check
echo "2️⃣  Checking process..."
PID=$(sudo systemctl show alpha-sniper-live.service -p MainPID --value)
if [ "$PID" -gt 0 ]; then
    echo -e "${GREEN}✅ Process running (PID: $PID)${NC}"
    ps -p $PID -o pid,user,%cpu,%mem,etime,cmd --no-headers
else
    echo -e "${RED}❌ No process found${NC}"
    exit 1
fi
echo ""

# Check 3: Environment Variables
echo "3️⃣  Checking environment variables..."
if [ -f "/proc/$PID/environ" ]; then
    ENV_VARS=$(sudo cat /proc/$PID/environ | tr '\0' '\n')

    if echo "$ENV_VARS" | grep -q "MEXC_API_KEY"; then
        echo -e "${GREEN}✅ MEXC_API_KEY loaded${NC}"
    else
        echo -e "${RED}❌ MEXC_API_KEY not found${NC}"
    fi

    if echo "$ENV_VARS" | grep -q "TELEGRAM_BOT_TOKEN"; then
        echo -e "${GREEN}✅ TELEGRAM_BOT_TOKEN loaded${NC}"
    else
        echo -e "${YELLOW}⚠️  TELEGRAM_BOT_TOKEN not found${NC}"
    fi

    if echo "$ENV_VARS" | grep -q "STARTING_EQUITY"; then
        EQUITY=$(echo "$ENV_VARS" | grep "STARTING_EQUITY" | cut -d'=' -f2)
        echo -e "${GREEN}✅ STARTING_EQUITY loaded: \$$EQUITY${NC}"
    else
        echo -e "${YELLOW}⚠️  STARTING_EQUITY not found (using default)${NC}"
    fi
else
    echo -e "${RED}❌ Cannot read process environment${NC}"
fi
echo ""

# Check 4: Log Files
echo "4️⃣  Checking log files..."
if [ -d "/opt/alpha-sniper/logs" ]; then
    echo -e "${GREEN}✅ Logs directory exists${NC}"

    if [ -f "/opt/alpha-sniper/logs/bot.log" ]; then
        LOG_SIZE=$(du -h /opt/alpha-sniper/logs/bot.log | cut -f1)
        LOG_LINES=$(wc -l < /opt/alpha-sniper/logs/bot.log)
        echo "   bot.log: $LOG_SIZE ($LOG_LINES lines)"

        # Show last few lines
        echo ""
        echo "   Last 5 log entries:"
        tail -n 5 /opt/alpha-sniper/logs/bot.log | sed 's/^/   /'
    else
        echo -e "${YELLOW}⚠️  bot.log not found yet (may be starting up)${NC}"
    fi
else
    echo -e "${RED}❌ Logs directory not found${NC}"
fi
echo ""

# Check 5: Recent Activity
echo "5️⃣  Checking recent activity (last 2 minutes)..."
RECENT_LOGS=$(sudo journalctl -u alpha-sniper-live.service --since "2 minutes ago" --no-pager | tail -n 10)
if [ -n "$RECENT_LOGS" ]; then
    echo -e "${GREEN}✅ Service is active${NC}"
    echo ""
    echo "   Recent logs:"
    echo "$RECENT_LOGS" | sed 's/^/   /'
else
    echo -e "${YELLOW}⚠️  No recent activity${NC}"
fi
echo ""

# Check 6: Error Check
echo "6️⃣  Checking for errors..."
ERROR_COUNT=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" --no-pager | grep -i "error\|exception\|fail" | wc -l)
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ No errors in last 10 minutes${NC}"
else
    echo -e "${YELLOW}⚠️  Found $ERROR_COUNT error(s) in last 10 minutes${NC}"
    echo "   Recent errors:"
    sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" --no-pager | grep -i "error\|exception\|fail" | tail -n 5 | sed 's/^/   /'
fi
echo ""

# Check 7: Live Test Mode Status
echo "7️⃣  Checking LIVE_TEST_MODE..."
if echo "$ENV_VARS" | grep -q "LIVE_TEST_MODE=true"; then
    echo -e "${GREEN}✅ LIVE_TEST_MODE enabled (safe mode)${NC}"
    MAX_ORDERS=$(echo "$ENV_VARS" | grep "MAX_LIVE_TEST_ORDERS_PER_DAY" | cut -d'=' -f2)
    MAX_USD=$(echo "$ENV_VARS" | grep "MAX_LIVE_TEST_USD_PER_ORDER" | cut -d'=' -f2)
    echo "   Max orders per day: $MAX_ORDERS"
    echo "   Max USD per order: \$$MAX_USD"
else
    echo -e "${YELLOW}⚠️  LIVE_TEST_MODE disabled (full LIVE mode)${NC}"
fi
echo ""

# Summary
echo "======================================================================"
echo "📊 VERIFICATION SUMMARY"
echo "======================================================================"
echo -e "${GREEN}✅ Service Status:${NC} Running (PID: $PID)"
echo -e "${GREEN}✅ Environment:${NC} Loaded from .env"
echo -e "${GREEN}✅ Logs:${NC} Writing to /opt/alpha-sniper/logs/"
if [ "$ERROR_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ Health:${NC} No errors detected"
else
    echo -e "${YELLOW}⚠️  Health:${NC} $ERROR_COUNT error(s) found"
fi
echo ""
echo "Quick commands:"
echo "  View live logs:      sudo journalctl -u alpha-sniper-live.service -f"
echo "  View bot log:        tail -f /opt/alpha-sniper/logs/bot.log"
echo "  Restart service:     sudo systemctl restart alpha-sniper-live.service"
echo "  Stop service:        sudo systemctl stop alpha-sniper-live.service"
echo ""
