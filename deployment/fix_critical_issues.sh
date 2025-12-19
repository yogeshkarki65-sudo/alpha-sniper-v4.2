#!/bin/bash
# ============================================================================
# Critical Issue Fix Script
# ============================================================================
# Fixes: Missing telegram module, env file inline comments, service restart

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 FIXING CRITICAL ISSUES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ============================================================================
# 1. Install Missing Python Telegram Module
# ============================================================================
echo "1️⃣  Installing missing Python telegram module..."
cd /opt/alpha-sniper
source venv/bin/activate

pip install python-telegram-bot --quiet
if [ $? -eq 0 ]; then
    echo "✅ Telegram module installed successfully"
else
    echo "❌ Failed to install telegram module"
    exit 1
fi

# Verify import works
python -c "import telegram; print('✅ Telegram module import verified')"

deactivate
echo ""

# ============================================================================
# 2. Fix Env File Inline Comments
# ============================================================================
echo "2️⃣  Fixing env file inline comments..."

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Env file not found: $ENV_FILE"
    exit 1
fi

# Create backup
sudo cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "✅ Backup created: ${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

# Remove inline comments (everything after # on each line)
sudo sed -i 's/#.*$//' "$ENV_FILE"

# Remove trailing whitespace
sudo sed -i 's/[[:space:]]*$//' "$ENV_FILE"

# Show critical settings after fix
echo ""
echo "Fixed critical settings:"
grep -E "^(PUMP_ONLY|MAX_HOLD_HOURS_PUMP|MIN_SCORE_PUMP|TELEGRAM_SCAN_SUMMARY|TELEGRAM_TRADE_ALERTS|TELEGRAM_WHY_NO_TRADE)=" "$ENV_FILE" | head -6
echo ""

# ============================================================================
# 3. Clear Old Positions (Using Old 3h Max Hold)
# ============================================================================
echo "3️⃣  Clearing old positions (using old 3h max hold)..."

POSITIONS_FILE="/var/lib/alpha-sniper/positions.json"
if [ -f "$POSITIONS_FILE" ]; then
    OLD_COUNT=$(cat "$POSITIONS_FILE" | grep -c '"max_hold_hours": 3' || echo "0")
    if [ "$OLD_COUNT" -gt 0 ]; then
        sudo cp "$POSITIONS_FILE" "${POSITIONS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "[]" | sudo tee "$POSITIONS_FILE" > /dev/null
        echo "✅ Cleared $OLD_COUNT old position(s)"
    else
        echo "✅ No old positions to clear"
    fi
else
    echo "✅ No positions file found (will be created on first trade)"
fi
echo ""

# ============================================================================
# 4. Restart Service
# ============================================================================
echo "4️⃣  Restarting alpha-sniper service..."

sudo systemctl restart alpha-sniper-live.service

# Wait for service to stabilize
sleep 3

SERVICE_STATUS=$(sudo systemctl is-active alpha-sniper-live.service 2>/dev/null || echo "inactive")
if [ "$SERVICE_STATUS" == "active" ]; then
    echo "✅ Service restarted successfully"
else
    echo "❌ Service failed to start (status: $SERVICE_STATUS)"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u alpha-sniper-live.service --since "30 seconds ago" --no-pager | tail -20
    exit 1
fi
echo ""

# ============================================================================
# 5. Verify Bot is Scanning
# ============================================================================
echo "5️⃣  Verifying bot activity (waiting 30 seconds for scans)..."
sleep 30

RECENT_SCANS=$(sudo journalctl -u alpha-sniper-live.service --since "45 seconds ago" --no-pager | grep -c "Scan cycle starting" || echo "0")

if [ "$RECENT_SCANS" -gt 0 ]; then
    echo "✅ Bot is scanning ($RECENT_SCANS scan(s) detected)"
else
    echo "⚠️  No scans detected yet (may need more time)"
    echo ""
    echo "Recent logs:"
    sudo journalctl -u alpha-sniper-live.service --since "45 seconds ago" --no-pager | tail -15
fi
echo ""

# ============================================================================
# FINAL STATUS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CRITICAL FIXES APPLIED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Wait 2-3 minutes for bot to complete first scan cycle"
echo "  2. Run verification script again:"
echo "     sudo /opt/alpha-sniper/deployment/verify_all.sh"
echo ""
echo "  3. Monitor Telegram for scan summaries"
echo "  4. Check for pump signals meeting 0.75 threshold"
echo ""
echo "If issues persist, check logs:"
echo "  sudo journalctl -u alpha-sniper-live.service -f"
echo ""
