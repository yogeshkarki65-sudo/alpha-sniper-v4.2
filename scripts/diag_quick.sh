#!/bin/bash
#
# Quick Diagnostics - Last 10 minutes of bot activity
#
# Shows:
# - Last thresholds banner
# - All EAGER flow summaries
# - Last filter summary
# - All placement/filled/cancel events
#
# Usage: bash scripts/diag_quick.sh

set -e

# Configuration
SERVICE_NAME="${SERVICE_NAME:-alpha-sniper-async.service}"
MINUTES="${1:-10}"  # Default to 10 minutes, or use first arg

echo "========================================"
echo " ALPHA SNIPER - QUICK DIAGNOSTICS"
echo " Last ${MINUTES} minutes"
echo "========================================"
echo ""

# Check if journalctl is available
if ! command -v journalctl &> /dev/null; then
    echo "ERROR: journalctl not found. This script requires systemd."
    echo "Try checking logs manually in /var/log or /opt/alpha-sniper/logs/"
    exit 1
fi

# Check if service exists
if ! systemctl list-units --all | grep -q "$SERVICE_NAME"; then
    echo "WARNING: Service '$SERVICE_NAME' not found."
    echo "Available alpha-sniper services:"
    systemctl list-units --all | grep -i alpha || echo "  (none found)"
    echo ""
    echo "Set SERVICE_NAME environment variable to use a different service."
    echo "Example: SERVICE_NAME=alpha-sniper-live.service bash scripts/diag_quick.sh"
    exit 1
fi

echo "📊 Service: $SERVICE_NAME"
echo ""

# 1. Last thresholds banner
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 LAST THRESHOLDS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" \
    | grep "EAGER_THRESHOLDS" \
    | tail -1 \
    | sed 's/.*EAGER_THRESHOLDS]/EAGER_THRESHOLDS:/' \
    || echo "(No thresholds logged in last ${MINUTES}min)"
echo ""

# 2. All EAGER flow summaries
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 EAGER SUMMARIES (all in window)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" \
    | grep "EAGER_SUMMARY" \
    | sed 's/.*EAGER_SUMMARY]//' \
    || echo "(No EAGER summaries in last ${MINUTES}min)"
echo ""

# 3. Last filter summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 LAST FILTER SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" \
    | grep "EAGER_FILTER_SUMMARY" \
    | tail -1 \
    | sed 's/.*EAGER_FILTER_SUMMARY]/Rejections:/' \
    || echo "(No filter summaries in last ${MINUTES}min)"
echo ""

# 4. All placement/filled/cancel events
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 ORDER EVENTS (place/filled/cancel)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" \
    | grep -E "EAGER_PLACE|EAGER_FILLED|EAGER_CANCEL" \
    | sed 's/.*\(EAGER_[A-Z_]*\)]/\1:/' \
    || echo "(No order events in last ${MINUTES}min)"
echo ""

# 5. Skip-after-pass events (candidates that passed filters but couldn't trade)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  SKIP AFTER PASS (passed filters, failed sizing/validation)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" \
    | grep "SKIP_AFTER_PASS" \
    | sed 's/.*EAGER]/SKIP:/' \
    || echo "(No skip-after-pass events in last ${MINUTES}min)"
echo ""

# 6. Recent errors (last 3)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "❌ RECENT ERRORS (last 3)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo journalctl -u "$SERVICE_NAME" --since "${MINUTES} minutes ago" -p err \
    | tail -3 \
    || echo "(No errors in last ${MINUTES}min)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Diagnostics complete"
echo ""
echo "Usage tips:"
echo "  • Show last 30min: bash scripts/diag_quick.sh 30"
echo "  • Custom service:  SERVICE_NAME=my-service bash scripts/diag_quick.sh"
echo "  • Full logs:       sudo journalctl -u $SERVICE_NAME -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
