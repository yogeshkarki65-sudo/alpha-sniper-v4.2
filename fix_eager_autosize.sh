#!/bin/bash
###############################################################################
# EAGER Auto-Fix Script - Finds optimal position size automatically
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"; }
print_info() { echo -e "  ${BLUE}ℹ${NC} $1"; }

cd /opt/alpha-sniper

print_step "Disabling EAGER temporarily to check balance..."
source venv/bin/activate

# Temporarily disable EAGER
python scripts/overrides_cli.py set --key EAGER_ENABLE --value false
sudo systemctl restart alpha-sniper-async.service
sleep 5

print_step "Checking actual free balance..."
FREE_USDT=$(sudo journalctl -u alpha-sniper-async.service --since "1 minute ago" | grep -oP 'Real equity: USDT=\K[0-9.]+' | tail -1)

if [ -z "$FREE_USDT" ]; then
    print_info "Could not detect balance, using conservative default"
    FREE_USDT=50
fi

print_info "Free USDT: \$$FREE_USDT"

# Calculate optimal risk percentage
# Formula: We want ~$30-50 position sizes (safe for $1 minimum, safe for balance)
# Position = (Balance * Risk) / SL%
# $30 = ($FREE_USDT * Risk) / 0.008
# Risk = ($30 * 0.008) / $FREE_USDT

TARGET_POSITION=30
SL_PCT=0.008
OPTIMAL_RISK=$(echo "scale=6; ($TARGET_POSITION * $SL_PCT) / $FREE_USDT" | bc)

# Cap between 0.001 and 0.005 (0.1% to 0.5%)
if (( $(echo "$OPTIMAL_RISK > 0.005" | bc -l) )); then
    OPTIMAL_RISK=0.005
fi
if (( $(echo "$OPTIMAL_RISK < 0.001" | bc -l) )); then
    OPTIMAL_RISK=0.001
fi

print_step "Configuring optimal settings..."
print_info "Risk per trade: $(echo "$OPTIMAL_RISK * 100" | bc)%"
print_info "Expected position size: ~\$$(echo "$FREE_USDT * $OPTIMAL_RISK / $SL_PCT" | bc | cut -d. -f1)"

# Apply settings
python scripts/overrides_cli.py set --key RISK_PER_TRADE --value $OPTIMAL_RISK
python scripts/overrides_cli.py set --key SIZING_AUTOPILOT_ENABLE --value false
python scripts/overrides_cli.py set --key EAGER_ENABLE --value true

print_step "Final configuration:"
python scripts/overrides_cli.py show

deactivate

print_step "Restarting service..."
sudo systemctl restart alpha-sniper-async.service

echo ""
echo -e "${GREEN}✓ EAGER auto-configured successfully!${NC}"
echo ""
print_info "Monitor for trades:"
echo "  ${YELLOW}sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered 'EAGER.*OPENED'${NC}"
echo ""
print_info "You should see EAGER trades within 2-3 minutes!"
echo ""
