#!/bin/bash
# One-shot verification script for Alpha Sniper hardening
# Usage: bash verification_script.sh

set -e

echo "=========================================="
echo "Alpha Sniper Verification Script"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd /opt/alpha-sniper/alpha-sniper || { echo "Failed to cd to /opt/alpha-sniper/alpha-sniper"; exit 1; }
source ../venv/bin/activate || { echo "Failed to activate venv"; exit 1; }

echo "1. Checking current overrides..."
python ../scripts/overrides_cli.py show 2>/dev/null || echo "No overrides set"
echo ""

echo "2. Verifying key settings..."
python ../scripts/print_settings.py --json 2>/dev/null | jq -r '.settings | {
  MODE,
  LIVE_TEST_MODE,
  LIVE_TEST_MAX_USD_PER_ORDER,
  RISK_PER_TRADE,
  EAGER_SL_PCT,
  EAGER_MIN_DEPTH_USD,
  RESERVE_USDT,
  EAGER_EPS_PCT
}' || echo "Settings verification failed (expected if --json not yet implemented)"
echo ""

echo -e "${YELLOW}3. Restarting alpha-sniper-async.service...${NC}"
sudo systemctl restart alpha-sniper-async.service
echo "Waiting 8 seconds for startup..."
sleep 8
echo ""

echo "4. Service status:"
sudo systemctl status alpha-sniper-async.service --no-pager -l | head -15
echo ""

echo -e "${GREEN}5. Monitoring logs for new patterns...${NC}"
echo "Looking for: [AUTO_BUMP], [CLAMP], [PRECISION], [ORDER_TIF], [EAGER]"
echo "Press Ctrl+C to stop"
echo ""

sudo journalctl -u alpha-sniper-async.service -f --no-pager -o cat | grep --line-buffered -E '\[AUTO_BUMP\]|\[CLAMP\]|\[PRECISION\]|\[ORDER_TIF\]|\[EAGER\]|\[LIVE_TEST\]|OPENED|CLOSED|insufficient|rounded_to_zero|unaffordable' | while read line; do
    echo "$line"
done
