#!/bin/bash
###############################################################################
# EAGER Feature Verification Script
# Usage: bash verify_eager.sh
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_PATH="/opt/alpha-sniper"
SERVICE_NAME="alpha-sniper-async.service"

print_header() {
    echo -e "${BLUE}[$1]${NC} ${GREEN}$2${NC}"
}

print_ok() {
    echo -e "  ${GREEN}✓${NC} $1"
}

print_fail() {
    echo -e "  ${RED}✗${NC} $1"
}

print_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

cd "$REPO_PATH" || exit 1

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          EAGER Breakout Feature - Verification                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Check service status
print_header "1" "Service Status"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    print_ok "Service is running"
    UPTIME=$(systemctl show "$SERVICE_NAME" -p ActiveEnterTimestamp --value)
    print_info "Started: $UPTIME"
else
    print_fail "Service is not running"
    echo ""
    echo "Start with: sudo systemctl start $SERVICE_NAME"
    exit 1
fi
echo ""

# 2. Check git branch
print_header "2" "Git Branch"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_COMMIT=$(git rev-parse --short HEAD)
print_info "Branch: $CURRENT_BRANCH"
print_info "Commit: $CURRENT_COMMIT"

if [[ "$CURRENT_BRANCH" == "claude/fix-issues-018PzVLhR8jpyJBusPvozqDS" ]] || git log -1 --oneline | grep -q "EAGER"; then
    print_ok "EAGER code is present"
else
    print_fail "EAGER code may not be deployed"
fi
echo ""

# 3. Check EAGER settings
print_header "3" "EAGER Configuration"

python3 <<EOF
import sys
sys.path.insert(0, '/opt/alpha-sniper')
try:
    from alpha_sniper.config.settings import Settings
    s = Settings()

    print(f"  EAGER_ENABLE: {s.EAGER_ENABLE} {'✓' if s.EAGER_ENABLE else '✗ (disabled)'}")
    print(f"  EAGER_VSPIKE_MIN: {s.EAGER_VSPIKE_MIN}")
    print(f"  EAGER_MAX_NEG_RET5M: {s.EAGER_MAX_NEG_RET5M}")
    print(f"  EAGER_LOOKBACK_HIGH_N: {s.EAGER_LOOKBACK_HIGH_N}")
    print(f"  EAGER_SL_PCT: {s.EAGER_SL_PCT * 100:.1f}%")
    print(f"  EAGER_TP_PCT: {s.EAGER_TP_PCT * 100:.1f}%")
    print(f"  EAGER_MAX_PER_SCAN: {s.EAGER_MAX_PER_SCAN}")
    print(f"  EAGER_ONLY_LIVE_TEST: {s.EAGER_ONLY_LIVE_TEST}")

    # Check LIVE_TEST_MODE
    live_test = getattr(s, 'LIVE_TEST_MODE', None)
    print(f"  LIVE_TEST_MODE: {live_test}")

    # Determine if EAGER will actually trade
    if s.EAGER_ENABLE:
        if s.EAGER_ONLY_LIVE_TEST and live_test:
            print(f"\n  ℹ EAGER will run in TEST mode (no real trades)")
        elif s.EAGER_ONLY_LIVE_TEST and not live_test:
            print(f"\n  ✗ EAGER is DISABLED (EAGER_ONLY_LIVE_TEST=True but LIVE_TEST_MODE=False)")
        else:
            print(f"\n  ✓ EAGER will execute REAL trades")
    else:
        print(f"\n  ✗ EAGER is disabled")

except Exception as e:
    print(f"  ✗ Failed to load settings: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    print_fail "Configuration check failed"
    exit 1
fi
echo ""

# 4. Check runtime overrides
print_header "4" "Runtime Overrides"
if [ -f "data/overrides.json" ]; then
    print_ok "overrides.json exists"

    # Check if EAGER overrides are present
    if grep -q "EAGER" data/overrides.json 2>/dev/null; then
        print_info "EAGER overrides found:"
        grep "EAGER" data/overrides.json | sed 's/^/    /'
    else
        print_info "No EAGER overrides (using defaults)"
    fi

    # Show AutoTune state
    if grep -q "EARLY_ACCEL_REQUIRED" data/overrides.json 2>/dev/null; then
        ACCEL_STATE=$(grep "EARLY_ACCEL_REQUIRED" data/overrides.json | grep -o "true\|false")
        print_info "EARLY_ACCEL_REQUIRED: $ACCEL_STATE"
    fi
else
    print_info "No overrides.json (using defaults)"
fi
echo ""

# 5. Check recent logs for EAGER activity
print_header "5" "Recent EAGER Activity"

EAGER_LOGS=$(journalctl -u "$SERVICE_NAME" --since "10 minutes ago" --no-pager | grep -i "EAGER" || true)

if [ -n "$EAGER_LOGS" ]; then
    print_ok "EAGER logs found in last 10 minutes"
    echo ""
    echo "$EAGER_LOGS" | tail -10 | sed 's/^/    /'
else
    print_info "No EAGER logs in last 10 minutes"
    print_info "EAGER may not have found suitable candidates yet"
fi
echo ""

# 6. Check for EARLY_TOP (near-miss) logs
print_header "6" "Near-Miss Visibility"

EARLY_TOP_LOGS=$(journalctl -u "$SERVICE_NAME" --since "5 minutes ago" --no-pager | grep "EARLY_TOP" || true)

if [ -n "$EARLY_TOP_LOGS" ]; then
    print_ok "Near-miss logs found"
    echo ""
    echo "$EARLY_TOP_LOGS" | tail -3 | sed 's/^/    /'
    echo ""

    # Check if depth is populated
    if echo "$EARLY_TOP_LOGS" | grep -q "depth=\$[1-9]"; then
        print_ok "Depth snapshot working (shows non-zero values)"
    else
        print_info "Depth snapshot may not be working (all zeros)"
    fi
else
    print_info "No near-miss logs in last 5 minutes"
fi
echo ""

# 7. Check for feature extraction
print_header "7" "Feature Extraction"

FEATURE_LOGS=$(journalctl -u "$SERVICE_NAME" --since "5 minutes ago" --no-pager | grep -E "ret5m=.*vspike=" || true)

if [ -n "$FEATURE_LOGS" ]; then
    # Check if values are non-zero
    if echo "$FEATURE_LOGS" | grep -q "ret5m=[^0].*vspike=[^0]"; then
        print_ok "Feature extraction working (non-zero values)"
    else
        print_fail "Feature extraction may have issues (all zeros)"
    fi
else
    print_info "No feature logs found yet"
fi
echo ""

# 8. Summary and recommendations
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                        Summary                                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Overall status
python3 <<EOF
import sys
sys.path.insert(0, '/opt/alpha-sniper')
from alpha_sniper.config.settings import Settings

s = Settings()
live_test = getattr(s, 'LIVE_TEST_MODE', True)

if s.EAGER_ENABLE:
    if s.EAGER_ONLY_LIVE_TEST and live_test:
        print("  Status: EAGER is ENABLED (TEST MODE)")
        print("  • EAGER will log candidates but NOT execute real trades")
        print("  • To enable real trading:")
        print("    python scripts/overrides_cli.py set --key EAGER_ONLY_LIVE_TEST --value false")
        print("    sudo systemctl restart alpha-sniper-async.service")
    elif s.EAGER_ONLY_LIVE_TEST and not live_test:
        print("  Status: EAGER is BLOCKED")
        print("  • EAGER_ONLY_LIVE_TEST=True but LIVE_TEST_MODE=False")
        print("  • To enable:")
        print("    python scripts/overrides_cli.py set --key EAGER_ONLY_LIVE_TEST --value false")
        print("    sudo systemctl restart alpha-sniper-async.service")
    else:
        print("  Status: EAGER is ENABLED (LIVE TRADING)")
        print("  • EAGER will execute REAL trades!")
        print("  • Monitor with: sudo journalctl -u alpha-sniper-async.service -f | grep EAGER")
else:
    print("  Status: EAGER is DISABLED")
    print("  • To enable:")
    print("    python scripts/overrides_cli.py set --key EAGER_ENABLE --value true")
    print("    sudo systemctl restart alpha-sniper-async.service")
EOF

echo ""
print_info "Monitoring commands:"
echo ""
echo "  Watch EAGER activity:"
echo "    ${YELLOW}sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered EAGER${NC}"
echo ""
echo "  Watch near-miss logs:"
echo "    ${YELLOW}sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered EARLY_TOP${NC}"
echo ""
echo "  Watch all trades:"
echo "    ${YELLOW}sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered 'OPENED\|CLOSED'${NC}"
echo ""
echo "  View current config:"
echo "    ${YELLOW}python scripts/overrides_cli.py show${NC}"
echo ""
