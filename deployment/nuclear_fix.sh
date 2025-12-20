#!/bin/bash
# ============================================================================
# NUCLEAR OPTION: Force fix METIS/CKB errors
# ============================================================================

set -e

POSITIONS_FILE="/var/lib/alpha-sniper/positions.json"
ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        NUCLEAR FIX FOR METIS/CKB ERRORS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Backup and clear positions
echo "Step 1: Clearing positions.json..."
if [[ -f "$POSITIONS_FILE" ]]; then
    sudo cp "$POSITIONS_FILE" "${POSITIONS_FILE}.backup.$(date +%s)"
    echo "[]" | sudo tee "$POSITIONS_FILE" > /dev/null
    echo "✅ Cleared all positions"
else
    echo "✅ Positions file doesn't exist (creating empty)"
    echo "[]" | sudo tee "$POSITIONS_FILE" > /dev/null
fi
echo ""

# Step 2: Add/update blacklist
echo "Step 2: Adding METIS/CKB to blacklist..."
if sudo grep -q "^SYMBOL_BLACKLIST=" "$ENV_FILE"; then
    # Update existing line
    sudo sed -i 's|^SYMBOL_BLACKLIST=.*|SYMBOL_BLACKLIST=METIS/USDT,CKB/USDT|' "$ENV_FILE"
    echo "✅ Updated SYMBOL_BLACKLIST"
else
    # Add new line
    echo "SYMBOL_BLACKLIST=METIS/USDT,CKB/USDT" | sudo tee -a "$ENV_FILE" > /dev/null
    echo "✅ Added SYMBOL_BLACKLIST"
fi
echo ""

# Step 3: Show what we set
echo "Step 3: Verifying configuration..."
echo "Blacklist setting:"
sudo grep "^SYMBOL_BLACKLIST=" "$ENV_FILE" || echo "  (not found - will use empty)"
echo ""

# Step 4: Kill and restart service
echo "Step 4: Force restarting service..."
sudo systemctl stop alpha-sniper-live.service
sleep 2
sudo systemctl start alpha-sniper-live.service
echo "✅ Service restarted"
echo ""

# Step 5: Wait and check logs
echo "Step 5: Checking logs (waiting 10 seconds)..."
sleep 10

echo ""
echo "Recent logs:"
sudo journalctl -u alpha-sniper-live.service --since "30 seconds ago" | tail -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ FIX APPLIED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Monitor logs for METIS/CKB errors:"
echo "  sudo journalctl -u alpha-sniper-live.service -f | grep -i 'metis\|ckb\|error'"
echo ""
echo "If you STILL see errors, check:"
echo "  1. Service status: sudo systemctl status alpha-sniper-live.service"
echo "  2. Positions file: sudo cat $POSITIONS_FILE"
echo "  3. Blacklist setting: sudo grep SYMBOL_BLACKLIST $ENV_FILE"
echo ""
