#!/bin/bash
# ============================================================================
# Clear Old Positions Using 3h Max Hold
# ============================================================================

set -e

echo "🧹 Clearing old positions with 3h max hold..."
echo ""

POSITIONS_FILE="/var/lib/alpha-sniper/positions.json"

if [[ ! -f "$POSITIONS_FILE" ]]; then
    echo "✅ No positions file found"
    exit 0
fi

# Check for old positions
OLD_COUNT=$(cat "$POSITIONS_FILE" | grep -c '"max_hold_hours": 3' || echo "0")

if [[ "$OLD_COUNT" -eq 0 ]]; then
    echo "✅ No old positions to clear"
    exit 0
fi

# Backup and clear
echo "Found $OLD_COUNT position(s) using old 3h max hold"
echo ""

BACKUP_FILE="${POSITIONS_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
sudo cp "$POSITIONS_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

echo "[]" | sudo tee "$POSITIONS_FILE" > /dev/null
echo "✅ Cleared $OLD_COUNT old position(s)"
echo ""
echo "These positions will now close naturally according to their original rules."
echo "New positions will use the optimized 24h max hold time."
