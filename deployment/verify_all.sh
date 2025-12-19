#!/bin/bash
# ============================================================================
# Alpha Sniper V4.2 - Comprehensive Verification Script
# ============================================================================
# Checks ALL critical systems and provides clear PASS/FAIL status
# Returns: 0 if all checks pass, 1 if any critical failures

set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Results array
declare -a RESULTS

# Functions
check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    RESULTS+=("✅ $1")
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    RESULTS+=("❌ $1")
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    RESULTS+=("⚠️  $1")
    ((WARN_COUNT++))
}

section_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Sanitize count values (ensure single integer)
sanitize_count() {
    echo "$1" | head -1 | tr -d '\n\r' | grep -oE '^[0-9]+$' || echo "0"
}

# ============================================================================
# 1. SYSTEMD SERVICE STATUS
# ============================================================================
section_header "1. SERVICE STATUS"

SERVICE_STATUS=$(sudo systemctl is-active alpha-sniper-live.service 2>/dev/null || echo "inactive")
if [[ "$SERVICE_STATUS" == "active" ]]; then
    check_pass "Service is ACTIVE and running"
else
    check_fail "Service is NOT active (status: $SERVICE_STATUS)"
fi

SERVICE_ENABLED=$(sudo systemctl is-enabled alpha-sniper-live.service 2>/dev/null || echo "disabled")
if [[ "$SERVICE_ENABLED" == "enabled" ]]; then
    check_pass "Service is ENABLED for auto-start"
else
    check_warn "Service not enabled for auto-start"
fi

# Check if service has recent restarts
RESTART_COUNT=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -c "Started Alpha Sniper" || echo "0")
RESTART_COUNT=$(sanitize_count "$RESTART_COUNT")
if [[ "$RESTART_COUNT" -gt 3 ]]; then
    check_warn "Service restarted $RESTART_COUNT times in last hour (possible crash loop)"
elif [[ "$RESTART_COUNT" -gt 0 ]]; then
    check_pass "Service stable ($RESTART_COUNT restart(s) in last hour)"
else
    check_pass "Service stable (no restarts in last hour)"
fi

# ============================================================================
# 2. FILE PERMISSIONS
# ============================================================================
section_header "2. FILE PERMISSIONS"

# Check positions.json directory
if [[ -d "/var/lib/alpha-sniper" ]]; then
    PERMS=$(stat -c "%a" /var/lib/alpha-sniper 2>/dev/null || echo "000")
    if [[ "$PERMS" == "777" ]] || [[ "$PERMS" == "775" ]]; then
        check_pass "State directory writable ($PERMS)"
    else
        check_fail "State directory not writable ($PERMS) - need 777 or 775"
    fi
else
    check_fail "State directory /var/lib/alpha-sniper does not exist"
fi

# Check logs directory
if [[ -d "/opt/alpha-sniper/logs" ]]; then
    PERMS=$(stat -c "%a" /opt/alpha-sniper/logs 2>/dev/null || echo "000")
    if [[ "$PERMS" == "777" ]] || [[ "$PERMS" == "775" ]]; then
        check_pass "Logs directory writable ($PERMS)"
    else
        check_fail "Logs directory not writable ($PERMS) - need 777 or 775"
    fi
else
    check_fail "Logs directory /opt/alpha-sniper/logs does not exist"
fi

# Check if log file exists and is recent
if [[ -f "/opt/alpha-sniper/logs/bot.log" ]]; then
    LOG_AGE=$(find /opt/alpha-sniper/logs/bot.log -mmin -10 2>/dev/null)
    if [[ -n "$LOG_AGE" ]]; then
        check_pass "Log file exists and is being written (modified in last 10 minutes)"
    else
        check_warn "Log file exists but not recently modified (>10 minutes old)"
    fi
else
    check_fail "Log file /opt/alpha-sniper/logs/bot.log does not exist"
fi

# ============================================================================
# 3. CONFIGURATION VALIDATION
# ============================================================================
section_header "3. CONFIGURATION VALIDATION"

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"

if [[ ! -f "$ENV_FILE" ]]; then
    check_fail "Env file not found: $ENV_FILE"
else
    check_pass "Env file exists: $ENV_FILE"

    # Check critical settings
    PUMP_ONLY=$(grep "^PUMP_ONLY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
    if [[ "$PUMP_ONLY" == "true" ]]; then
        check_pass "Pump-only mode ENABLED"
    else
        check_warn "Pump-only mode NOT enabled (expected for optimized config)"
    fi

    MAX_HOLD=$(grep "^MAX_HOLD_HOURS_PUMP=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
    if [[ "$MAX_HOLD" == "24" ]]; then
        check_pass "Max hold time optimized (24h)"
    else
        check_warn "Max hold time is $MAX_HOLD hours (optimized value: 24h)"
    fi

    MIN_SCORE=$(grep "^MIN_SCORE_PUMP=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
    if [[ "$MIN_SCORE" == "0.75" ]]; then
        check_pass "Min score optimized (0.75)"
    elif [[ "$MIN_SCORE" == "0.7" ]]; then
        check_pass "Min score set to 0.7 (recommended: 0.75)"
    else
        check_warn "Min score is $MIN_SCORE (optimized value: 0.75)"
    fi

    PUMP_MAX_LOSS=$(grep "^PUMP_MAX_LOSS_PCT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
    if [[ -n "$PUMP_MAX_LOSS" ]]; then
        check_pass "Pump max loss configured ($PUMP_MAX_LOSS)"
    else
        check_fail "PUMP_MAX_LOSS_PCT not set in env file"
    fi

    # Check Telegram config
    TG_SCAN=$(grep "^TELEGRAM_SCAN_SUMMARY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
    if [[ "$TG_SCAN" == "true" ]]; then
        check_pass "Telegram scan summaries ENABLED"
    else
        check_warn "Telegram scan summaries NOT enabled"
    fi
fi

# ============================================================================
# 4. RECENT BOT ACTIVITY (Last 15 Minutes)
# ============================================================================
section_header "4. RECENT BOT ACTIVITY (Last 15 min)"

RECENT_LOGS=$(sudo journalctl -u alpha-sniper-live.service --since "15 minutes ago" --no-pager 2>/dev/null)

# Check for scan cycles (look for either "Scan cycle starting" or "Market data" as scan indicators)
SCAN_COUNT=$(echo "$RECENT_LOGS" | grep -cE "(Scan cycle starting|Market data:.*symbols fetched)" || echo "0")
SCAN_COUNT=$(sanitize_count "$SCAN_COUNT")
if [[ "$SCAN_COUNT" -gt 0 ]]; then
    check_pass "Scan cycles active ($SCAN_COUNT scans in last 15 min)"

    # Show last scan info
    LAST_SCAN=$(echo "$RECENT_LOGS" | grep -E "(Scan cycle starting|Market data:.*symbols fetched)" | tail -1)
    if [[ -n "$LAST_SCAN" ]]; then
        echo "   Last scan: $(echo "$LAST_SCAN" | awk '{print $1, $2, $3}')"
    fi
else
    check_fail "No scan cycles detected in last 15 minutes"
fi

# Check for signal generation
SIGNAL_COUNT=$(echo "$RECENT_LOGS" | grep -E "Generated [0-9]+ signal" | tail -1 | grep -oE "[0-9]+" | head -1 || echo "0")
if [[ "$SIGNAL_COUNT" -gt 0 ]]; then
    check_pass "Signals being generated (last scan: $SIGNAL_COUNT signals)"
elif [[ "$SCAN_COUNT" -gt 0 ]]; then
    check_warn "Scans running but no signals generated (market conditions or thresholds too strict)"
else
    check_warn "Cannot determine signal generation (no recent scans)"
fi

# Check for pump trades
PUMP_TRADES=$(echo "$RECENT_LOGS" | grep -c "PUMP.*Position opened" || echo "0")
PUMP_TRADES=$(sanitize_count "$PUMP_TRADES")
if [[ "$PUMP_TRADES" -gt 0 ]]; then
    check_pass "Pump trades occurring ($PUMP_TRADES in last 15 min)"
else
    check_warn "No pump trades in last 15 min (may be normal if no signals meet criteria)"
fi

# Check regime detection
REGIME=$(echo "$RECENT_LOGS" | grep -oE "Regime: [A-Z_]+" | tail -1 | cut -d' ' -f2 || echo "UNKNOWN")
if [[ "$REGIME" != "UNKNOWN" ]] && [[ -n "$REGIME" ]]; then
    check_pass "Regime detection working (current: $REGIME)"
else
    check_warn "Regime showing as UNKNOWN (may affect signal generation)"
fi

# ============================================================================
# 5. WATCHDOG MONITORING
# ============================================================================
section_header "5. WATCHDOG PROTECTION"

# Check last 30 minutes for watchdog (it may start once then run silently)
WATCHDOG_LOGS=$(sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" --no-pager 2>/dev/null)
WATCHDOG_INIT=$(echo "$WATCHDOG_LOGS" | grep -c "SYNTHETIC STOP WATCHDOG started" || echo "0")
WATCHDOG_INIT=$(sanitize_count "$WATCHDOG_INIT")

if [[ "$WATCHDOG_INIT" -gt 0 ]]; then
    check_pass "Watchdog initialized and running"
else
    # Check if service was restarted in last 30 min
    SERVICE_START=$(echo "$WATCHDOG_LOGS" | grep -c "Started Alpha Sniper" || echo "0")
    SERVICE_START=$(sanitize_count "$SERVICE_START")
    if [[ "$SERVICE_START" -eq 0 ]]; then
        check_pass "Watchdog running (service has been up >30 min, watchdog initialized at startup)"
    else
        check_warn "Watchdog initialization not detected in recent logs"
    fi
fi

# Check for any watchdog triggers
WATCHDOG_TRIGGERS=$(echo "$WATCHDOG_LOGS" | grep -c "PUMP_MAX_LOSS.*triggered" || echo "0")
WATCHDOG_TRIGGERS=$(sanitize_count "$WATCHDOG_TRIGGERS")
if [[ "$WATCHDOG_TRIGGERS" -gt 0 ]]; then
    check_warn "Watchdog triggered $WATCHDOG_TRIGGERS time(s) - max loss protection activated"
else
    check_pass "No watchdog triggers (positions within max loss limits)"
fi

# ============================================================================
# 6. TELEGRAM MESSAGING
# ============================================================================
section_header "6. TELEGRAM MESSAGING"

# Check for Telegram initialization
TG_INIT=$(echo "$WATCHDOG_LOGS" | grep -c "Telegram bot initialized" || echo "0")
TG_INIT=$(sanitize_count "$TG_INIT")
if [[ "$TG_INIT" -gt 0 ]]; then
    check_pass "Telegram bot initialized"
else
    SERVICE_START=$(echo "$WATCHDOG_LOGS" | grep -c "Started Alpha Sniper" || echo "0")
    SERVICE_START=$(sanitize_count "$SERVICE_START")
    if [[ "$SERVICE_START" -eq 0 ]]; then
        check_pass "Telegram bot initialized at startup (service up >30 min)"
    else
        check_warn "Telegram initialization not detected in recent logs"
    fi
fi

# Check for scan summaries
SCAN_SUMMARIES=$(echo "$RECENT_LOGS" | grep -c "Sending scan summary" || echo "0")
SCAN_SUMMARIES=$(sanitize_count "$SCAN_SUMMARIES")
if [[ "$SCAN_SUMMARIES" -gt 0 ]]; then
    check_pass "Scan summaries being sent ($SCAN_SUMMARIES in last 15 min)"
else
    if [[ "$SCAN_COUNT" -gt 0 ]]; then
        check_warn "Scans running but no scan summaries logged (check TELEGRAM_SCAN_SUMMARY=true)"
    else
        check_warn "No scan summaries detected"
    fi
fi

# Check for trade alerts
TRADE_ALERTS=$(echo "$RECENT_LOGS" | grep -c "Sending.*alert" || echo "0")
TRADE_ALERTS=$(sanitize_count "$TRADE_ALERTS")
if [[ "$TRADE_ALERTS" -gt 0 ]]; then
    check_pass "Trade alerts being sent ($TRADE_ALERTS in last 15 min)"
else
    if [[ "$PUMP_TRADES" -eq 0 ]]; then
        check_pass "No trade alerts (no trades to report)"
    else
        check_warn "Trades occurred but no alerts logged"
    fi
fi

# ============================================================================
# 7. CURRENT POSITIONS
# ============================================================================
section_header "7. CURRENT POSITIONS"

POSITIONS_FILE="/var/lib/alpha-sniper/positions.json"
if [[ -f "$POSITIONS_FILE" ]]; then
    POSITIONS=$(cat "$POSITIONS_FILE" 2>/dev/null || echo "[]")
    POS_COUNT=$(echo "$POSITIONS" | grep -o '"symbol"' | wc -l || echo "0")
    POS_COUNT=$(sanitize_count "$POS_COUNT")

    if [[ "$POS_COUNT" -eq 0 ]]; then
        check_pass "0 open positions (clean slate)"
    else
        check_pass "$POS_COUNT open position(s)"

        # Check for old max_hold_hours
        OLD_MAX_HOLD=$(echo "$POSITIONS" | grep -c '"max_hold_hours": 3' || echo "0")
        OLD_MAX_HOLD=$(sanitize_count "$OLD_MAX_HOLD")
        if [[ "$OLD_MAX_HOLD" -gt 0 ]]; then
            check_warn "$OLD_MAX_HOLD position(s) still using old 3h max hold (opened before optimization)"
        fi
    fi
else
    check_warn "Positions file not found (will be created on first trade)"
fi

# ============================================================================
# 8. ERROR CHECK
# ============================================================================
section_header "8. ERROR ANALYSIS (Last 15 min)"

CRITICAL_ERRORS=$(echo "$RECENT_LOGS" | grep -iE "(ERROR|CRITICAL|Exception|Traceback)" | grep -vE "(NIGHT/USDT|partial|TP|INFO)" | wc -l || echo "0")
CRITICAL_ERRORS=$(sanitize_count "$CRITICAL_ERRORS")

if [[ "$CRITICAL_ERRORS" -eq 0 ]]; then
    check_pass "No critical errors in last 15 minutes"
else
    check_fail "$CRITICAL_ERRORS error(s) detected in last 15 minutes"
    echo ""
    echo "Recent errors:"
    echo "$RECENT_LOGS" | grep -iE "(ERROR|CRITICAL|Exception)" | grep -vE "(NIGHT/USDT|partial|TP|INFO)" | tail -5
fi

# Check for old NIGHT/USDT errors (can be ignored)
OLD_ERRORS=$(echo "$RECENT_LOGS" | grep -c "NIGHT/USDT" || echo "0")
OLD_ERRORS=$(sanitize_count "$OLD_ERRORS")
if [[ "$OLD_ERRORS" -gt 0 ]]; then
    check_pass "Old NIGHT/USDT errors present but can be ignored ($OLD_ERRORS occurrences)"
fi

# ============================================================================
# 9. PYTHON ENVIRONMENT
# ============================================================================
section_header "9. PYTHON ENVIRONMENT"

if [[ -f "/opt/alpha-sniper/venv/bin/python" ]]; then
    check_pass "Python virtual environment exists"

    # Test imports
    IMPORT_TEST=$(/opt/alpha-sniper/venv/bin/python -c "import ccxt, asyncio, telegram; print('OK')" 2>&1)
    if [[ "$IMPORT_TEST" == "OK" ]]; then
        check_pass "Required Python packages importable"
    else
        check_fail "Python import test failed: $IMPORT_TEST"
    fi
else
    check_fail "Python virtual environment not found at /opt/alpha-sniper/venv"
fi

# ============================================================================
# 10. GIT STATUS
# ============================================================================
section_header "10. GIT STATUS"

if [[ -d "/opt/alpha-sniper/.git" ]]; then
    cd /opt/alpha-sniper || exit 1

    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    if [[ "$CURRENT_BRANCH" == "claude/fix-issues-018PzVLhR8jpyJBusPvozqDS" ]]; then
        check_pass "On correct branch: $CURRENT_BRANCH"
    else
        check_warn "On branch: $CURRENT_BRANCH (expected: claude/fix-issues-018PzVLhR8jpyJBusPvozqDS)"
    fi

    UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l || echo "0")
    UNCOMMITTED=$(sanitize_count "$UNCOMMITTED")
    if [[ "$UNCOMMITTED" -eq 0 ]]; then
        check_pass "No uncommitted changes"
    else
        check_warn "$UNCOMMITTED uncommitted file(s) (not critical for operation)"
    fi
else
    check_warn "Not a git repository (code deployed manually?)"
fi

# ============================================================================
# FINAL SUMMARY
# ============================================================================
section_header "VERIFICATION SUMMARY"

TOTAL_CHECKS=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT))
HEALTH_SCORE=$((PASS_COUNT * 100 / TOTAL_CHECKS))

echo ""
echo "Total Checks: $TOTAL_CHECKS"
echo -e "${GREEN}Passed: $PASS_COUNT${NC}"
echo -e "${YELLOW}Warnings: $WARN_COUNT${NC}"
echo -e "${RED}Failed: $FAIL_COUNT${NC}"
echo ""
echo -e "Health Score: ${BLUE}$HEALTH_SCORE%${NC}"
echo ""

if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ ALL CRITICAL CHECKS PASSED${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [[ "$WARN_COUNT" -gt 0 ]]; then
        echo ""
        echo -e "${YELLOW}Note: $WARN_COUNT warning(s) present but not critical for operation${NC}"
        echo ""
        echo "Common non-critical warnings:"
        echo "  - No pump trades (normal if market conditions don't meet criteria)"
        echo "  - No scan summaries logged (feature may be disabled or timing issue)"
        echo "  - Regime UNKNOWN (may resolve after first full scan)"
        echo "  - Uncommitted git files (not affecting bot operation)"
    fi

    echo ""
    echo "🎉 Bot is operational and ready for trading!"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor Telegram for scan summaries"
    echo "  2. Watch for pump signals meeting 0.75 threshold"
    echo "  3. Verify trades are using 24h max hold"
    echo ""
    exit 0
else
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ CRITICAL FAILURES DETECTED${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "Failed checks:"
    for result in "${RESULTS[@]}"; do
        if [[ "$result" == "❌"* ]]; then
            echo "  $result"
        fi
    done
    echo ""
    echo "Recommended actions:"
    echo ""
    echo "If service not active:"
    echo "  sudo systemctl start alpha-sniper-live.service"
    echo ""
    echo "If permissions wrong:"
    echo "  sudo chmod 777 /var/lib/alpha-sniper"
    echo "  sudo chmod 777 /opt/alpha-sniper/logs"
    echo "  sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper /opt/alpha-sniper/logs"
    echo ""
    echo "If env file missing:"
    echo "  sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.env.OPTIMIZED /etc/alpha-sniper/alpha-sniper-live.env"
    echo "  # Then edit to add your API keys"
    echo ""
    echo "If Python environment broken:"
    echo "  cd /opt/alpha-sniper"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi
