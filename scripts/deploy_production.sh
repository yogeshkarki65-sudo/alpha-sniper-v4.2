#!/bin/bash
#
# Alpha Sniper v4.2 - Production Deployment Script
#
# Deploys code to production with:
# - Systemd unit update
# - Environment validation
# - Service restart
# - Health verification
#
# Usage: bash scripts/deploy_production.sh [branch]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="/opt/alpha-sniper"
SERVICE_NAME="alpha-sniper-live.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
ENV_FILE="${REPO_ROOT}/alpha-sniper/.env"
UNIT_FILE="${REPO_ROOT}/systemd/alpha-sniper-live.service"
BRANCH="${1:-claude/fix-issues-018PzVLhR8jpyJBusPvozqDS}"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo ""
    echo "==================================================================="
    echo "$1"
    echo "==================================================================="
}

# Check if running as correct user
if [ "$EUID" -eq 0 ]; then
    log_error "Do not run this script as root. Run as ubuntu user and use sudo when needed."
    exit 1
fi

log_step "🚀 ALPHA SNIPER v4.2 - PRODUCTION DEPLOYMENT"
log_info "Branch: ${BRANCH}"
log_info "Repository: ${REPO_ROOT}"
log_info "Service: ${SERVICE_NAME}"
echo ""

# ===================================================================
# 1. STOP SERVICE
# ===================================================================
log_step "1️⃣ STOPPING SERVICE"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log_info "Stopping ${SERVICE_NAME}..."
    sudo systemctl stop "${SERVICE_NAME}"
    sleep 2
    log_info "✓ Service stopped"
else
    log_info "Service not running"
fi

# ===================================================================
# 2. BACKUP CURRENT STATE
# ===================================================================
log_step "2️⃣ CREATING BACKUP"

BACKUP_DIR="${HOME}/backups/deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${BACKUP_DIR}"

log_info "Backing up current state to: ${BACKUP_DIR}"

# Backup .env
if [ -f "${ENV_FILE}" ]; then
    cp "${ENV_FILE}" "${BACKUP_DIR}/env.backup"
    log_info "✓ .env backed up"
fi

# Backup current commit
cd "${REPO_ROOT}"
git rev-parse HEAD > "${BACKUP_DIR}/commit.txt"
git branch > "${BACKUP_DIR}/branch.txt"
log_info "✓ Git state backed up"

# ===================================================================
# 3. UPDATE CODE FROM GIT
# ===================================================================
log_step "3️⃣ UPDATING CODE"

cd "${REPO_ROOT}"

log_info "Fetching latest changes..."
git fetch origin

log_info "Checking out branch: ${BRANCH}"
git checkout "${BRANCH}"

log_info "Pulling latest code..."
git pull origin "${BRANCH}"

CURRENT_COMMIT=$(git rev-parse HEAD)
log_info "✓ Updated to commit: ${CURRENT_COMMIT}"

git log -1 --oneline

# ===================================================================
# 4. UPDATE SYSTEMD UNIT
# ===================================================================
log_step "4️⃣ UPDATING SYSTEMD UNIT"

if [ ! -f "${UNIT_FILE}" ]; then
    log_error "Unit file not found: ${UNIT_FILE}"
    exit 1
fi

log_info "Copying systemd unit to: ${SERVICE_PATH}"
sudo cp "${UNIT_FILE}" "${SERVICE_PATH}"

log_info "Reloading systemd daemon..."
sudo systemctl daemon-reload

log_info "✓ Systemd unit updated"

# ===================================================================
# 5. VERIFY .ENV FILE
# ===================================================================
log_step "5️⃣ VERIFYING ENVIRONMENT FILE"

if [ ! -f "${ENV_FILE}" ]; then
    log_error ".env file not found: ${ENV_FILE}"
    log_error "Create ${ENV_FILE} before deploying"
    exit 1
fi

# Check for critical variables
log_info "Checking .env contains required variables..."

REQUIRED_VARS=(
    "MEXC_API_KEY"
    "MEXC_SECRET_KEY"
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_CHAT_ID"
)

MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${var}=" "${ENV_FILE}"; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    log_error "Missing required variables in .env:"
    for var in "${MISSING_VARS[@]}"; do
        log_error "  - $var"
    done
    exit 1
fi

log_info "✓ .env file validated"

# ===================================================================
# 6. INSTALL DEPENDENCIES
# ===================================================================
log_step "6️⃣ INSTALLING DEPENDENCIES"

if [ -f "${REPO_ROOT}/venv/bin/activate" ]; then
    log_info "Activating virtual environment..."
    source "${REPO_ROOT}/venv/bin/activate"

    log_info "Updating dependencies..."
    pip install --quiet --upgrade pip

    if [ -f "${REPO_ROOT}/requirements.txt" ]; then
        pip install --quiet -r "${REPO_ROOT}/requirements.txt"
    fi

    log_info "✓ Dependencies updated"
else
    log_warn "Virtual environment not found, skipping dependency install"
fi

# ===================================================================
# 7. SYNTAX CHECK
# ===================================================================
log_step "7️⃣ PYTHON SYNTAX CHECK"

log_info "Checking Python syntax..."
python -m compileall -q "${REPO_ROOT}/alpha-sniper" || {
    log_error "Python syntax errors detected"
    exit 1
}

log_info "✓ Syntax check passed"

# ===================================================================
# 8. START SERVICE
# ===================================================================
log_step "8️⃣ STARTING SERVICE"

log_info "Starting ${SERVICE_NAME}..."
sudo systemctl start "${SERVICE_NAME}"

sleep 3

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log_info "✓ Service started successfully"
else
    log_error "Service failed to start"
    sudo systemctl status "${SERVICE_NAME}" --no-pager
    exit 1
fi

# ===================================================================
# 9. VERIFY ENVIRONMENT LOADED
# ===================================================================
log_step "9️⃣ VERIFYING ENVIRONMENT LOADED"

log_info "Getting service PID..."
SERVICE_PID=$(systemctl show -p MainPID --value "${SERVICE_NAME}")

if [ -z "$SERVICE_PID" ] || [ "$SERVICE_PID" = "0" ]; then
    log_error "Could not get service PID"
    exit 1
fi

log_info "Service PID: ${SERVICE_PID}"

log_info "Checking /proc/${SERVICE_PID}/environ..."
if [ -f "/proc/${SERVICE_PID}/environ" ]; then
    # Check for some key variables
    if tr '\0' '\n' < "/proc/${SERVICE_PID}/environ" | grep -q "MEXC_API_KEY"; then
        log_info "✓ MEXC_API_KEY loaded"
    else
        log_warn "⚠ MEXC_API_KEY not found in process environment"
    fi

    if tr '\0' '\n' < "/proc/${SERVICE_PID}/environ" | grep -q "TELEGRAM_BOT_TOKEN"; then
        log_info "✓ TELEGRAM_BOT_TOKEN loaded"
    else
        log_warn "⚠ TELEGRAM_BOT_TOKEN not found in process environment"
    fi

    log_info "✓ Environment variables loaded"

    # Show all loaded variables (masked)
    echo ""
    log_info "Loaded environment variables:"
    tr '\0' '\n' < "/proc/${SERVICE_PID}/environ" | grep -E "^(MEXC|TELEGRAM|MIN|MAX|PUMP)" | sed 's/=.*/=***/' | head -20

else
    log_warn "Cannot read /proc/${SERVICE_PID}/environ"
fi

# ===================================================================
# 10. HEALTH CHECK
# ===================================================================
log_step "🔟 HEALTH CHECK"

log_info "Checking service status..."
sudo systemctl status "${SERVICE_NAME}" --no-pager | head -20

echo ""
log_info "Recent logs (last 20 lines):"
tail -20 "${REPO_ROOT}/logs/bot.log" 2>/dev/null || echo "No logs yet"

echo ""
log_info "Waiting 10s for bot to initialize..."
sleep 10

# Check for errors in recent logs
if tail -50 "${REPO_ROOT}/logs/bot.log" 2>/dev/null | grep -i -E "(error|exception|failed)" | grep -v "Failed to" | head -5; then
    log_warn "⚠ Potential errors detected in logs (review above)"
else
    log_info "✓ No obvious errors in recent logs"
fi

# ===================================================================
# DEPLOYMENT COMPLETE
# ===================================================================
log_step "✅ DEPLOYMENT COMPLETE"

echo ""
log_info "Summary:"
log_info "  Branch: ${BRANCH}"
log_info "  Commit: ${CURRENT_COMMIT}"
log_info "  Service: ${SERVICE_NAME}"
log_info "  Status: RUNNING"
log_info "  PID: ${SERVICE_PID}"
log_info "  Backup: ${BACKUP_DIR}"
echo ""
log_info "Monitor logs with:"
log_info "  tail -f ${REPO_ROOT}/logs/bot.log"
echo ""
log_info "Check service status with:"
log_info "  sudo systemctl status ${SERVICE_NAME}"
echo ""
log_info "Rollback if needed:"
log_info "  cd ${REPO_ROOT}"
log_info "  git checkout $(cat ${BACKUP_DIR}/commit.txt)"
log_info "  sudo systemctl restart ${SERVICE_NAME}"
echo ""

log_info "🎉 Deployment successful!"
