#!/bin/bash
###############################################################################
# Quick EAGER Verification (No Pydantic imports)
###############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_ok() { echo -e "  ${GREEN}✓${NC} $1"; }
print_fail() { echo -e "  ${RED}✗${NC} $1"; }
print_info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
print_header() { echo -e "${BLUE}[$1]${NC} ${GREEN}$2${NC}"; }

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          EAGER Feature - Quick Verification                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Service Status
print_header "1" "Service Status"
if systemctl is-active --quiet alpha-sniper-async.service; then
    print_ok "Service is running"
    systemctl status alpha-sniper-async.service --no-pager -l | head -3 | tail -1
else
    print_fail "Service is NOT running"
    echo ""
    echo "Start with: sudo systemctl start alpha-sniper-async.service"
    exit 1
fi
echo ""

# 2. EAGER Code Present
print_header "2" "EAGER Code in Files"
if grep -q "EAGER_ENABLE" alpha-sniper/config/settings.py; then
    print_ok "EAGER settings found in settings.py"
    grep "EAGER_ENABLE\|EAGER_VSPIKE_MIN\|EAGER_SL_PCT\|EAGER_TP_PCT" alpha-sniper/config/settings.py | head -4 | sed 's/^/    /'
else
    print_fail "EAGER settings NOT found in settings.py"
fi
echo ""

if grep -q "EAGER breakout" app_async.py; then
    print_ok "EAGER pipeline found in app_async.py"
    grep -n "EAGER breakout" app_async.py | head -1 | sed 's/^/    Line /'
else
    print_fail "EAGER pipeline NOT found in app_async.py"
fi
echo ""

# 3. Recent Logs
print_header "3" "Recent Activity (last 2 minutes)"
RECENT_LOGS=$(journalctl -u alpha-sniper-async.service --since "2 minutes ago" --no-pager)

if echo "$RECENT_LOGS" | grep -q "EARLY_TOP"; then
    print_ok "Near-miss logs found"
    echo "$RECENT_LOGS" | grep "EARLY_TOP" | tail -3 | sed 's/^/    /'
else
    print_info "No near-miss logs yet (wait for next scan)"
fi
echo ""

if echo "$RECENT_LOGS" | grep -q "EAGER"; then
    print_ok "EAGER activity found"
    echo "$RECENT_LOGS" | grep "EAGER" | tail -5 | sed 's/^/    /'
else
    print_info "No EAGER activity yet"
fi
echo ""

# 4. Runtime Overrides
print_header "4" "Current Configuration"
if [ -f "data/overrides.json" ]; then
    print_ok "overrides.json exists"

    if grep -q "EARLY_ACCEL_REQUIRED" data/overrides.json; then
        ACCEL=$(grep "EARLY_ACCEL_REQUIRED" data/overrides.json | grep -o "true\|false")
        print_info "EARLY_ACCEL_REQUIRED: $ACCEL"
    fi

    if grep -q "EAGER" data/overrides.json; then
        print_info "EAGER overrides present:"
        grep "EAGER" data/overrides.json | sed 's/^/    /'
    else
        print_info "No EAGER overrides (using defaults)"
    fi
else
    print_info "No overrides.json"
fi
echo ""

# 5. Summary
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                        Status                                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if systemctl is-active --quiet alpha-sniper-async.service && grep -q "EAGER_ENABLE" alpha-sniper/config/settings.py; then
    print_ok "EAGER feature is DEPLOYED and service is RUNNING"
    echo ""
    print_info "By default, EAGER_ONLY_LIVE_TEST=True"
    print_info "This means EAGER only runs when LIVE_TEST_MODE=True"
    echo ""
    print_info "Monitor EAGER activity:"
    echo "  ${YELLOW}sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered EAGER${NC}"
    echo ""
    print_info "Watch near-miss logs (top 3 candidates):"
    echo "  ${YELLOW}sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered EARLY_TOP${NC}"
    echo ""
    print_info "To enable EAGER in production:"
    echo "  ${YELLOW}python scripts/overrides_cli.py set --key EAGER_ONLY_LIVE_TEST --value false${NC}"
    echo "  ${YELLOW}sudo systemctl restart alpha-sniper-async.service${NC}"
else
    print_fail "EAGER deployment incomplete or service not running"
fi
echo ""
