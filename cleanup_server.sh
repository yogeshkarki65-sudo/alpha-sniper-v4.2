#!/bin/bash
# Server Cleanup Script for Alpha Sniper
# Removes unnecessary files and old databases
# Usage: bash cleanup_server.sh

set -e

echo "=========================================="
echo "  Alpha Sniper Server Cleanup"
echo "=========================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backup directory
BACKUP_DIR="/opt/alpha-sniper/backups/cleanup_$(date +%Y%m%d_%H%M%S)"

# Function to confirm action
confirm() {
    read -p "$1 (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

echo "This script will:"
echo "  1. Archive old alpha.db database (if exists)"
echo "  2. Remove hardening documentation (already applied)"
echo "  3. Remove duplicate/unused scripts"
echo "  4. Keep only essential files"
echo ""

if ! confirm "Continue with cleanup?"; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# 1. Handle old database
echo ""
echo -e "${YELLOW}[1/4] Checking for old database...${NC}"
if [ -f "/opt/alpha-sniper/data/alpha.db" ]; then
    echo "  Found old alpha.db (last used: $(stat -c %y /opt/alpha-sniper/data/alpha.db | cut -d' ' -f1))"
    if confirm "  Archive old alpha.db to backup directory?"; then
        mv /opt/alpha-sniper/data/alpha.db "$BACKUP_DIR/alpha.db"
        echo -e "  ${GREEN}✓${NC} Archived to $BACKUP_DIR/alpha.db"
    else
        echo "  Skipped"
    fi
else
    echo "  No old alpha.db found"
fi

# 2. Archive hardening docs
echo ""
echo -e "${YELLOW}[2/4] Archiving hardening documentation...${NC}"
cd /opt/alpha-sniper/alpha-sniper

HARDENING_FILES=(
    "README_HARDENING.md"
    "HARDENING_SUMMARY.md"
    "SIMPLE_HARDENING.md"
    "MIGRATION_NOTES.md"
    "ROLLBACK.md"
    "PATCHES.diff"
    "verification_script.sh"
)

for file in "${HARDENING_FILES[@]}"; do
    if [ -f "$file" ]; then
        mv "$file" "$BACKUP_DIR/" 2>/dev/null || true
        echo "  ${GREEN}✓${NC} Archived $file"
    fi
done

# 3. Remove duplicate scripts
echo ""
echo -e "${YELLOW}[3/4] Checking for duplicate/unused scripts...${NC}"

# Keep check_bot_health.sh, remove others if confirmed
OPTIONAL_SCRIPTS=(
    "quick_stats_from_logs.sh"
)

for script in "${OPTIONAL_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "  Found: $script"
        if confirm "    Remove $script? (functionality covered by check_performance.sh)"; then
            mv "$script" "$BACKUP_DIR/" 2>/dev/null || true
            echo "  ${GREEN}✓${NC} Archived $script"
        else
            echo "  Kept $script"
        fi
    fi
done

# 4. Summary
echo ""
echo -e "${YELLOW}[4/4] Cleanup Summary${NC}"
echo ""
echo "Active Database:"
ls -lh /opt/alpha-sniper/data/alpha_async.db 2>/dev/null || echo "  Warning: alpha_async.db not found"

echo ""
echo "Essential Scripts (kept):"
echo "  - check_bot_health.sh (quick health check)"
echo "  - check_performance.sh (detailed performance analysis)"

echo ""
echo "Archived Files:"
ls -lh "$BACKUP_DIR" | tail -n +2 || echo "  No files archived"

echo ""
echo -e "${GREEN}=========================================="
echo "  Cleanup Complete!"
echo "==========================================${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""
echo "To restore archived files:"
echo "  cp $BACKUP_DIR/[filename] /opt/alpha-sniper/alpha-sniper/"
echo ""
echo "To permanently delete backups (after verification):"
echo "  rm -rf $BACKUP_DIR"
echo ""
