#!/bin/bash
# ============================================================================
# Fix No Trades Issue - Automated Diagnostics & Fix
# ============================================================================

set -e

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="${ENV_FILE}.backup.fix_trades.$(date +%Y%m%d_%H%M%S)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        FIX NO TRADES ISSUE - AUTOMATED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This script will:"
echo "  1. Enable debug logging to see rejection reasons"
echo "  2. Optionally disable confirmation candles (quick test)"
echo "  3. Restart the service"
echo "  4. Run health verification"
echo "  5. Monitor logs for results"
echo ""

# Prompt for approach
echo "Choose approach:"
echo "  1) Enable debug only (keep confirmation candles, diagnose first)"
echo "  2) Enable debug + disable confirmation candles (quick test)"
echo ""
read -p "Enter choice [1 or 2]: " choice

# Backup
sudo cp "$ENV_FILE" "$BACKUP_FILE"
echo ""
echo "✅ Backup created: $BACKUP_FILE"
echo ""

# Function to add or update env variable
add_or_update() {
    local key="$1"
    local value="$2"

    if sudo grep -q "^${key}=" "$ENV_FILE"; then
        sudo sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        echo "✅ Updated: $key=$value"
    else
        echo "${key}=${value}" | sudo tee -a "$ENV_FILE" > /dev/null
        echo "✅ Added: $key=$value"
    fi
}

# Always enable debug
echo "📝 Enabling debug logging..."
add_or_update "PUMP_DEBUG_LOGGING" "true"

# Optionally disable confirmation candles
if [[ "$choice" == "2" ]]; then
    echo "📝 Disabling confirmation candles..."
    add_or_update "PUMP_CONFIRMATION_CANDLES" "0"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CONFIGURATION UPDATED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Restart service
echo "🔄 Restarting service..."
sudo systemctl restart alpha-sniper-live.service
echo "✅ Service restarted"
echo ""

# Wait for service to stabilize
echo "⏳ Waiting 10 seconds for service to stabilize..."
sleep 10

# Run health check
echo ""
echo "🏥 Running health verification..."
echo ""
sudo ./deployment/verify_all.sh

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next: Monitor logs for 15-30 minutes to see results"
echo ""
echo "To see rejection reasons (if choice 1):"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -E 'REJECTION|CONFIRMATION'"
echo ""
echo "To see if trades are opening (if choice 2):"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -E 'Opening position|signal generated'"
echo ""
echo "To rollback if needed:"
echo "  sudo cp $BACKUP_FILE $ENV_FILE"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
