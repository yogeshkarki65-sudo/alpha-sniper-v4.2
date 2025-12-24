#!/bin/bash
# Verification script for no-trade diagnostic fixes
# Run this after deploying the fixes

set -e

echo "================================================"
echo "Alpha Sniper V4.2 - No-Trade Fixes Verification"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check if running as correct user
echo "1. Checking user..."
if [ "$USER" != "ubuntu" ]; then
    echo -e "${YELLOW}WARNING: Not running as ubuntu user (current: $USER)${NC}"
else
    echo -e "${GREEN}✓ Running as ubuntu user${NC}"
fi
echo ""

# 2. Check critical files exist
echo "2. Checking critical files..."
FILES=(
    "alpha-sniper/core/symbol_blacklist.py"
    "deployment/NO_TRADES_DIAGNOSTIC.md"
    "deployment/ENV_SETUP_GUIDE.md"
)

for file in "${FILES[@]}"; do
    if [ -f "/opt/alpha-sniper/$file" ]; then
        echo -e "${GREEN}✓ $file exists${NC}"
    else
        echo -e "${RED}✗ $file MISSING${NC}"
    fi
done
echo ""

# 3. Check /var/lib/alpha-sniper permissions
echo "3. Checking /var/lib/alpha-sniper..."
if [ -d "/var/lib/alpha-sniper" ]; then
    owner=$(stat -c '%U:%G' /var/lib/alpha-sniper)
    perms=$(stat -c '%a' /var/lib/alpha-sniper)

    if [ "$owner" = "ubuntu:ubuntu" ]; then
        echo -e "${GREEN}✓ Ownership correct: $owner${NC}"
    else
        echo -e "${RED}✗ Wrong ownership: $owner (should be ubuntu:ubuntu)${NC}"
        echo "  Fix: sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper"
    fi

    if [ "$perms" = "755" ] || [ "$perms" = "775" ] || [ "$perms" = "777" ]; then
        echo -e "${GREEN}✓ Permissions OK: $perms${NC}"
    else
        echo -e "${YELLOW}⚠ Unusual permissions: $perms${NC}"
    fi
else
    echo -e "${RED}✗ /var/lib/alpha-sniper does not exist${NC}"
    echo "  Creating..."
    sudo mkdir -p /var/lib/alpha-sniper
    sudo chown ubuntu:ubuntu /var/lib/alpha-sniper
    sudo chmod 755 /var/lib/alpha-sniper
    echo -e "${GREEN}✓ Created /var/lib/alpha-sniper${NC}"
fi
echo ""

# 4. Check service status
echo "4. Checking service status..."
if systemctl is-active --quiet alpha-sniper-live.service; then
    echo -e "${GREEN}✓ Service is running${NC}"

    # Get uptime
    uptime=$(systemctl show -p ActiveEnterTimestamp alpha-sniper-live.service --value)
    echo "  Started: $uptime"
else
    echo -e "${RED}✗ Service is NOT running${NC}"
    echo "  Start: sudo systemctl start alpha-sniper-live.service"
fi
echo ""

# 5. Check for recent logs
echo "5. Checking recent logs (last 2 minutes)..."
echo "   Looking for: [SIGNAL_REJECTED], [PLACING_ORDER], [BLACKLIST]"
echo ""

# Get logs from last 2 minutes
recent_logs=$(sudo journalctl -u alpha-sniper-live.service --since "2 minutes ago" | grep -E "SIGNAL_REJECTED|PLACING_ORDER|BLACKLIST_ADD|Mode:" || true)

if [ -n "$recent_logs" ]; then
    echo "$recent_logs" | head -20
else
    echo -e "${YELLOW}⚠ No recent logs found (service might need restart)${NC}"
fi
echo ""

# 6. Check blacklist file
echo "6. Checking blacklist file..."
blacklist_file="/var/lib/alpha-sniper/symbol_blacklist.json"
if [ -f "$blacklist_file" ]; then
    count=$(jq '.blacklist | length' "$blacklist_file" 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ Blacklist file exists${NC}"
    echo "  Blacklisted symbols: $count"

    if [ "$count" -gt 0 ]; then
        echo "  Symbols:"
        jq -r '.blacklist | keys[]' "$blacklist_file" 2>/dev/null || echo "  (unable to parse)"
    fi
else
    echo -e "${YELLOW}⚠ Blacklist file doesn't exist yet (will be created on first BadSymbol error)${NC}"
fi
echo ""

# 7. Check environment configuration
echo "7. Checking environment configuration..."
env_file="/etc/alpha-sniper/alpha-sniper-live.env"
if [ -f "$env_file" ]; then
    echo -e "${GREEN}✓ Environment file exists${NC}"

    # Check critical variables
    sim_mode=$(grep "^SIM_MODE=" "$env_file" | cut -d= -f2 || echo "")
    mexc_key=$(grep "^MEXC_API_KEY=" "$env_file" | cut -d= -f2 || echo "")
    telegram_token=$(grep "^TELEGRAM_BOT_TOKEN=" "$env_file" | cut -d= -f2 || echo "")

    if [ "$sim_mode" = "false" ]; then
        echo -e "${GREEN}  ✓ SIM_MODE=false (LIVE mode)${NC}"
    else
        echo -e "${YELLOW}  ⚠ SIM_MODE=$sim_mode (not LIVE)${NC}"
    fi

    if [ -n "$mexc_key" ] && [ "$mexc_key" != "your_mexc_api_key_here" ]; then
        echo -e "${GREEN}  ✓ MEXC_API_KEY is set${NC}"
    else
        echo -e "${RED}  ✗ MEXC_API_KEY not configured${NC}"
    fi

    if [ -n "$telegram_token" ] && [ "$telegram_token" != "your_telegram_bot_token_here" ]; then
        echo -e "${GREEN}  ✓ TELEGRAM_BOT_TOKEN is set${NC}"
    else
        echo -e "${RED}  ✗ TELEGRAM_BOT_TOKEN not configured${NC}"
    fi
else
    echo -e "${RED}✗ Environment file missing: $env_file${NC}"
fi
echo ""

# 8. Summary
echo "================================================"
echo "SUMMARY"
echo "================================================"
echo ""
echo "If service is running and logs show new format ([SIGNAL_REJECTED], etc.),"
echo "then fixes are working correctly."
echo ""
echo -e "${YELLOW}IMPORTANT:${NC}"
echo "- Check logs for WHY signals are being rejected"
echo "- With \$58 account, expect 'position_too_small' rejections"
echo "- MEXC requires \$5 minimum notional - may be impossible with tiny account"
echo ""
echo "Next steps:"
echo "1. Monitor logs: sudo journalctl -u alpha-sniper-live.service -f"
echo "2. Look for [SIGNAL_REJECTED] to see why no trades"
echo "3. Consider increasing account size to \$200+ for LIVE trading"
echo "4. Or stay in SIM_MODE=true until account grows"
echo ""
