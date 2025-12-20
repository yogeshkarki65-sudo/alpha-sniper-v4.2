#!/bin/bash
# ============================================================================
# Force Close Problematic Positions (METIS/USDT, CKB/USDT)
# ============================================================================

set -e

POSITIONS_FILE="/var/lib/alpha-sniper/positions.json"
BACKUP_FILE="${POSITIONS_FILE}.backup.force_close.$(date +%Y%m%d_%H%M%S)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        FORCE CLOSE PROBLEMATIC POSITIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will remove METIS/USDT and CKB/USDT from positions.json"
echo "You must manually sell these on MEXC first!"
echo ""

# Check if positions file exists
if [[ ! -f "$POSITIONS_FILE" ]]; then
    echo "❌ Positions file not found: $POSITIONS_FILE"
    exit 1
fi

# Backup first
sudo cp "$POSITIONS_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"
echo ""

# Show current positions
echo "Current positions in file:"
sudo cat "$POSITIONS_FILE" | jq -r '.[] | .symbol' 2>/dev/null || echo "(Unable to parse - may be empty or corrupt)"
echo ""

# Ask for confirmation
read -p "Have you MANUALLY CLOSED METIS/USDT and CKB/USDT on MEXC? (yes/no): " confirm

if [[ "$confirm" != "yes" ]]; then
    echo ""
    echo "❌ Aborting. Please close the positions on MEXC first, then re-run this script."
    echo ""
    echo "To close manually:"
    echo "  1. Go to MEXC Spot > Open Orders/Positions"
    echo "  2. Market sell all METIS"
    echo "  3. Market sell all CKB"
    echo "  4. Then run this script again"
    exit 1
fi

# Remove METIS/USDT and CKB/USDT from positions.json
echo "Removing METIS/USDT and CKB/USDT from positions file..."
sudo jq 'map(select(.symbol != "METIS/USDT" and .symbol != "CKB/USDT"))' "$POSITIONS_FILE" > /tmp/positions_cleaned.json
sudo mv /tmp/positions_cleaned.json "$POSITIONS_FILE"

echo ""
echo "✅ Positions removed from tracking file"
echo ""

# Show remaining positions
echo "Remaining positions:"
sudo cat "$POSITIONS_FILE" | jq -r '.[] | .symbol' 2>/dev/null || echo "(No positions)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ CLEANUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Apply blacklist to prevent these symbols from being traded again:"
echo "     sudo ./deployment/fix_symbol_errors.sh"
echo ""
echo "  2. Restart service:"
echo "     sudo systemctl restart alpha-sniper-live.service"
echo ""
echo "  3. Monitor logs to confirm no more errors:"
echo "     sudo journalctl -u alpha-sniper-live.service -f | grep -E 'METIS|CKB|ERROR'"
echo ""
