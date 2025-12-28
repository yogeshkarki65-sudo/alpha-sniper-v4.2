#!/bin/bash
########################################
# Alpha Sniper V4.2 - Quick Deploy Script
# Regime-Based Thresholds + Telegram Fixes
########################################

set -e  # Exit on error

echo "========================================="
echo "Alpha Sniper V4.2 Deployment"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Backup current env file${NC}"
sudo cp /etc/alpha-sniper/alpha-sniper-live.env /etc/alpha-sniper/alpha-sniper-live.env.backup.$(date +%Y%m%d_%H%M%S)
echo -e "${GREEN}✓ Backup created${NC}"
echo ""

echo -e "${YELLOW}Step 2: Stop bot${NC}"
sudo systemctl stop alpha-sniper-live.service
echo -e "${GREEN}✓ Bot stopped${NC}"
echo ""

echo -e "${YELLOW}Step 3: Pull latest code${NC}"
cd /opt/alpha-sniper
sudo git fetch origin
sudo git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
sudo git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

echo -e "${YELLOW}Step 4: Verify changes${NC}"
if sudo grep -q "get_pump_thresholds" /opt/alpha-sniper/alpha-sniper/config.py; then
    echo -e "${GREEN}✓ Regime threshold code found${NC}"
else
    echo -e "${RED}✗ Regime threshold code NOT found - check deployment${NC}"
    exit 1
fi

if sudo grep -q "send_test_message" /opt/alpha-sniper/alpha-sniper/utils/telegram.py; then
    echo -e "${GREEN}✓ Telegram test message code found${NC}"
else
    echo -e "${RED}✗ Telegram test message code NOT found - check deployment${NC}"
    exit 1
fi
echo ""

echo -e "${YELLOW}Step 5: Set permissions${NC}"
sudo chown -R alpha-sniper:alpha-sniper /opt/alpha-sniper
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
echo -e "${GREEN}✓ Permissions set${NC}"
echo ""

echo -e "${RED}IMPORTANT: Replace /etc/alpha-sniper/alpha-sniper-live.env with new file NOW${NC}"
echo "Press Enter when you've replaced the env file..."
read

echo -e "${YELLOW}Step 6: Restart bot${NC}"
sudo systemctl restart alpha-sniper-live.service
echo -e "${GREEN}✓ Bot restarted${NC}"
echo ""

echo -e "${YELLOW}Step 7: Checking startup logs...${NC}"
sleep 3
echo ""
sudo journalctl -u alpha-sniper-live.service --since "10 seconds ago" --no-pager | tail -30

echo ""
echo "========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "========================================="
echo ""
echo "What to check:"
echo "1. Telegram test message (should arrive within 10s)"
echo "2. Look for: [PUMP_DEBUG] Active thresholds (regime=...)"
echo "3. Monitor for: after_core > 0 in scan summaries"
echo "4. Watch for: [TELEGRAM] ✅ messages (not ❌)"
echo ""
echo "Monitor live logs:"
echo "  sudo journalctl -u alpha-sniper-live.service -f"
echo ""
echo "Check status:"
echo "  sudo systemctl status alpha-sniper-live.service"
echo ""
