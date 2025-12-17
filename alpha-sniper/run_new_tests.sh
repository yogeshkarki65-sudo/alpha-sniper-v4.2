#!/bin/bash
# Test runner for new unit tests covering git diff changes

echo "=========================================="
echo "Running Unit Tests for Git Diff Changes"
echo "=========================================="
echo ""

echo "Files tested (from git diff main..HEAD):"
echo "  - alpha-sniper/config.py"
echo "  - alpha-sniper/risk_engine.py"
echo "  - alpha-sniper/signals/pump_engine.py"
echo "  - alpha-sniper/main.py"
echo ""

cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

run_test() {
    echo "----------------------------------------"
    echo "Running: $1"
    echo "----------------------------------------"
    python3 "$1"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED: $1${NC}"
    else
        echo -e "${RED}✗ FAILED: $1${NC}"
        return 1
    fi
    echo ""
}

FAILED=0

# Run each test file
run_test "test_config_pump_thresholds.py" || FAILED=1
run_test "test_pump_engine_aggressive.py" || FAILED=1
run_test "test_risk_engine_regime.py" || FAILED=1
run_test "test_main_scan_timing.py" || FAILED=1
run_test "test_integration_pump_thresholds.py" || FAILED=1
run_test "test_edge_cases_boundaries.py" || FAILED=1

echo "=========================================="
echo "Test Summary"
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi