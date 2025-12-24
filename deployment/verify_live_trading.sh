#!/bin/bash
# Verification script for LIVE trading fixes
# Run this after deploying the fixes to verify everything is working

set -e

echo "========================================"
echo "Alpha Sniper V4.2 - LIVE Trading Verification"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verify config source
echo "1. Checking config source..."
config_logs=$(sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago" | grep "CONFIG_SOURCE\|CONFIG_INIT" | tail -5)
if [ -n "$config_logs" ]; then
    echo "$config_logs"
    echo -e "${GREEN}✓ Config source logged${NC}"
else
    echo -e "${YELLOW}⚠ No config source logs found (service may need restart)${NC}"
fi
echo ""

# 2. Verify mode is LIVE
echo "2. Checking mode..."
mode=$(sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago" | grep "Mode:" | tail -1)
echo "$mode"
if echo "$mode" | grep -q "Mode: LIVE"; then
    echo -e "${GREEN}✓ LIVE mode confirmed${NC}"
else
    echo -e "${RED}✗ WARNING: Not in LIVE mode!${NC}"
fi
echo ""

# 3. Check for sizing logs
echo "3. Checking sizing logs..."
sizing_logs=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "\[SIZING\]" | tail -5)
if [ -n "$sizing_logs" ]; then
    echo "$sizing_logs"
    echo -e "${GREEN}✓ Sizing logs active${NC}"
else
    echo -e "${YELLOW}⚠ No sizing logs yet (wait for next scan cycle)${NC}"
fi
echo ""

# 4. Check for min_notional rejections
echo "4. Checking min_notional rejections..."
rejections=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "below_min_notional\|notional_bump" | tail -5)
if [ -n "$rejections" ]; then
    echo "$rejections"
    rejection_count=$(echo "$rejections" | wc -l)
    echo -e "${YELLOW}Min notional issues: $rejection_count${NC}"
    echo "  Consider enabling ALLOW_MIN_NOTIONAL_BUMP=true"
else
    echo -e "${GREEN}✓ No min_notional issues${NC}"
fi
echo ""

# 5. Check for "invalid type" errors
echo "5. Checking for 'invalid type' errors..."
invalid_type=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "invalid type" | wc -l)
echo "Invalid type errors: $invalid_type"
if [ "$invalid_type" -eq 0 ]; then
    echo -e "${GREEN}✓ No 'invalid type' errors (stop placement fixed)${NC}"
else
    echo -e "${RED}✗ WARNING: Still seeing 'invalid type' errors!${NC}"
    sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "invalid type" | tail -3
fi
echo ""

# 6. Check protection logs
echo "6. Checking protection strategy..."
protection_logs=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "\[PROTECTION\]" | tail -3)
if [ -n "$protection_logs" ]; then
    echo "$protection_logs"
    echo -e "${GREEN}✓ Protection strategy active${NC}"
else
    echo -e "${YELLOW}⚠ No protection logs (no pump trades yet)${NC}"
fi
echo ""

# 7. Check for sizing bumps (if enabled)
echo "7. Checking sizing bumps..."
bumps=$(sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "\[SIZING_BUMP\]" | wc -l)
if [ "$bumps" -gt 0 ]; then
    echo -e "${GREEN}✓ Position sizing bumps active: $bumps${NC}"
    sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | grep "\[SIZING_BUMP\]" | tail -3
else
    echo "No sizing bumps (either disabled or not needed)"
fi
echo ""

# 8. Check for recent order placements
echo "8. Checking recent order attempts..."
orders=$(sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" | grep "\[PLACING_ORDER\]\|\[ORDER_OK\]\|ORDER_FAILED" | tail -10)
if [ -n "$orders" ]; then
    echo "$orders"
    echo -e "${GREEN}✓ Order activity detected${NC}"
else
    echo "No recent order attempts"
fi
echo ""

# 9. Summary
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo ""

# Count issues
issues=0
if [ "$invalid_type" -gt 0 ]; then
    echo -e "${RED}✗ Invalid type errors still occurring${NC}"
    issues=$((issues + 1))
else
    echo -e "${GREEN}✓ No invalid type errors${NC}"
fi

if echo "$mode" | grep -q "Mode: LIVE"; then
    echo -e "${GREEN}✓ Running in LIVE mode${NC}"
else
    echo -e "${RED}✗ Not in LIVE mode${NC}"
    issues=$((issues + 1))
fi

if [ -n "$config_logs" ]; then
    echo -e "${GREEN}✓ Config source logging active${NC}"
else
    echo -e "${YELLOW}⚠ Config source not logged${NC}"
fi

if [ -n "$sizing_logs" ]; then
    echo -e "${GREEN}✓ Detailed sizing logs active${NC}"
else
    echo -e "${YELLOW}⚠ Sizing logs not yet seen${NC}"
fi

echo ""
if [ "$issues" -eq 0 ]; then
    echo -e "${GREEN}✅ All critical checks passed!${NC}"
else
    echo -e "${YELLOW}⚠ $issues issues found - review above${NC}"
fi

echo ""
echo "Next steps:"
echo "1. Monitor for actual order placement:"
echo "   sudo journalctl -u alpha-sniper-live.service -f | grep 'PLACING_ORDER\\|ORDER_OK\\|PROTECTION'"
echo ""
echo "2. Check env file if ALLOW_MIN_NOTIONAL_BUMP needed:"
echo "   sudo nano /etc/alpha-sniper/alpha-sniper-live.env"
echo "   # Add: ALLOW_MIN_NOTIONAL_BUMP=true"
echo ""
