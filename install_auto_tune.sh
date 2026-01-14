#!/bin/bash
# install_auto_tune.sh - Install automatic tuning as a cron job
# This sets up the auto-tuner to run every 6 hours

set -e

echo "========================================"
echo "INSTALLING AUTO-TUNE SERVICE"
echo "========================================"

# Check if script exists
if [ ! -f "/opt/alpha-sniper/auto_tune_service.sh" ]; then
    echo "ERROR: auto_tune_service.sh not found at /opt/alpha-sniper/"
    echo "Make sure the script is deployed to the production server"
    exit 1
fi

# Make sure it's executable
chmod +x /opt/alpha-sniper/auto_tune_service.sh

# Create cron job entry
# Run every 6 hours at :15 past the hour (00:15, 06:15, 12:15, 18:15)
CRON_JOB="15 */6 * * * /opt/alpha-sniper/auto_tune_service.sh '6 hours ago' >> /opt/alpha-sniper/logs/auto_tune_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "auto_tune_service.sh"; then
    echo "⚠️  Auto-tune cron job already exists"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep auto_tune
    echo ""
    read -p "Replace existing cron job? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
    # Remove old cron job
    crontab -l | grep -v "auto_tune_service.sh" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Auto-tune service installed successfully!"
echo ""
echo "Schedule: Every 6 hours (00:15, 06:15, 12:15, 18:15)"
echo "Lookback: 6 hours of data"
echo "Log file: /opt/alpha-sniper/logs/auto_tune.log"
echo "Cron log: /opt/alpha-sniper/logs/auto_tune_cron.log"
echo ""
echo "Current cron jobs:"
crontab -l | grep auto_tune || echo "  (none found)"
echo ""
echo "========================================"
echo "WHAT IT DOES:"
echo "========================================"
echo ""
echo "The auto-tuner monitors performance every 6 hours and:"
echo ""
echo "1. Low Win Rate (<25%)"
echo "   → Tightens EARLY_RET_5M_MIN by +0.2%"
echo "   → Safety: Won't exceed 3.5%"
echo ""
echo "2. Too Few Trades (cand<0.2, wr>35%)"
echo "   → Loosens EARLY_VOL_SPIKE_MIN by -0.2x"
echo "   → Safety: Won't go below 1.5x"
echo ""
echo "3. Low Open Rate (<25%)"
echo "   → Increases EAGER_EPS_PCT by +0.03%"
echo "   → Safety: Won't exceed 0.3%"
echo ""
echo "4. Good Win Rate (≥30%)"
echo "   → Scales up RISK_PER_TRADE by +0.05%"
echo "   → Safety: Won't exceed 0.5%"
echo ""
echo "========================================"
echo "MONITORING:"
echo "========================================"
echo ""
echo "View auto-tune log:"
echo "  tail -f /opt/alpha-sniper/logs/auto_tune.log"
echo ""
echo "View cron execution log:"
echo "  tail -f /opt/alpha-sniper/logs/auto_tune_cron.log"
echo ""
echo "Run manual test (won't wait for cron):"
echo "  /opt/alpha-sniper/auto_tune_service.sh '6 hours ago'"
echo ""
echo "Disable auto-tune:"
echo "  crontab -l | grep -v auto_tune_service.sh | crontab -"
echo ""
echo "========================================"
echo ""
