#!/bin/bash
# Deployment script for auto-adjustment features
# Usage: bash deploy_auto_adjust.sh

set -e

echo "=========================================="
echo "  Deploying Auto-Adjustment Features"
echo "=========================================="
echo ""

cd /opt/alpha-sniper/alpha-sniper

# 1. Stop the service
echo "[1/5] Stopping service..."
sudo systemctl stop alpha-sniper-async.service
echo "  ✓ Service stopped"

# 2. Pull latest changes
echo ""
echo "[2/5] Pulling latest changes..."
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
echo "  ✓ Code updated"

# 3. Show what changed
echo ""
echo "[3/5] Latest changes:"
git log --oneline -1
echo ""

# 4. Verify database exists
echo "[4/5] Verifying database..."
if [ -f "/opt/alpha-sniper/data/alpha_async.db" ]; then
    echo "  ✓ Database found: /opt/alpha-sniper/data/alpha_async.db"
    TRADE_COUNT=$(sqlite3 /opt/alpha-sniper/data/alpha_async.db "SELECT COUNT(*) FROM trades;" 2>/dev/null || echo "0")
    echo "  ✓ Total trades in database: $TRADE_COUNT"
else
    echo "  ⚠️  Warning: Database not found, will be created on first run"
fi

# 5. Start the service
echo ""
echo "[5/5] Starting service..."
sudo systemctl start alpha-sniper-async.service
sleep 3

# Check status
if sudo systemctl is-active --quiet alpha-sniper-async.service; then
    echo "  ✓ Service started successfully"
else
    echo "  ❌ Service failed to start!"
    echo ""
    echo "Check logs:"
    echo "  sudo journalctl -u alpha-sniper-async.service -n 50"
    exit 1
fi

echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "New Features Activated:"
echo "  ✓ Auto-tighten if win rate < 40% after 100+ trades"
echo "  ✓ Auto-loosen if no trades for 6+ hours"
echo ""
echo "Monitor logs for adjustments:"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep -E 'WINRATE_ADJUST|QUIET_MARKET'"
echo ""
echo "Check bot health:"
echo "  bash check_bot_health.sh"
echo ""
