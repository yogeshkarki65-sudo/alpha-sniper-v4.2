#!/bin/bash
################################################################################
# Alpha Sniper v4.2.3 - Production Deployment Script with Rollback
#
# This script safely deploys code changes to production:
# 1. Pre-flight checks (git status, network)
# 2. Create rollback point
# 3. Pull latest code from git
# 4. Install dependencies
# 5. Run syntax checks
# 6. Run smoke tests (market data only - no orders)
# 7. Restart service
# 8. Verify health (service active + successful scan)
# 9. Rollback on failure
#
# Usage:
#   scripts/deploy.sh [branch-or-commit]
#
# Examples:
#   scripts/deploy.sh main
#   scripts/deploy.sh claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
#   scripts/deploy.sh a7d79f86
#
# Environment:
#   Reads from scripts/deploy_config.env (create from deploy_config_example.env)
#
# Exit codes:
#   0 = Deployment successful
#   1 = Deployment failed (rollback attempted)
#   2 = Pre-flight check failed (no changes made)
################################################################################

set -euo pipefail  # Fail fast

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load deployment config
CONFIG_FILE="$SCRIPT_DIR/deploy_config.env"
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${BLUE}Loading deployment config from: $CONFIG_FILE${NC}"
    source "$CONFIG_FILE"
else
    echo -e "${YELLOW}⚠ No deploy_config.env found, using defaults${NC}"
fi

# Default configuration (override in deploy_config.env)
SERVICE_NAME="${SERVICE_NAME:-alpha-sniper-live.service}"
LOG_FILE="${LOG_FILE:-/opt/alpha-sniper/logs/bot.log}"
VENV_PATH="${VENV_PATH:-$REPO_ROOT/venv}"
PYTHON_BIN="${PYTHON_BIN:-$VENV_PATH/bin/python}"
PIP_BIN="${PIP_BIN:-$VENV_PATH/bin/pip}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-60}"  # seconds
ROLLBACK_ENABLED="${ROLLBACK_ENABLED:-true}"

# Rollback state
ROLLBACK_COMMIT=""
ORIGINAL_BRANCH=""

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo -e "${BLUE}===================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===================================================================${NC}"
}

# Rollback function
rollback() {
    if [ "$ROLLBACK_ENABLED" != "true" ]; then
        log_warning "Rollback disabled, skipping"
        return 1
    fi

    log_step "ROLLBACK: Reverting to previous version"

    cd "$REPO_ROOT"

    # Restore git state
    if [ -n "$ROLLBACK_COMMIT" ]; then
        log_info "Restoring git commit: $ROLLBACK_COMMIT"
        git checkout -f "$ROLLBACK_COMMIT" || {
            log_error "Failed to checkout rollback commit"
            return 1
        }

        if [ -n "$ORIGINAL_BRANCH" ]; then
            log_info "Restoring branch: $ORIGINAL_BRANCH"
            git checkout "$ORIGINAL_BRANCH" 2>/dev/null || log_warning "Could not restore original branch"
        fi
    fi

    # Reinstall dependencies (in case they changed)
    log_info "Reinstalling dependencies..."
    if [ -f "$REPO_ROOT/requirements.txt" ]; then
        "$PIP_BIN" install -q -r "$REPO_ROOT/requirements.txt" || log_warning "Dependency rollback failed"
    fi

    # Restart service
    log_info "Restarting service after rollback..."
    sudo systemctl restart "$SERVICE_NAME" || {
        log_error "Failed to restart service during rollback"
        return 1
    }

    # Wait for service
    sleep 3

    # Check service
    if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Service active after rollback"
        return 0
    else
        log_error "Service failed to start after rollback"
        return 1
    fi
}

# Cleanup on exit
cleanup() {
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Deployment failed with exit code $exit_code"
        if [ "$ROLLBACK_ENABLED" == "true" ]; then
            rollback || log_error "Rollback also failed - manual intervention required"
        fi
    fi
}

trap cleanup EXIT

# Main deployment
main() {
    TARGET_REF="${1:-main}"

    log_step "🚀 ALPHA SNIPER v4.2.3 - PRODUCTION DEPLOYMENT"

    log_info "Target: $TARGET_REF"
    log_info "Service: $SERVICE_NAME"
    log_info "Repo: $REPO_ROOT"
    echo ""

    # ===================================================================
    # PRE-FLIGHT CHECKS
    # ===================================================================
    log_step "1️⃣ PRE-FLIGHT CHECKS"

    cd "$REPO_ROOT"

    # Check if git repo
    if [ ! -d ".git" ]; then
        log_error "Not a git repository: $REPO_ROOT"
        exit 2
    fi
    log_success "Git repository OK"

    # Check network (can reach GitHub)
    log_info "Checking network connectivity..."
    if ! git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
        log_error "Cannot reach git remote (network issue or auth problem)"
        exit 2
    fi
    log_success "Network connectivity OK"

    # Check service exists
    if ! systemctl list-units --full --all | grep -q "$SERVICE_NAME"; then
        log_warning "Service $SERVICE_NAME not found, will skip service operations"
    else
        log_success "Service $SERVICE_NAME found"
    fi

    # Check Python environment
    if [ ! -f "$PYTHON_BIN" ]; then
        log_error "Python binary not found: $PYTHON_BIN"
        log_error "Create venv or update PYTHON_BIN in deploy_config.env"
        exit 2
    fi
    log_success "Python environment OK: $PYTHON_BIN"

    # ===================================================================
    # CREATE ROLLBACK POINT
    # ===================================================================
    log_step "2️⃣ CREATE ROLLBACK POINT"

    ROLLBACK_COMMIT=$(git rev-parse HEAD)
    ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

    log_info "Current commit: $ROLLBACK_COMMIT"
    log_info "Current branch: $ORIGINAL_BRANCH"
    log_success "Rollback point saved"

    # ===================================================================
    # STOP SERVICE
    # ===================================================================
    log_step "3️⃣ STOP SERVICE"

    if systemctl list-units --full --all | grep -q "$SERVICE_NAME"; then
        log_info "Stopping service: $SERVICE_NAME"
        sudo systemctl stop "$SERVICE_NAME" || {
            log_error "Failed to stop service"
            exit 1
        }
        log_success "Service stopped"
    else
        log_info "Service not running, skipping stop"
    fi

    # ===================================================================
    # PULL LATEST CODE
    # ===================================================================
    log_step "4️⃣ PULL LATEST CODE"

    log_info "Fetching from origin..."
    git fetch origin || {
        log_error "Git fetch failed"
        exit 1
    }

    log_info "Checking out: $TARGET_REF"
    git checkout "$TARGET_REF" || {
        log_error "Git checkout failed"
        exit 1
    }

    # If it's a branch, pull latest
    if git show-ref --verify --quiet "refs/heads/$TARGET_REF"; then
        log_info "Pulling latest changes for branch: $TARGET_REF"
        git pull origin "$TARGET_REF" || {
            log_error "Git pull failed"
            exit 1
        }
    fi

    NEW_COMMIT=$(git rev-parse HEAD)
    log_success "Code updated to: $NEW_COMMIT"

    # Show changes
    if [ "$ROLLBACK_COMMIT" != "$NEW_COMMIT" ]; then
        log_info "Changes deployed:"
        git log --oneline "$ROLLBACK_COMMIT".."$NEW_COMMIT" | head -5
    else
        log_info "No new commits (already at target)"
    fi

    # ===================================================================
    # INSTALL DEPENDENCIES
    # ===================================================================
    log_step "5️⃣ INSTALL DEPENDENCIES"

    if [ -f "$REPO_ROOT/requirements.txt" ]; then
        log_info "Installing Python dependencies..."
        "$PIP_BIN" install -q -r "$REPO_ROOT/requirements.txt" || {
            log_error "Failed to install dependencies"
            exit 1
        }
        log_success "Dependencies installed"
    else
        log_info "No requirements.txt found, skipping"
    fi

    # ===================================================================
    # SYNTAX CHECKS
    # ===================================================================
    log_step "6️⃣ SYNTAX CHECKS"

    log_info "Compiling Python files..."
    "$PYTHON_BIN" -m compileall -q "$REPO_ROOT/alpha-sniper" || {
        log_error "Python syntax errors detected"
        exit 1
    }
    log_success "Syntax checks passed"

    # ===================================================================
    # SMOKE TESTS
    # ===================================================================
    log_step "7️⃣ SMOKE TESTS"

    SMOKE_TEST_SCRIPT="$REPO_ROOT/scripts/smoke_market_data.py"

    if [ -f "$SMOKE_TEST_SCRIPT" ]; then
        log_info "Running smoke tests (market data only, no orders)..."
        "$PYTHON_BIN" "$SMOKE_TEST_SCRIPT" || {
            log_error "Smoke tests FAILED"
            log_error "Review smoke test output above for details"
            exit 1
        }
        log_success "Smoke tests PASSED"
    else
        log_warning "Smoke test script not found, skipping: $SMOKE_TEST_SCRIPT"
    fi

    # ===================================================================
    # RESTART SERVICE
    # ===================================================================
    log_step "8️⃣ RESTART SERVICE"

    if systemctl list-units --full --all | grep -q "$SERVICE_NAME"; then
        log_info "Starting service: $SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME" || {
            log_error "Failed to start service"
            exit 1
        }
        sleep 3
        log_success "Service started"
    else
        log_info "Service not configured, skipping restart"
    fi

    # ===================================================================
    # HEALTH CHECK
    # ===================================================================
    log_step "9️⃣ HEALTH CHECK"

    if systemctl list-units --full --all | grep -q "$SERVICE_NAME"; then
        # Check 1: Service is active
        log_info "Verifying service is active..."
        if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
            log_error "Service is not active"
            sudo systemctl status "$SERVICE_NAME" --no-pager || true
            exit 1
        fi
        log_success "Service is active"

        # Check 2: Look for successful scan in logs
        log_info "Verifying bot health (waiting max ${HEALTH_CHECK_TIMEOUT}s for successful scan)..."

        # Wait for "New cycle" or "Scan completed" in logs
        START_TIME=$(date +%s)
        SUCCESS=false

        while true; do
            if tail -100 "$LOG_FILE" 2>/dev/null | grep -q -E "(New cycle|Scan completed|Processing.*signals)"; then
                SUCCESS=true
                break
            fi

            ELAPSED=$(($(date +%s) - START_TIME))
            if [ $ELAPSED -ge $HEALTH_CHECK_TIMEOUT ]; then
                break
            fi

            sleep 2
        done

        if [ "$SUCCESS" = true ]; then
            log_success "Bot health check PASSED (scan activity detected)"
        else
            log_warning "Bot health check TIMEOUT (no scan activity in ${HEALTH_CHECK_TIMEOUT}s)"
            log_warning "Bot may still be initializing - check logs manually"
            log_info "Recent logs:"
            tail -20 "$LOG_FILE" 2>/dev/null || echo "Cannot read log file"
        fi

        # Show service status
        log_info "Service status:"
        sudo systemctl status "$SERVICE_NAME" --no-pager | head -15
    else
        log_info "Service not configured, skipping health check"
    fi

    # ===================================================================
    # SUCCESS
    # ===================================================================
    log_step "✅ DEPLOYMENT SUCCESSFUL"

    echo ""
    log_success "Deployed: $NEW_COMMIT"
    log_success "Service: $SERVICE_NAME is running"

    echo ""
    log_info "📊 Monitor logs:"
    log_info "   tail -f $LOG_FILE"

    echo ""
    log_info "🔍 Check service:"
    log_info "   sudo systemctl status $SERVICE_NAME"

    echo ""
    log_info "🛠️  Rollback if needed:"
    log_info "   git checkout $ROLLBACK_COMMIT"
    log_info "   sudo systemctl restart $SERVICE_NAME"

    echo ""
    log_step "✅ DEPLOYMENT COMPLETE"

    return 0
}

# Run main
main "$@"
