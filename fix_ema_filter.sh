#!/bin/bash
# fix_ema_filter.sh - Re-enable the critical EMA trend filter

set -e

echo "=== Re-enabling EMA Trend Filter ==="
echo ""

cd /opt/alpha-sniper
source venv/bin/activate

# Re-enable the EMA trend check (most important quality filter)
echo "Enabling ENTRY_TREND_EMA_CHECK_ENABLE..."
python scripts/overrides_cli.py set --key ENTRY_TREND_EMA_CHECK_ENABLE --value true

# Verify all current settings
echo ""
echo "=== Current Entry Thresholds ==="
echo "EARLY_RET_5M_MIN: $(python scripts/overrides_cli.py get --key EARLY_RET_5M_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)"
echo "EARLY_VOL_SPIKE_MIN: $(python scripts/overrides_cli.py get --key EARLY_VOL_SPIKE_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)"
echo "EAGER_VSPIKE_MIN: $(python scripts/overrides_cli.py get --key EAGER_VSPIKE_MIN 2>/dev/null | grep -oP '[\d.]+' | head -1)"

echo ""
echo "=== Entry Filters Status ==="
echo "EMA_TREND: $(python scripts/overrides_cli.py get --key ENTRY_TREND_EMA_CHECK_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "ACCEL: $(python scripts/overrides_cli.py get --key ENTRY_ACCEL_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "WICK: $(python scripts/overrides_cli.py get --key ENTRY_WICK_FILTER_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "BTC_GUARD: $(python scripts/overrides_cli.py get --key BTC_GUARD_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "SPREAD_CAP: $(python scripts/overrides_cli.py get --key ENTRY_SPREAD_CAP_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "VOL_QUALITY: $(python scripts/overrides_cli.py get --key ENTRY_VOLUME_QUALITY_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "REGIME_AWARE: $(python scripts/overrides_cli.py get --key ENTRY_REGIME_AWARE_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"

echo ""
echo "=== AutoTune Status ==="
echo "WINRATE_ADJUST: $(python scripts/overrides_cli.py get --key WINRATE_ADJUST_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"
echo "AUTOTUNE_FLOW: $(python scripts/overrides_cli.py get --key AUTOTUNE_FLOW_ENABLE 2>/dev/null | grep -oP '(True|False)' | head -1)"

deactivate

echo ""
echo "=== Restarting Service ==="
sudo systemctl restart alpha-sniper-async.service
sleep 3
sudo systemctl status alpha-sniper-async.service --no-pager | head -20

echo ""
echo "=== DONE ==="
echo ""
echo "Monitor for trades:"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep -E 'EAGER_THRESHOLDS|OPENED LONG|eager_candidates='"
echo ""
echo "Expected configuration:"
echo "  • Thresholds: ret5m≥1.4%, vspike≥1.6x (LOOSE)"
echo "  • EMA Filter: ENABLED (quality check)"
echo "  • AutoTune: DISABLED (no more overrides)"
echo ""
echo "This should give you 5-15 trades per day with better quality (25-35% win rate target)"
echo ""
