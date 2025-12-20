#!/bin/bash
# ============================================================================
# Alpha Sniper V4.2 - Environment Optimizer (Phase 1)
# ============================================================================
# Adds regime-specific configuration overrides

set -e

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="${ENV_FILE}.backup.phase1.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Applying Phase 1 Optimizations..."
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
        # Update existing
        sudo sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
        echo "✅ Updated: $key=$value"
    else
        # Add new
        echo "${key}=${value}" | sudo tee -a "$ENV_FILE" > /dev/null
        echo "✅ Added: $key=$value"
    fi
}

echo "📝 Adding regime-specific settings..."
echo ""

# Regime-specific MAX LOSS overrides
add_or_update "PUMP_MAX_LOSS_PCT_STRONG_BULL" "0.03"
add_or_update "PUMP_MAX_LOSS_PCT_SIDEWAYS" "0.015"
add_or_update "PUMP_MAX_LOSS_PCT_MILD_BEAR" "0.012"
add_or_update "PUMP_MAX_LOSS_PCT_FULL_BEAR" "0.01"

# Regime-specific MIN SCORE overrides
add_or_update "MIN_SCORE_PUMP_STRONG_BULL" "0.70"
add_or_update "MIN_SCORE_PUMP_SIDEWAYS" "0.80"
add_or_update "MIN_SCORE_PUMP_MILD_BEAR" "0.85"
add_or_update "MIN_SCORE_PUMP_FULL_BEAR" "0.90"

# Regime-specific POSITION SIZE overrides
add_or_update "POSITION_SIZE_PCT_STRONG_BULL" "0.15"
add_or_update "POSITION_SIZE_PCT_SIDEWAYS" "0.07"
add_or_update "POSITION_SIZE_PCT_MILD_BEAR" "0.05"
add_or_update "POSITION_SIZE_PCT_FULL_BEAR" "0.03"

echo ""
echo "📝 Adding Phase 2 features config..."
echo ""

# Trailing stops (Phase 2A)
add_or_update "PUMP_TRAILING_ENABLED" "true"
add_or_update "PUMP_TRAILING_PCT" "0.03"
add_or_update "PUMP_TRAILING_ACTIVATION_PCT" "0.05"

# Partial take profits (Phase 2B)
add_or_update "PUMP_PARTIAL_TP_ENABLED" "true"
add_or_update "PUMP_PARTIAL_TP_LEVELS" "0.05:0.5,0.10:1.0"

# Position size scaling (Phase 2C)
add_or_update "POSITION_SCALE_WITH_SCORE" "true"
add_or_update "POSITION_SCALE_MAX" "1.5"

echo ""
echo "📝 Adding Phase 3 features config..."
echo ""

# Confirmation candles (Phase 3A)
add_or_update "PUMP_CONFIRMATION_CANDLES" "2"
add_or_update "PUMP_CONFIRMATION_VOLUME_MULT" "3.0"
add_or_update "PUMP_CONFIRMATION_PRICE_CHANGE_PCT" "0.02"

# ATR-based stops (Phase 3B)
add_or_update "PUMP_USE_ATR_STOPS" "false"
add_or_update "PUMP_ATR_PERIOD" "14"
add_or_update "PUMP_ATR_MULTIPLIER" "2.0"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ PHASE 1 COMPLETE - ENV FILE UPDATED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary of changes:"
echo "  ✅ Regime-specific max loss (0.01-0.03)"
echo "  ✅ Regime-specific min score (0.70-0.90)"
echo "  ✅ Regime-specific position size (0.03-0.15)"
echo "  ✅ Trailing stops config"
echo "  ✅ Partial TP config"
echo "  ✅ Position scaling config"
echo "  ✅ Confirmation candles config"
echo "  ✅ ATR stops config (disabled by default)"
echo ""
echo "Next: Restart service to apply changes"
echo "  sudo systemctl restart alpha-sniper-live.service"
echo ""
