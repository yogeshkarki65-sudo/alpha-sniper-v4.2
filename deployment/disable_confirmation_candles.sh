#!/bin/bash
# ============================================================================
# Disable Confirmation Candles (Quick Test)
# ============================================================================

set -e

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="${ENV_FILE}.backup.no_conf.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Disabling Confirmation Candles..."
echo ""

# Backup first
sudo cp "$ENV_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"
echo ""

# Function to add or update env variable
add_or_update() {
    local key="$1"
    local value="$2"

    if sudo grep -q "^${key}=" "$ENV_FILE"; then
        # Update existing
        sudo sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        echo "✅ Updated: $key=$value"
    else
        # Add new
        echo "${key}=${value}" | sudo tee -a "$ENV_FILE" > /dev/null
        echo "✅ Added: $key=$value"
    fi
}

# Disable confirmation candles
add_or_update "PUMP_CONFIRMATION_CANDLES" "0"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CONFIRMATION CANDLES DISABLED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This is a quick test to see if trades start opening."
echo ""
echo "Next: Restart service to apply changes"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
echo "Then monitor for trades:"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -E 'Opening position|PUMP.*signal'"
echo ""
