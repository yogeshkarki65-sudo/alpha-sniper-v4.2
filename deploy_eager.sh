#!/bin/bash
###############################################################################
# EAGER Breakout Feature - One-Shot Deployment Script
# Branch: claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
# Usage: sudo bash deploy_eager.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_PATH="/opt/alpha-sniper"
BRANCH="claude/fix-issues-018PzVLhR8jpyJBusPvozqDS"
SERVICE_NAME="alpha-sniper-async.service"
VENV_PATH="${REPO_PATH}/venv"

###############################################################################
# Helper Functions
###############################################################################

print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

###############################################################################
# Main Deployment Steps
###############################################################################

main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     EAGER Breakout Feature - Deployment Script                ║"
    echo "║     Branch: ${BRANCH}                                          ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    # Step 1: Check prerequisites
    print_step "Step 1: Checking prerequisites..."
    check_root

    if [ ! -d "$REPO_PATH" ]; then
        print_error "Repository path not found: $REPO_PATH"
        exit 1
    fi

    cd "$REPO_PATH"
    print_info "Working directory: $(pwd)"
    echo ""

    # Step 2: Backup current state
    print_step "Step 2: Creating backup..."
    BACKUP_DIR="/tmp/alpha-sniper-backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup key files
    cp -r ./data "$BACKUP_DIR/" 2>/dev/null || print_warning "No data dir to backup"
    cp .env "$BACKUP_DIR/" 2>/dev/null || print_warning "No .env to backup"

    # Get current commit
    CURRENT_COMMIT=$(git rev-parse HEAD)
    echo "$CURRENT_COMMIT" > "$BACKUP_DIR/previous_commit.txt"

    print_info "Backup created at: $BACKUP_DIR"
    print_info "Previous commit: $CURRENT_COMMIT"
    echo ""

    # Step 3: Stop service
    print_step "Step 3: Stopping service..."
    systemctl stop "$SERVICE_NAME" || print_warning "Service was not running"
    sleep 2
    echo ""

    # Step 4: Pull latest code
    print_step "Step 4: Pulling latest code from branch..."
    print_info "Branch: $BRANCH"

    # Fetch latest
    git fetch origin "$BRANCH" || {
        print_error "Failed to fetch from remote"
        exit 1
    }

    # Show what will change
    echo ""
    print_info "Changes to be pulled:"
    git log HEAD..origin/"$BRANCH" --oneline --decorate --graph | head -5 || true
    echo ""

    # Pull the code
    git pull origin "$BRANCH" || {
        print_error "Failed to pull from branch"
        exit 1
    }

    NEW_COMMIT=$(git rev-parse HEAD)
    print_info "Updated to commit: $NEW_COMMIT"
    echo ""

    # Step 5: Validate Python syntax
    print_step "Step 5: Validating Python syntax..."

    FILES_TO_CHECK=(
        "alpha-sniper/config/settings.py"
        "alpha-sniper/scanner/runner.py"
        "app_async.py"
    )

    for file in "${FILES_TO_CHECK[@]}"; do
        if [ -f "$file" ]; then
            python3 -m py_compile "$file" && {
                print_info "✓ $file"
            } || {
                print_error "✗ $file - Syntax error!"
                exit 1
            }
        else
            print_warning "File not found: $file"
        fi
    done
    echo ""

    # Step 6: Test configuration loading
    print_step "Step 6: Testing configuration..."

    # Activate venv if it exists
    if [ -d "$VENV_PATH" ]; then
        source "$VENV_PATH/bin/activate"
        print_info "Virtual environment activated"
    fi

    # Test Settings import
    python3 <<EOF
import sys
sys.path.insert(0, '/opt/alpha-sniper')
try:
    from alpha_sniper.config.settings import Settings
    s = Settings()
    print(f"✓ Settings loaded successfully")
    print(f"  EAGER_ENABLE: {s.EAGER_ENABLE}")
    print(f"  EAGER_VSPIKE_MIN: {s.EAGER_VSPIKE_MIN}")
    print(f"  EAGER_MAX_NEG_RET5M: {s.EAGER_MAX_NEG_RET5M}")
    print(f"  EAGER_SL_PCT: {s.EAGER_SL_PCT}")
    print(f"  EAGER_TP_PCT: {s.EAGER_TP_PCT}")
    print(f"  EAGER_ONLY_LIVE_TEST: {s.EAGER_ONLY_LIVE_TEST}")
    print(f"  SNAPSHOT_DEPTH_TOPK: {s.SNAPSHOT_DEPTH_TOPK}")
except Exception as e:
    print(f"✗ Failed to load settings: {e}")
    sys.exit(1)
EOF

    if [ $? -ne 0 ]; then
        print_error "Configuration test failed"
        exit 1
    fi
    echo ""

    # Step 7: Fix permissions
    print_step "Step 7: Fixing permissions..."
    chown -R ubuntu:ubuntu /opt/alpha-sniper/data 2>/dev/null || true
    chmod 664 /opt/alpha-sniper/data/*.json 2>/dev/null || true
    print_info "Permissions updated"
    echo ""

    # Step 8: Check LIVE_TEST_MODE setting
    print_step "Step 8: Checking LIVE_TEST_MODE..."
    if grep -q "LIVE_TEST_MODE=true" .env 2>/dev/null; then
        print_warning "LIVE_TEST_MODE=true (EAGER will run in test mode)"
        print_info "EAGER trades will be logged but not executed for real"
    elif grep -q "LIVE_TEST_MODE=false" .env 2>/dev/null; then
        print_warning "LIVE_TEST_MODE=false (EAGER will execute REAL trades)"
        print_info "EAGER is set to EAGER_ONLY_LIVE_TEST=True by default"
        print_warning "This means EAGER will NOT run unless you override EAGER_ONLY_LIVE_TEST=False"
    else
        print_warning "LIVE_TEST_MODE not found in .env (using default)"
    fi
    echo ""

    # Step 9: Show current overrides
    print_step "Step 9: Current runtime overrides..."
    if [ -f "data/overrides.json" ]; then
        python3 -c "import json; print(json.dumps(json.load(open('data/overrides.json')), indent=2))" || {
            print_warning "Could not parse overrides.json"
        }
    else
        print_info "No overrides.json found (will use defaults)"
    fi
    echo ""

    # Step 10: Start service
    print_step "Step 10: Starting service..."
    systemctl start "$SERVICE_NAME" || {
        print_error "Failed to start service"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager
        exit 1
    }

    sleep 3

    # Check service status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_info "✓ Service is running"
    else
        print_error "✗ Service failed to start"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager
        exit 1
    fi
    echo ""

    # Step 11: Monitor initial logs
    print_step "Step 11: Checking initial logs..."
    print_info "Looking for EAGER and AutoTune messages..."
    echo ""

    journalctl -u "$SERVICE_NAME" -n 50 --no-pager | grep -E "EAGER|FLOW_TOGGLE|AutoTune|EARLY_TOP" || {
        print_warning "No EAGER/AutoTune logs yet (may appear after first scan)"
    }
    echo ""

    # Final summary
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                  Deployment Complete! ✓                        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    print_info "Summary:"
    echo "  • Previous commit: $CURRENT_COMMIT"
    echo "  • New commit: $NEW_COMMIT"
    echo "  • Backup location: $BACKUP_DIR"
    echo "  • Service status: $(systemctl is-active $SERVICE_NAME)"
    echo ""

    print_info "Next Steps:"
    echo ""
    echo "  1. Monitor logs for EAGER activity:"
    echo "     ${YELLOW}sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered -E 'EAGER|EARLY_TOP'${NC}"
    echo ""
    echo "  2. Watch for trades:"
    echo "     ${YELLOW}sudo journalctl -u $SERVICE_NAME -f | grep --line-buffered 'OPENED\|CLOSED'${NC}"
    echo ""
    echo "  3. Check service status:"
    echo "     ${YELLOW}sudo systemctl status $SERVICE_NAME${NC}"
    echo ""
    echo "  4. View current overrides:"
    echo "     ${YELLOW}python scripts/overrides_cli.py show${NC}"
    echo ""
    echo "  5. Adjust EAGER settings (optional):"
    echo "     ${YELLOW}python scripts/overrides_cli.py set --key EAGER_VSPIKE_MIN --value 2.5${NC}"
    echo ""

    print_warning "IMPORTANT: EAGER is currently gated by EAGER_ONLY_LIVE_TEST=True"
    print_info "To enable EAGER in production, run:"
    echo "  ${YELLOW}python scripts/overrides_cli.py set --key EAGER_ONLY_LIVE_TEST --value false${NC}"
    echo "  ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}"
    echo ""

    print_info "To rollback to previous version:"
    echo "  ${YELLOW}cd /opt/alpha-sniper${NC}"
    echo "  ${YELLOW}git reset --hard $CURRENT_COMMIT${NC}"
    echo "  ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}"
    echo ""
}

###############################################################################
# Execute Main
###############################################################################

main "$@"
