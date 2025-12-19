#!/bin/bash
# Alpha Sniper V4.2 - Comprehensive Health Check
# Checks every aspect of the bot for proper operation

set +e  # Don't exit on errors, we want to see all issues

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     ALPHA SNIPER V4.2 - COMPREHENSIVE HEALTH CHECK            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Timestamp: $(date)"
echo "Hostname: $(hostname)"
echo ""

# Track overall health
ISSUES_FOUND=0
WARNINGS_FOUND=0

# Function to print status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo "✅ $message"
            ;;
        "WARN")
            echo "⚠️  $message"
            ((WARNINGS_FOUND++))
            ;;
        "FAIL")
            echo "❌ $message"
            ((ISSUES_FOUND++))
            ;;
        "INFO")
            echo "ℹ️  $message"
            ;;
    esac
}

# ============================================================================
# 1. GIT REPOSITORY STATUS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. GIT REPOSITORY STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /opt/alpha-sniper 2>/dev/null || { print_status "FAIL" "Cannot access /opt/alpha-sniper"; exit 1; }

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
CURRENT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null)
EXPECTED_BRANCH="claude/fix-issues-018PzVLhR8jpyJBusPvozqDS"
EXPECTED_COMMIT="d514abd"

if [ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ]; then
    print_status "OK" "Branch: $CURRENT_BRANCH"
else
    print_status "FAIL" "Branch: $CURRENT_BRANCH (expected: $EXPECTED_BRANCH)"
fi

if [ "$CURRENT_COMMIT" = "$EXPECTED_COMMIT" ]; then
    print_status "OK" "Commit: $CURRENT_COMMIT (latest)"
else
    print_status "WARN" "Commit: $CURRENT_COMMIT (expected: $EXPECTED_COMMIT)"
    echo "   Latest commit message: $(git log -1 --oneline)"
fi

# Check for uncommitted changes
if git diff-index --quiet HEAD --; then
    print_status "OK" "No uncommitted changes"
else
    print_status "WARN" "Uncommitted changes detected"
    git status --short | head -5
fi

echo ""

# ============================================================================
# 2. FILE PERMISSIONS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. FILE PERMISSIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check critical directories
check_dir_perms() {
    local dir=$1
    local expected_perms=$2
    local description=$3

    if [ -d "$dir" ]; then
        actual_perms=$(stat -c "%a" "$dir")
        actual_owner=$(stat -c "%U:%G" "$dir")

        if [ "$actual_perms" = "$expected_perms" ] || [ "$actual_perms" = "777" ]; then
            print_status "OK" "$description: $dir ($actual_perms, $actual_owner)"
        else
            print_status "WARN" "$description: $dir (perms: $actual_perms, expected: $expected_perms)"
        fi
    else
        print_status "FAIL" "$description: $dir (NOT FOUND)"
    fi
}

check_dir_perms "/var/lib/alpha-sniper" "777" "State directory"
check_dir_perms "/opt/alpha-sniper/logs" "775" "Logs directory"
check_dir_perms "/opt/alpha-sniper/reports" "775" "Reports directory"
check_dir_perms "/opt/alpha-sniper/alpha-sniper" "755" "Bot code directory"

# Check critical files
check_file_perms() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        perms=$(stat -c "%a" "$file")
        owner=$(stat -c "%U:%G" "$file")
        size=$(stat -c "%s" "$file")
        print_status "OK" "$description: $file ($perms, $owner, ${size}B)"
    else
        print_status "WARN" "$description: $file (NOT FOUND)"
    fi
}

check_file_perms "/var/lib/alpha-sniper/positions.json" "Positions file"
check_file_perms "/opt/alpha-sniper/logs/bot.log" "Bot log file"
check_file_perms "/etc/alpha-sniper/alpha-sniper-live.env" "Env config file"
check_file_perms "/etc/systemd/system/alpha-sniper-live.service" "Systemd service"

# Check if ubuntu user can write to critical directories
if sudo -u ubuntu touch /var/lib/alpha-sniper/.write_test 2>/dev/null; then
    sudo rm /var/lib/alpha-sniper/.write_test
    print_status "OK" "Ubuntu user can write to /var/lib/alpha-sniper"
else
    print_status "FAIL" "Ubuntu user CANNOT write to /var/lib/alpha-sniper"
fi

if sudo -u ubuntu touch /opt/alpha-sniper/logs/.write_test 2>/dev/null; then
    sudo rm /opt/alpha-sniper/logs/.write_test
    print_status "OK" "Ubuntu user can write to /opt/alpha-sniper/logs"
else
    print_status "FAIL" "Ubuntu user CANNOT write to /opt/alpha-sniper/logs"
fi

echo ""

# ============================================================================
# 3. PYTHON ENVIRONMENT
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. PYTHON ENVIRONMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PYTHON_PATH="/opt/alpha-sniper/venv/bin/python"

if [ -f "$PYTHON_PATH" ]; then
    PYTHON_VERSION=$($PYTHON_PATH --version 2>&1)
    print_status "OK" "Python: $PYTHON_VERSION"
else
    print_status "FAIL" "Python virtualenv not found at $PYTHON_PATH"
fi

# Check critical Python modules
check_module() {
    local module=$1
    if $PYTHON_PATH -c "import $module" 2>/dev/null; then
        version=$($PYTHON_PATH -c "import $module; print(getattr($module, '__version__', 'unknown'))" 2>/dev/null)
        print_status "OK" "Module $module: $version"
    else
        print_status "FAIL" "Module $module: NOT INSTALLED"
    fi
}

check_module "ccxt"
check_module "pandas"
check_module "numpy"
check_module "requests"
check_module "asyncio"

# Validate Python syntax of main files
echo ""
echo "Validating Python syntax..."
for file in /opt/alpha-sniper/alpha-sniper/{main.py,config.py,risk_engine.py,exchange.py}; do
    if [ -f "$file" ]; then
        if $PYTHON_PATH -m py_compile "$file" 2>/dev/null; then
            print_status "OK" "Syntax valid: $(basename $file)"
        else
            print_status "FAIL" "Syntax ERROR: $(basename $file)"
        fi
    fi
done

echo ""

# ============================================================================
# 4. SYSTEMD SERVICE STATUS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. SYSTEMD SERVICE STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if systemctl is-active --quiet alpha-sniper-live.service; then
    print_status "OK" "Service is ACTIVE (running)"
else
    print_status "FAIL" "Service is NOT ACTIVE"
fi

if systemctl is-enabled --quiet alpha-sniper-live.service; then
    print_status "OK" "Service is ENABLED (auto-start)"
else
    print_status "WARN" "Service is NOT ENABLED (won't auto-start)"
fi

# Check service uptime
UPTIME=$(systemctl show alpha-sniper-live.service --property=ActiveEnterTimestamp --value)
if [ -n "$UPTIME" ]; then
    print_status "INFO" "Service started: $UPTIME"
fi

# Check for recent restarts
RESTART_COUNT=$(systemctl show alpha-sniper-live.service --property=NRestarts --value)
print_status "INFO" "Service restarts: $RESTART_COUNT"

# Check memory usage
MEM_CURRENT=$(systemctl show alpha-sniper-live.service --property=MemoryCurrent --value)
if [ "$MEM_CURRENT" != "[not set]" ] && [ -n "$MEM_CURRENT" ]; then
    MEM_MB=$((MEM_CURRENT / 1024 / 1024))
    if [ $MEM_MB -lt 1024 ]; then
        print_status "OK" "Memory usage: ${MEM_MB}MB"
    else
        print_status "WARN" "Memory usage: ${MEM_MB}MB (high)"
    fi
fi

echo ""

# ============================================================================
# 5. CONFIGURATION VALIDATION
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. CONFIGURATION VALIDATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ENV_FILE="/etc/alpha-sniper/alpha-sniper-live.env"

if [ -f "$ENV_FILE" ]; then
    print_status "OK" "Env file exists: $ENV_FILE"

    # Check critical variables
    check_var() {
        local var=$1
        local description=$2
        local value=$(grep "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")

        if [ -n "$value" ]; then
            # Mask API keys
            if [[ "$var" == *"API_KEY"* ]] || [[ "$var" == *"SECRET"* ]] || [[ "$var" == *"TOKEN"* ]]; then
                masked="${value:0:4}...${value: -4}"
                print_status "OK" "$description: $masked"
            else
                print_status "OK" "$description: $value"
            fi
        else
            print_status "WARN" "$description: NOT SET"
        fi
    }

    echo ""
    echo "Core Settings:"
    check_var "SIM_MODE" "Sim Mode"
    check_var "PUMP_ONLY" "Pump Only Mode"
    check_var "PUMP_MAX_LOSS_PCT" "Pump Max Loss"
    check_var "MAX_HOLD_HOURS_PUMP" "Max Hold Hours (Pump)"

    echo ""
    echo "API Credentials:"
    check_var "MEXC_API_KEY" "MEXC API Key"
    check_var "MEXC_SECRET_KEY" "MEXC Secret Key"
    check_var "TELEGRAM_BOT_TOKEN" "Telegram Bot Token"
    check_var "TELEGRAM_CHAT_ID" "Telegram Chat ID"

    echo ""
    echo "New Features:"
    check_var "TELEGRAM_TRADE_ALERTS" "Trade Alerts"
    check_var "TELEGRAM_SCAN_SUMMARY" "Scan Summary"
    check_var "TELEGRAM_WHY_NO_TRADE" "Why No Trade"
    check_var "SCAN_UNIVERSE_MAX" "Universe Max"

    # Check for deprecated variables
    echo ""
    echo "Deprecated Variables Check:"
    if grep -q "^HARD_STOP_PCT_PUMP=" "$ENV_FILE" 2>/dev/null; then
        print_status "WARN" "Found deprecated: HARD_STOP_PCT_PUMP (use PUMP_MAX_LOSS_PCT)"
    else
        print_status "OK" "No HARD_STOP_PCT_PUMP (good - use PUMP_MAX_LOSS_PCT)"
    fi

    if grep -q "^HARD_STOP_WATCHDOG_INTERVAL=" "$ENV_FILE" 2>/dev/null; then
        print_status "WARN" "Found deprecated: HARD_STOP_WATCHDOG_INTERVAL (use PUMP_MAX_LOSS_WATCHDOG_INTERVAL)"
    else
        print_status "OK" "No HARD_STOP_WATCHDOG_INTERVAL (good - use PUMP_MAX_LOSS_WATCHDOG_INTERVAL)"
    fi

else
    print_status "FAIL" "Env file NOT FOUND: $ENV_FILE"
fi

echo ""

# ============================================================================
# 6. RUNTIME STATUS (FROM LOGS)
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. RUNTIME STATUS (FROM LOGS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check recent errors
ERROR_COUNT=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -i "error" | grep -v "0 errors" | wc -l)
if [ $ERROR_COUNT -eq 0 ]; then
    print_status "OK" "No errors in last hour"
else
    print_status "WARN" "$ERROR_COUNT errors in last hour"
    echo "   Recent errors:"
    sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -i "error" | tail -3 | sed 's/^/   /'
fi

# Check if watchdog is running
if sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" --no-pager 2>/dev/null | grep -q "SYNTHETIC STOP WATCHDOG started"; then
    print_status "OK" "Synthetic stop watchdog is running"
else
    print_status "WARN" "Synthetic stop watchdog not detected in logs"
fi

# Check recent scan cycles
SCAN_COUNT=$(sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" --no-pager 2>/dev/null | grep -c "New cycle" || echo "0")
if [ $SCAN_COUNT -gt 0 ]; then
    print_status "OK" "Scan cycles running ($SCAN_COUNT in last 30min)"
else
    print_status "FAIL" "No scan cycles detected in last 30 minutes"
fi

# Check open positions
OPEN_POS=$(sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago" --no-pager 2>/dev/null | grep "New cycle" | tail -1 | grep -oP 'open_positions=\K[0-9]+' || echo "0")
print_status "INFO" "Current open positions: $OPEN_POS"

# Check current equity
EQUITY=$(sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago" --no-pager 2>/dev/null | grep "New cycle" | tail -1 | grep -oP 'equity=\$\K[0-9.]+' || echo "unknown")
print_status "INFO" "Current equity: \$$EQUITY"

# Check current regime
REGIME=$(sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago" --no-pager 2>/dev/null | grep "New cycle" | tail -1 | grep -oP 'regime=\K[A-Z_]+' || echo "unknown")
print_status "INFO" "Current regime: $REGIME"

echo ""

# ============================================================================
# 7. TELEGRAM CONNECTIVITY
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. TELEGRAM CONNECTIVITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if Telegram messages are being sent
TG_SENT=$(sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" --no-pager 2>/dev/null | grep -c "Message sent successfully" || echo "0")
if [ $TG_SENT -gt 0 ]; then
    print_status "OK" "Telegram messages sent: $TG_SENT in last 30min"
else
    print_status "WARN" "No Telegram messages sent in last 30 minutes"
fi

# Check for Telegram errors
TG_ERRORS=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -i "telegram" | grep -i "error\|failed" | wc -l)
if [ $TG_ERRORS -eq 0 ]; then
    print_status "OK" "No Telegram errors"
else
    print_status "WARN" "Telegram errors: $TG_ERRORS in last hour"
fi

echo ""

# ============================================================================
# 8. EXCHANGE CONNECTIVITY
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. EXCHANGE CONNECTIVITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for exchange errors
EXCH_ERRORS=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -i "mexc\|exchange" | grep -i "error\|failed" | wc -l)
if [ $EXCH_ERRORS -eq 0 ]; then
    print_status "OK" "No exchange errors"
else
    print_status "WARN" "Exchange errors: $EXCH_ERRORS in last hour"
fi

# Check if equity sync is working
EQUITY_SYNC=$(sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" --no-pager 2>/dev/null | grep -c "Equity Sync sent successfully" || echo "0")
if [ $EQUITY_SYNC -gt 0 ]; then
    print_status "OK" "Equity sync working ($EQUITY_SYNC syncs in 30min)"
else
    print_status "WARN" "No equity syncs detected in last 30 minutes"
fi

echo ""

# ============================================================================
# 9. RECENT TRADE ACTIVITY
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9. RECENT TRADE ACTIVITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check trades in last 24h
TRADES_24H=$(sudo journalctl -u alpha-sniper-live.service --since "24 hours ago" --no-pager 2>/dev/null | grep -c "Position closed" || echo "0")
print_status "INFO" "Trades (24h): $TRADES_24H"

# Check trades in last hour
TRADES_1H=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -c "Position closed" || echo "0")
print_status "INFO" "Trades (1h): $TRADES_1H"

# Check for pump trades
PUMP_TRADES=$(sudo journalctl -u alpha-sniper-live.service --since "24 hours ago" --no-pager 2>/dev/null | grep "Position" | grep -ic "pump" || echo "0")
print_status "INFO" "Pump trades (24h): $PUMP_TRADES"

# Check pump max loss triggers
PUMP_STOPS=$(sudo journalctl -u alpha-sniper-live.service --since "24 hours ago" --no-pager 2>/dev/null | grep -c "PUMP_MAX_LOSS" || echo "0")
if [ $PUMP_STOPS -eq 0 ]; then
    print_status "OK" "No pump max loss triggers (24h)"
else
    print_status "INFO" "Pump max loss triggers: $PUMP_STOPS"
fi

echo ""

# ============================================================================
# 10. NEW FEATURES STATUS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "10. NEW FEATURES STATUS (Full Telegram Messaging)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if new Telegram methods exist in code
if grep -q "send_scan_summary" /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py 2>/dev/null; then
    print_status "OK" "send_scan_summary method exists"
else
    print_status "FAIL" "send_scan_summary method NOT FOUND (need code update)"
fi

if grep -q "send_why_no_trade" /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py 2>/dev/null; then
    print_status "OK" "send_why_no_trade method exists"
else
    print_status "FAIL" "send_why_no_trade method NOT FOUND (need code update)"
fi

# Check if main.py calls these methods
if grep -q "send_scan_summary" /opt/alpha-sniper/alpha-sniper/main.py 2>/dev/null; then
    print_status "OK" "main.py calls send_scan_summary"
else
    print_status "FAIL" "main.py does NOT call send_scan_summary (need code update)"
fi

if grep -q "send_why_no_trade" /opt/alpha-sniper/alpha-sniper/main.py 2>/dev/null; then
    print_status "OK" "main.py calls send_why_no_trade"
else
    print_status "FAIL" "main.py does NOT call send_why_no_trade (need code update)"
fi

# Check if risk_engine sends trade_open notifications
if grep -q "send_trade_open" /opt/alpha-sniper/alpha-sniper/risk_engine.py 2>/dev/null; then
    print_status "OK" "risk_engine.py sends trade_open notifications"
else
    print_status "FAIL" "risk_engine.py does NOT send trade_open (need code update)"
fi

# Check for scan summaries in logs
SCAN_SUMMARIES=$(sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager 2>/dev/null | grep -c "Scan Summary" || echo "0")
if [ $SCAN_SUMMARIES -gt 0 ]; then
    print_status "OK" "Scan summaries being sent ($SCAN_SUMMARIES in last hour)"
else
    print_status "WARN" "No scan summaries in logs (feature may not be active)"
fi

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "HEALTH CHECK SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ $ISSUES_FOUND -eq 0 ] && [ $WARNINGS_FOUND -eq 0 ]; then
    echo "🎉 EXCELLENT: No issues or warnings found!"
    echo "   Bot is operating optimally."
elif [ $ISSUES_FOUND -eq 0 ]; then
    echo "✅ GOOD: No critical issues found."
    echo "⚠️  Warnings: $WARNINGS_FOUND (review recommended)"
else
    echo "❌ ISSUES FOUND: $ISSUES_FOUND critical issues"
    echo "⚠️  Warnings: $WARNINGS_FOUND"
    echo ""
    echo "ACTION REQUIRED: Review issues above and fix them."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Health check completed at $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
