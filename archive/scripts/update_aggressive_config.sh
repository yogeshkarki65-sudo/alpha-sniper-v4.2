#!/bin/bash
# ========================================
# Update Alpha Sniper Config to Aggressive Pump-Only
# ========================================
# This script updates ONLY pump-related and risk settings
# Does NOT touch: API keys, Telegram credentials, or other settings
# ========================================

set -e  # Exit on error

CONFIG_FILE="/etc/alpha-sniper/alpha-sniper-live.env"
BACKUP_FILE="/etc/alpha-sniper/alpha-sniper-live.env.backup.$(date +%Y%m%d_%H%M%S)"

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

echo "========================================="
echo "Updating to AGGRESSIVE Pump-Only Config"
echo "========================================="
echo ""
echo "Backup: $BACKUP_FILE"

# Create backup
sudo cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "✓ Backup created"

# Update pump-only mode
sudo sed -i 's/^PUMP_ONLY_MODE=.*/PUMP_ONLY_MODE=true/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_ENGINE_ENABLED=.*/PUMP_ENGINE_ENABLED=true/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MAX_CONCURRENT=.*/PUMP_MAX_CONCURRENT=3/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_RISK_PER_TRADE=.*/PUMP_RISK_PER_TRADE=0.006/' "$CONFIG_FILE"

# Update pump filters (loosened)
sudo sed -i 's/^PUMP_MIN_24H_RETURN=.*/PUMP_MIN_24H_RETURN=0.50/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MAX_24H_RETURN=.*/PUMP_MAX_24H_RETURN=5.00/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MIN_RVOL=.*/PUMP_MIN_RVOL=2.0/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MIN_MOMENTUM_1H=.*/PUMP_MIN_MOMENTUM_1H=35/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MIN_24H_QUOTE_VOLUME=.*/PUMP_MIN_24H_QUOTE_VOLUME=500000/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MIN_SCORE=.*/PUMP_MIN_SCORE=75/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_MAX_HOLD_HOURS=.*/PUMP_MAX_HOLD_HOURS=2/' "$CONFIG_FILE"

# Update ATR trailing stops (aggressive)
sudo sed -i 's/^PUMP_TRAIL_INITIAL_ATR_MULT=.*/PUMP_TRAIL_INITIAL_ATR_MULT=2.0/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_TRAIL_ATR_MULT=.*/PUMP_TRAIL_ATR_MULT=1.3/' "$CONFIG_FILE"
sudo sed -i 's/^PUMP_TRAIL_START_MINUTES=.*/PUMP_TRAIL_START_MINUTES=20/' "$CONFIG_FILE"

# Update risk management (protected)
sudo sed -i 's/^MAX_PORTFOLIO_HEAT=.*/MAX_PORTFOLIO_HEAT=0.03/' "$CONFIG_FILE"
sudo sed -i 's/^MAX_CONCURRENT_POSITIONS=.*/MAX_CONCURRENT_POSITIONS=3/' "$CONFIG_FILE"
sudo sed -i 's/^MAX_SPREAD_PCT=.*/MAX_SPREAD_PCT=0.8/' "$CONFIG_FILE"
sudo sed -i 's/^ENABLE_DAILY_LOSS_LIMIT=.*/ENABLE_DAILY_LOSS_LIMIT=true/' "$CONFIG_FILE"
sudo sed -i 's/^MAX_DAILY_LOSS_PCT=.*/MAX_DAILY_LOSS_PCT=0.03/' "$CONFIG_FILE"

# Update timing
sudo sed -i 's/^SCAN_INTERVAL_SECONDS=.*/SCAN_INTERVAL_SECONDS=120/' "$CONFIG_FILE"
sudo sed -i 's/^POSITION_CHECK_INTERVAL_SECONDS=.*/POSITION_CHECK_INTERVAL_SECONDS=10/' "$CONFIG_FILE"

# Update stop distances (aggressive)
sudo sed -i 's/^MIN_STOP_PCT_CORE=.*/MIN_STOP_PCT_CORE=0.015/' "$CONFIG_FILE"
sudo sed -i 's/^MIN_STOP_PCT_BEAR_MICRO=.*/MIN_STOP_PCT_BEAR_MICRO=0.012/' "$CONFIG_FILE"
sudo sed -i 's/^MIN_STOP_PCT_PUMP=.*/MIN_STOP_PCT_PUMP=0.020/' "$CONFIG_FILE"

# Disable conflicting features
sudo sed -i 's/^SHORT_FUNDING_OVERLAY_ENABLED=.*/SHORT_FUNDING_OVERLAY_ENABLED=false/' "$CONFIG_FILE"
sudo sed -i 's/^CORRELATION_LIMIT_ENABLED=.*/CORRELATION_LIMIT_ENABLED=false/' "$CONFIG_FILE"

echo "✓ Configuration updated"
echo ""
echo "========================================="
echo "CHANGES APPLIED (Aggressive Pump-Only)"
echo "========================================="
echo ""
echo "PUMP FILTERS (Loosened):"
echo "  - Min 24h Return: 50% (was 80%)"
echo "  - Max 24h Return: 500% (was 300%)"
echo "  - Min RVOL: 2.0x (was 3.0x)"
echo "  - Min Momentum: 35 (was 45)"
echo "  - Min Volume: \$500k (was \$1M)"
echo "  - Min Score: 75 (was 90)"
echo "  - Max Hold: 2h (was 3h)"
echo ""
echo "RISK MANAGEMENT (Protected):"
echo "  - Risk per trade: 0.6% (was 0.08%)"
echo "  - Portfolio heat: 3% (was 0.8%)"
echo "  - Daily loss limit: 3% (was 2%)"
echo "  - Max concurrent: 3 positions"
echo ""
echo "ATR STOPS (Aggressive):"
echo "  - Initial stop: 2.0x ATR (was 2.5x)"
echo "  - Trailing stop: 1.3x ATR (was 1.5x)"
echo "  - Trail start: 20 min (was 30 min)"
echo ""
echo "TIMING:"
echo "  - Scan interval: 2 min (was 3 min)"
echo "  - Position check: 10s (was 15s)"
echo ""
echo "========================================="
echo "NEXT STEPS:"
echo "========================================="
echo ""
echo "1. Verify changes:"
echo "   sudo grep -E '^(PUMP_|MAX_PORTFOLIO_HEAT|MAX_DAILY_LOSS)' $CONFIG_FILE"
echo ""
echo "2. Restart service:"
echo "   sudo systemctl restart alpha-sniper-live.service"
echo ""
echo "3. Check logs:"
echo "   sudo journalctl -u alpha-sniper-live.service -n 80 --no-pager"
echo ""
echo "4. Restore backup if needed:"
echo "   sudo cp $BACKUP_FILE $CONFIG_FILE"
echo "   sudo systemctl restart alpha-sniper-live.service"
echo ""
