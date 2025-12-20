#!/bin/bash
# ============================================================================
# Add Symbol Trading Validation (Fix NoneType Errors)
# ============================================================================

set -e

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="${ENV_FILE}.backup.symbol_validation.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Adding Symbol Trading Validation..."
echo ""

# Backup
sudo cp "$ENV_FILE" "$BACKUP_FILE"
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

# Add symbol blacklist for symbols that cause trading errors
echo "📝 Adding problematic symbol blacklist..."
add_or_update "SYMBOL_BLACKLIST" "METIS/USDT,CKB/USDT"

# Enable more detailed exchange error logging
echo "📝 Enabling detailed exchange logging..."
add_or_update "EXCHANGE_DEBUG_LOGGING" "true"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SYMBOL VALIDATION CONFIGURED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Blacklisted symbols: METIS/USDT, CKB/USDT"
echo ""
echo "Next: Restart service to apply changes"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
echo "Monitor to confirm errors are gone:"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -E 'ERROR|Opening position'"
echo ""
echo "To rollback:"
echo "  sudo cp $BACKUP_FILE $ENV_FILE"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
