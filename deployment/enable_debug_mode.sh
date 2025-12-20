#!/bin/bash
# ============================================================================
# Enable Debug Mode for Alpha Sniper
# ============================================================================

set -e

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="${ENV_FILE}.backup.debug.$(date +%Y%m%d_%H%M%S)"

echo "🔍 Enabling Debug Mode..."
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

# Enable debug logging
add_or_update "PUMP_DEBUG_LOGGING" "true"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEBUG MODE ENABLED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next: Restart service to apply changes"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
echo "Then monitor logs for rejection reasons:"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -E 'REJECTION|CONFIRMATION|Opening position'"
echo ""
