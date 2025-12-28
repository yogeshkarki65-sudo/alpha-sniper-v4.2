#!/bin/bash
################################################################################
# Alpha Sniper V4.2 - Auto ENV Optimizer Deployment Script
#
# This script will:
# 1. Stop the bot
# 2. Pull latest code from GitHub
# 3. Run optimizer in dry-run mode
# 4. Show proposed changes
# 5. Apply changes and restart bot
# 6. Set up crontab for automatic optimization every 6 hours
#
# Usage:
#   Copy this entire script and paste it into your server terminal
#   OR save as deploy_optimizer.sh and run: bash deploy_optimizer.sh
################################################################################

set -e  # Exit on any error

echo "================================================================================"
echo "🚀 Alpha Sniper V4.2 - Auto ENV Optimizer Deployment"
echo "================================================================================"
echo ""

# Configuration
INSTALL_DIR="/opt/alpha-sniper"
LOG_FILE="$INSTALL_DIR/logs/bot.log"
ENV_FILE="$INSTALL_DIR/alpha-sniper/.env"
DB_FILE="/var/lib/alpha-sniper/alpha_sniper.db"
OPTIMIZER_SCRIPT="$INSTALL_DIR/tools/auto_env_optimizer.py"
VENV_PYTHON="$INSTALL_DIR/venv/bin/python"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Stop the bot
echo -e "${BLUE}1️⃣  Stopping bot...${NC}"
sudo systemctl stop alpha-sniper-live.service
echo -e "${GREEN}   ✅ Bot stopped${NC}"
echo ""

# Step 2: Backup current state
echo -e "${BLUE}2️⃣  Creating backup...${NC}"
BACKUP_DIR="$HOME/backups/optimizer_deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "$ENV_FILE" "$BACKUP_DIR/env.backup" 2>/dev/null || true
cp "$DB_FILE" "$BACKUP_DIR/db.backup" 2>/dev/null || true
echo -e "${GREEN}   ✅ Backup saved to: $BACKUP_DIR${NC}"
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
git log --oneline -3
echo ""

# Step 5: Verify optimizer script exists
echo -e "${BLUE}5️⃣  Verifying optimizer script...${NC}"
if [ ! -f "$OPTIMIZER_SCRIPT" ]; then
    echo -e "${RED}   ❌ Optimizer script not found: $OPTIMIZER_SCRIPT${NC}"
    echo -e "${YELLOW}   Restarting bot and exiting...${NC}"
    sudo systemctl start alpha-sniper-live.service
    exit 1
fi
chmod +x "$OPTIMIZER_SCRIPT"
echo -e "${GREEN}   ✅ Optimizer script found${NC}"
echo ""

# Step 6: Run DRY RUN first
echo -e "${BLUE}6️⃣  Running optimizer in DRY-RUN mode...${NC}"
echo "================================================================================"
$VENV_PYTHON "$OPTIMIZER_SCRIPT" \
    --log "$LOG_FILE" \
    --env "$ENV_FILE" \
    --db "$DB_FILE" \
    --dry-run
echo "================================================================================"
echo ""

# Step 7: Ask for confirmation
echo -e "${YELLOW}⚠️  Review the proposed changes above.${NC}"
echo -e "${YELLOW}   Do you want to APPLY these changes and restart the bot?${NC}"
echo ""
read -p "   Type 'yes' to continue, anything else to cancel: " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}   ❌ Deployment cancelled by user${NC}"
    echo -e "${BLUE}   Restarting bot with current settings...${NC}"
    sudo systemctl start alpha-sniper-live.service
    sudo systemctl status alpha-sniper-live.service --no-pager | head -15
    echo ""
    echo -e "${GREEN}   ✅ Bot restarted with original settings${NC}"
    exit 0
fi

echo ""

# Step 8: Apply changes
echo -e "${BLUE}7️⃣  Applying optimizer changes...${NC}"
echo "================================================================================"
$VENV_PYTHON "$OPTIMIZER_SCRIPT" \
    --log "$LOG_FILE" \
    --env "$ENV_FILE" \
    --db "$DB_FILE" \
    --apply \
    --restart-cmd "sudo systemctl restart alpha-sniper-live.service"
echo "================================================================================"
echo ""

# Step 9: Verify bot is running
echo -e "${BLUE}8️⃣  Verifying bot status...${NC}"
sleep 3
sudo systemctl status alpha-sniper-live.service --no-pager | head -15
echo ""

# Step 10: Show recent logs
echo -e "${BLUE}9️⃣  Recent bot logs:${NC}"
echo "================================================================================"
tail -30 "$LOG_FILE"
echo "================================================================================"
echo ""

# Step 11: Set up crontab
echo -e "${BLUE}🔟 Setting up crontab for automatic optimization...${NC}"

# Create cron job command
CRON_CMD="0 */6 * * * cd $INSTALL_DIR && $VENV_PYTHON $OPTIMIZER_SCRIPT --log $LOG_FILE --env $ENV_FILE --db $DB_FILE --apply --restart-cmd \"sudo systemctl restart alpha-sniper-live\" >> /var/log/alpha-sniper-optimizer.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "auto_env_optimizer.py"; then
    echo -e "${YELLOW}   ⚠️  Cron job already exists. Skipping...${NC}"
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo -e "${GREEN}   ✅ Cron job added: Run every 6 hours${NC}"
fi

# Show current crontab
echo ""
echo -e "${BLUE}   Current crontab:${NC}"
crontab -l | grep -E "auto_env_optimizer|alpha-sniper" || echo "   (no alpha-sniper cron jobs)"
echo ""

# Step 12: Show tune history
echo -e "${BLUE}1️⃣1️⃣  Tune history:${NC}"
if [ -f "/opt/alpha-sniper/tune_history.json" ]; then
    cat "/opt/alpha-sniper/tune_history.json" | head -50
else
    echo -e "${YELLOW}   No tune history yet (will be created on first run)${NC}"
fi
echo ""

# Final summary
echo "================================================================================"
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo "================================================================================"
echo ""
echo -e "${BLUE}📊 What's running:${NC}"
echo "   • Bot: alpha-sniper-live.service (ACTIVE)"
echo "   • Optimizer: Runs every 6 hours via cron"
echo "   • Optimizer log: /var/log/alpha-sniper-optimizer.log"
echo ""
echo -e "${BLUE}🔍 Monitor commands:${NC}"
echo "   • Bot logs:       tail -f $LOG_FILE"
echo "   • Bot status:     sudo systemctl status alpha-sniper-live.service"
echo "   • Optimizer log:  tail -f /var/log/alpha-sniper-optimizer.log"
echo "   • Tune history:   cat /opt/alpha-sniper/tune_history.json"
echo ""
echo -e "${BLUE}🛠️  Manual optimizer commands:${NC}"
echo "   • Dry run:  $VENV_PYTHON $OPTIMIZER_SCRIPT --log $LOG_FILE --env $ENV_FILE --dry-run"
echo "   • Apply:    $VENV_PYTHON $OPTIMIZER_SCRIPT --log $LOG_FILE --env $ENV_FILE --apply --restart-cmd 'sudo systemctl restart alpha-sniper-live'"
echo ""
echo -e "${BLUE}⏰ Next automatic optimization:${NC}"
NEXT_RUN=$(date -d "$(date +%Y-%m-%d) $(( ($(date +%H) / 6 + 1) * 6 )):00:00" "+%Y-%m-%d %H:%M")
echo "   $NEXT_RUN"
echo ""
echo -e "${GREEN}🎯 The optimizer will now automatically tune your bot every 6 hours!${NC}"
echo "================================================================================"
