#!/bin/bash
################################################################################
# Alpha Sniper V4.2.2 - Deploy Enhancements
#
# Deploys:
# 1. Liquidity rejection improvements
# 2. Fresh impulse pump detection
# 3. CORE rejection observability
################################################################################

set -e

echo "================================================================================"
echo "🚀 Alpha Sniper V4.2.2 - Deploying Enhancements"
echo "================================================================================"
echo ""

# Configuration
SOURCE_DIR="/home/user/alpha-sniper-v4.2"
INSTALL_DIR="/opt/alpha-sniper"
ENV_FILE="$INSTALL_DIR/alpha-sniper/.env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Step 1: Create installation directory structure
echo -e "${BLUE}1️⃣  Setting up installation directory...${NC}"
mkdir -p "$INSTALL_DIR/alpha-sniper/signals"
mkdir -p "$INSTALL_DIR/tools"
mkdir -p "$INSTALL_DIR/logs"
echo -e "${GREEN}   ✅ Directory structure created${NC}"
echo ""

# Step 2: Backup existing .env if it exists
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

# Step 3: Copy Python files with v4.2.2 changes
echo -e "${BLUE}3️⃣  Deploying v4.2.2 code...${NC}"
cp "$SOURCE_DIR/alpha-sniper/config.py" "$INSTALL_DIR/alpha-sniper/"
cp "$SOURCE_DIR/alpha-sniper/risk_engine.py" "$INSTALL_DIR/alpha-sniper/"
cp "$SOURCE_DIR/alpha-sniper/signals/pump_engine.py" "$INSTALL_DIR/alpha-sniper/signals/"
cp "$SOURCE_DIR/tools/auto_env_optimizer.py" "$INSTALL_DIR/tools/" 2>/dev/null || true
echo -e "${GREEN}   ✅ Code files deployed${NC}"
echo ""

# Step 4: Verify v4.2.2 markers in deployed files
echo -e "${BLUE}4️⃣  Verifying v4.2.2 changes...${NC}"
if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/config.py"; then
    echo -e "${GREEN}   ✅ config.py - Liquidity params${NC}"
else
    echo -e "${RED}   ❌ config.py - Missing v4.2.2${NC}"
fi

if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/risk_engine.py"; then
    echo -e "${GREEN}   ✅ risk_engine.py - CORE rejection logging${NC}"
else
    echo -e "${RED}   ❌ risk_engine.py - Missing v4.2.2${NC}"
fi

if grep -q "v4.2.2" "$INSTALL_DIR/alpha-sniper/signals/pump_engine.py"; then
    echo -e "${GREEN}   ✅ pump_engine.py - Fresh impulse detection${NC}"
else
    echo -e "${RED}   ❌ pump_engine.py - Missing v4.2.2${NC}"
fi
echo ""

# Step 5: Create/update .env with v4.2.2 parameters
echo -e "${BLUE}5️⃣  Configuring .env parameters...${NC}"

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

# Step 6: Show configured parameters
echo -e "${BLUE}6️⃣  v4.2.2 Parameters:${NC}"
echo "================================================================================"
grep "MIN_LIQ_FACTOR\|MIN_ADJUSTED_USD\|PUMP_SPIKE_MULT\|PUMP_SPIKE_LOOKBACK\|PUMP_MAX_24H_EXTENDED" "$ENV_FILE" || echo "   (Not found - check manual config needed)"
echo "================================================================================"
echo ""

# Step 7: Show deployment summary
echo -e "${BLUE}7️⃣  Deployment locations:${NC}"
echo "   Code:    $INSTALL_DIR/alpha-sniper/"
echo "   Config:  $ENV_FILE"
echo "   Logs:    $INSTALL_DIR/logs/"
echo "   Backup:  $BACKUP_DIR"
echo ""

# Final summary
echo "================================================================================"
echo -e "${GREEN}✅ v4.2.2 DEPLOYMENT COMPLETE!${NC}"
echo "================================================================================"
echo ""
echo -e "${BLUE}📊 What's deployed:${NC}"
echo "   1. ✅ Liquidity rejection (MIN_LIQ_FACTOR=0.4, MIN_ADJUSTED_USD=5.0)"
echo "   2. ✅ Fresh impulse detection (PUMP_SPIKE_MULT=2.0, PUMP_MAX_24H_EXTENDED=12.0)"
echo "   3. ✅ CORE rejection logging (7 rejection types)"
echo ""
echo -e "${BLUE}🔄 Next steps:${NC}"
echo "   1. Review .env: cat $ENV_FILE"
echo "   2. Restart bot: sudo systemctl restart alpha-sniper-live.service"
echo ""
echo -e "${BLUE}🔍 Monitor after restart:${NC}"
echo "   tail -f $INSTALL_DIR/logs/bot.log | grep CORE_REJECT"
echo "   tail -f $INSTALL_DIR/logs/bot.log | grep LiquidityGuard"
echo ""
echo -e "${BLUE}🛠️  Rollback:${NC}"
echo "   cp $BACKUP_DIR/env.backup $ENV_FILE"
echo ""
echo -e "${GREEN}🎯 v4.2.2 is ready! Restart bot to activate.${NC}"
echo "================================================================================"
