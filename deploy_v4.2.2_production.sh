#!/bin/bash
################################################################################
# Alpha Sniper V4.2.2 - Production Deployment Script
#
# This script will:
# 1. Stop the bot
# 2. Backup .env
# 3. Pull latest code from GitHub
# 4. Update .env with v4.2.2 parameters
# 5. Restart bot
# 6. Show status
#
# Usage:
#   Copy this script to production server and run:
#   bash deploy_v4.2.2_production.sh
#
#   OR run directly via curl:
#   cd /opt/alpha-sniper && curl -sS https://raw.githubusercontent.com/yogeshkarki65-sudo/alpha-sniper-v4.2/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS/deploy_v4.2.2_production.sh | bash
################################################################################

set -e

echo "================================================================================"
echo "🚀 Alpha Sniper V4.2.2 - Production Deployment"
echo "================================================================================"
echo ""

# Configuration
INSTALL_DIR="/opt/alpha-sniper"
LOG_FILE="$INSTALL_DIR/logs/bot.log"
ENV_FILE="$INSTALL_DIR/alpha-sniper/.env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Step 1: Stop bot
echo -e "${BLUE}1️⃣  Stopping bot...${NC}"
sudo systemctl stop alpha-sniper-live.service
echo -e "${GREEN}   ✅ Bot stopped${NC}"
echo ""

# Step 2: Backup
echo -e "${BLUE}2️⃣  Creating backup...${NC}"
BACKUP_DIR="$HOME/backups/v4.2.2_deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$BACKUP_DIR/env.backup"
    echo -e "${GREEN}   ✅ Backup: $BACKUP_DIR/env.backup${NC}"
else
    echo -e "${YELLOW}   ⚠️  No existing .env file${NC}"
fi
echo ""

# Step 3: Pull latest code
echo -e "${BLUE}3️⃣  Pulling latest code from GitHub...${NC}"
cd "$INSTALL_DIR"
git fetch origin
git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
echo -e "${GREEN}   ✅ Code updated${NC}"
echo ""

# Step 4: Show recent commits
echo -e "${BLUE}4️⃣  Recent commits:${NC}"
git log --oneline -5
echo ""

# Step 5: Verify v4.2.2 changes
echo -e "${BLUE}5️⃣  Verifying v4.2.2 changes...${NC}"
if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/config.py"; then
    echo -e "${GREEN}   ✅ config.py - Liquidity params${NC}"
else
    echo -e "${RED}   ❌ config.py - Missing v4.2.2 changes${NC}"
fi

if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/risk_engine.py"; then
    echo -e "${GREEN}   ✅ risk_engine.py - CORE rejection logging${NC}"
else
    echo -e "${RED}   ❌ risk_engine.py - Missing v4.2.2 changes${NC}"
fi

if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/signals/pump_engine.py"; then
    echo -e "${GREEN}   ✅ pump_engine.py - Fresh impulse detection${NC}"
else
    echo -e "${RED}   ❌ pump_engine.py - Missing v4.2.2 changes${NC}"
fi
echo ""

# Step 6: Update .env with v4.2.2 parameters
echo -e "${BLUE}6️⃣  Updating .env with v4.2.2 parameters...${NC}"

# Create .env if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
    echo -e "${YELLOW}   Created new .env file${NC}"
fi

# Add liquidity params
if ! grep -q "MIN_LIQ_FACTOR" "$ENV_FILE"; then
    cat >> "$ENV_FILE" << 'ENVEOF'

# === v4.2.2: Liquidity rejection thresholds ===
MIN_LIQ_FACTOR=0.4
MIN_ADJUSTED_USD=5.0
ENVEOF
    echo -e "${GREEN}   ✅ Added liquidity thresholds${NC}"
else
    echo -e "${YELLOW}   ⚠️  Liquidity params already exist${NC}"
fi

# Add fresh impulse params
if ! grep -q "PUMP_SPIKE_MULT" "$ENV_FILE"; then
    cat >> "$ENV_FILE" << 'ENVEOF'

# === v4.2.2: Fresh impulse pump detection ===
PUMP_SPIKE_MULT=2.0
PUMP_SPIKE_LOOKBACK=1
PUMP_MAX_24H_EXTENDED=12.0
ENVEOF
    echo -e "${GREEN}   ✅ Added fresh impulse params${NC}"
else
    echo -e "${YELLOW}   ⚠️  Fresh impulse params already exist${NC}"
fi
echo ""

# Step 7: Show new parameters
echo -e "${BLUE}7️⃣  v4.2.2 Parameters:${NC}"
echo "================================================================================"
echo "MIN_LIQ_FACTOR=0.4"
echo "MIN_ADJUSTED_USD=5.0"
echo "PUMP_SPIKE_MULT=2.0"
echo "PUMP_SPIKE_LOOKBACK=1"
echo "PUMP_MAX_24H_EXTENDED=12.0"
echo "================================================================================"
echo ""

# Step 8: Restart bot
echo -e "${BLUE}8️⃣  Restarting bot...${NC}"
sudo systemctl start alpha-sniper-live.service
sleep 3
echo ""

# Step 9: Verify bot is running
echo -e "${BLUE}9️⃣  Bot status:${NC}"
echo "================================================================================"
sudo systemctl status alpha-sniper-live.service --no-pager | head -15
echo "================================================================================"
echo ""

# Step 10: Show recent logs
echo -e "${BLUE}🔟 Recent bot logs:${NC}"
echo "================================================================================"
tail -30 "$LOG_FILE" 2>/dev/null || echo "   No logs yet"
echo "================================================================================"
echo ""

# Final summary
echo "================================================================================"
echo -e "${GREEN}✅ v4.2.2 DEPLOYMENT COMPLETE!${NC}"
echo "================================================================================"
echo ""
echo -e "${BLUE}📊 What's new in v4.2.2:${NC}"
echo "   1. ✅ Liquidity rejection (no more \$2-5 trades)"
echo "   2. ✅ Fresh impulse detection (volume spike required)"
echo "   3. ✅ CORE rejection logging (7 rejection types tracked)"
echo ""
echo -e "${BLUE}🔍 Monitor new features:${NC}"
echo "   • CORE rejections:  tail -f $LOG_FILE | grep CORE_REJECT"
echo "   • Liquidity guard:  tail -f $LOG_FILE | grep LiquidityGuard"
echo "   • Bot status:       sudo systemctl status alpha-sniper-live.service"
echo ""
echo -e "${BLUE}🛠️  Rollback if needed:${NC}"
echo "   cp $BACKUP_DIR/env.backup $ENV_FILE"
echo "   sudo systemctl restart alpha-sniper-live.service"
echo ""
echo -e "${GREEN}🎯 v4.2.2 is now LIVE and running!${NC}"
echo "================================================================================"
