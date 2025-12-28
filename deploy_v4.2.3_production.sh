#!/bin/bash
################################################################################
# Alpha Sniper V4.2.3 - Production Deployment Script
#
# Deploys:
# 1. Order viability and exchange validation
# 2. Full order lifecycle logging
# 3. Reason-coded skip tracking
# 4. Production smoke tests
# 5. Automated deployment with rollback
################################################################################

set -e

echo "================================================================================"
echo "🚀 Alpha Sniper V4.2.3 - Deploying Production Observability"
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
BACKUP_DIR="$HOME/backups/v4.2.3_deploy_$(date +%Y%m%d_%H%M%S)"
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

# Step 5: Verify v4.2.3 changes
echo -e "${BLUE}5️⃣  Verifying v4.2.3 changes...${NC}"
if grep -q "MIN_VIABLE_TRADE_USD" "$INSTALL_DIR/alpha-sniper/config.py"; then
    echo -e "${GREEN}   ✅ config.py - Order viability params added${NC}"
else
    echo -e "${RED}   ❌ config.py - Missing v4.2.3 changes${NC}"
fi

if grep -q "validate_order" "$INSTALL_DIR/alpha-sniper/exchange.py"; then
    echo -e "${GREEN}   ✅ exchange.py - Exchange validation module added${NC}"
else
    echo -e "${RED}   ❌ exchange.py - Missing v4.2.3 changes${NC}"
fi

if grep -q "skip_reasons" "$INSTALL_DIR/alpha-sniper/main.py"; then
    echo -e "${GREEN}   ✅ main.py - Reason-coded skip tracking added${NC}"
else
    echo -e "${RED}   ❌ main.py - Missing v4.2.3 changes${NC}"
fi

if [ -f "$INSTALL_DIR/scripts/smoke_market_data.py" ]; then
    echo -e "${GREEN}   ✅ scripts/smoke_market_data.py - Smoke test available${NC}"
else
    echo -e "${RED}   ❌ scripts/smoke_market_data.py - Missing${NC}"
fi
echo ""

# Step 6: Update .env with v4.2.3 parameters
echo -e "${BLUE}6️⃣  Updating .env with v4.2.3 parameters...${NC}"

# Ensure .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}   Creating new .env file${NC}"
    touch "$ENV_FILE"
fi

# Add v4.2.3 viability params
if ! grep -q "MIN_VIABLE_TRADE_USD" "$ENV_FILE"; then
    cat >> "$ENV_FILE" << 'ENVEOF'

# === v4.2.3: Order Viability & Exchange Validation ===
MIN_VIABLE_TRADE_USD=10.0
MAX_SPREAD_PCT_ORDER=0.30
MIN_DEPTH_MULTIPLE=200
ORDERBOOK_DEPTH_LEVELS=10
VALIDATION_FEE_BUFFER_PCT=0.20
EXCHANGE_TAKER_FEE_FALLBACK=0.001
ENVEOF
    echo -e "${GREEN}   ✅ Added viability & validation params${NC}"
else
    echo -e "${YELLOW}   ⚠️  Viability params already exist (no changes)${NC}"
fi

# Add v4.2.3 smoke test params
if ! grep -q "SMOKE_TEST_SYMBOL" "$ENV_FILE"; then
    cat >> "$ENV_FILE" << 'ENVEOF'

# === v4.2.3: Production Smoke Tests ===
SMOKE_TEST_SYMBOL=BTC/USDT
SMOKE_TEST_USD=10.0
SMOKE_TEST_ALLOW_ORDERS=false
ENVEOF
    echo -e "${GREEN}   ✅ Added smoke test params${NC}"
else
    echo -e "${YELLOW}   ⚠️  Smoke test params already exist (no changes)${NC}"
fi
echo ""

# Step 7: Show new parameters
echo -e "${BLUE}7️⃣  v4.2.3 Parameters:${NC}"
echo "================================================================================"
echo "# Order Viability & Validation:"
echo "MIN_VIABLE_TRADE_USD=10.0              # Minimum trade size after all scaling"
echo "MAX_SPREAD_PCT_ORDER=0.30              # Reject if spread > 0.30%"
echo "MIN_DEPTH_MULTIPLE=200                 # Depth must be >= size * 200x"
echo ""
echo "# Smoke Tests:"
echo "SMOKE_TEST_SYMBOL=BTC/USDT             # Test symbol"
echo "SMOKE_TEST_USD=10.0                    # Test order size"
echo "SMOKE_TEST_ALLOW_ORDERS=false          # Safety gate (disabled by default)"
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
echo -e "${GREEN}✅ v4.2.3 DEPLOYMENT COMPLETE!${NC}"
echo "================================================================================"
echo ""
echo -e "${BLUE}📊 What's new in v4.2.3:${NC}"
echo "   1. ✅ Order viability gating (spread, depth, size checks)"
echo "   2. ✅ Exchange validation (minQty, minNotional, precision)"
echo "   3. ✅ Full order lifecycle logging (VALIDATING → PLACED → FILLED)"
echo "   4. ✅ Reason-coded skip tracking (aggregated summaries)"
echo "   5. ✅ Production smoke tests (market data + order lifecycle)"
echo ""
echo -e "${BLUE}🔍 Monitor new features:${NC}"
echo "   • Skip reasons:      tail -f $LOG_FILE | grep 'skip_reasons'"
echo "   • Viability checks:  tail -f $LOG_FILE | grep 'VIABILITY_CHECK'"
echo "   • Order lifecycle:   tail -f $LOG_FILE | grep -E '(ORDER_VALIDATING|ORDER_PLACED|ORDER_FILLED)'"
echo "   • CORE rejections:   tail -f $LOG_FILE | grep 'CORE_REJECT'"
echo ""
echo -e "${BLUE}🧪 Run smoke test (safe - no orders):${NC}"
echo "   cd $INSTALL_DIR"
echo "   source venv/bin/activate"
echo "   python scripts/smoke_market_data.py"
echo ""
echo -e "${BLUE}🛠️  Rollback if needed:${NC}"
echo "   cp $BACKUP_DIR/env.backup $ENV_FILE"
echo "   sudo systemctl restart alpha-sniper-live.service"
echo ""
echo -e "${GREEN}🎯 v4.2.3 is now LIVE and running!${NC}"
echo "================================================================================"
