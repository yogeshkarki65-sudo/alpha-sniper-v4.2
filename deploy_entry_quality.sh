#!/bin/bash
# deploy_entry_quality.sh - Deploy Entry Quality Improvements
# Run this script from the production server at /opt/alpha-sniper/alpha-sniper

set -e  # Exit on error

echo "=== Deploying Entry Quality Improvements ==="
echo ""

# Check we're in the right directory
if [ ! -f "app_async.py" ]; then
    echo "ERROR: Must run from /opt/alpha-sniper/alpha-sniper directory"
    exit 1
fi

# Stop service
echo "Stopping service..."
sudo systemctl stop alpha-sniper-async.service

# Pull latest code
echo ""
echo "Pulling latest code from branch..."
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Apply new defaults via overrides
cd /opt/alpha-sniper
source venv/bin/activate

echo ""
echo "=== Applying Quality-First Entry Thresholds ==="
python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.018
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 2.0
python scripts/overrides_cli.py set --key MIN_SCORE --value 6
python scripts/overrides_cli.py set --key EAGER_MIN_DEPTH_USD --value 8000
python scripts/overrides_cli.py set --key MIN_DEPTH_USD_ABSOLUTE --value 8000
python scripts/overrides_cli.py set --key MIN_DEPTH_MULTIPLE --value 150
python scripts/overrides_cli.py set --key UNIVERSE_MIN_QUOTE_VOLUME --value 150000
python scripts/overrides_cli.py set --key RISK_PER_TRADE --value 0.0020

echo ""
echo "=== Applying Universe Exclusions ==="
# New universe exclude regex (stables + memes)
python scripts/overrides_cli.py set --key UNIVERSE_EXCLUDE_REGEX --value '(^((DAI|FDUSD|USDC|EUR|XAUT|WBTC))/USDT$|.*/(FDUSD|USDC)$|([A-Z]*?(INU|PEPE|TRUMP|BONK|FLOKI|ELON)[A-Z]*)/USDT$)'

echo ""
echo "=== Applying AutoTune Controls ==="
# AutoTune controls (disable flow, enable winrate)
python scripts/overrides_cli.py set --key AUTOTUNE_FLOW_ENABLE --value false
python scripts/overrides_cli.py set --key WINRATE_ADJUST_ENABLE --value true
python scripts/overrides_cli.py set --key AUTOTUNE_MIN_DWELL_MIN --value 60

echo ""
echo "=== Applying Entry Quality Filters (v1) ==="
# Original 4 filters
python scripts/overrides_cli.py set --key ENTRY_TREND_EMA_CHECK_ENABLE --value true
python scripts/overrides_cli.py set --key ENTRY_ACCEL_ENABLE --value true
python scripts/overrides_cli.py set --key ENTRY_WICK_FILTER_ENABLE --value true
python scripts/overrides_cli.py set --key BTC_GUARD_ENABLE --value true
python scripts/overrides_cli.py set --key BTC_RET5M_MIN --value -0.003

echo ""
echo "=== Applying Advanced Filters (v2) ==="
# Spread cap filter (rejects illiquid books)
python scripts/overrides_cli.py set --key ENTRY_SPREAD_CAP_ENABLE --value true
python scripts/overrides_cli.py set --key ENTRY_SPREAD_MAX_PCT --value 0.0030

# Volume quality filter (sustained volume, not one-print manipulation)
python scripts/overrides_cli.py set --key ENTRY_VOLUME_QUALITY_ENABLE --value true
python scripts/overrides_cli.py set --key ENTRY_VOLUME_QUALITY_MULT --value 4.0

# Regime-aware thresholds (dynamic adjustment based on BTC)
python scripts/overrides_cli.py set --key ENTRY_REGIME_AWARE_ENABLE --value true
python scripts/overrides_cli.py set --key ENTRY_REGIME_STRICT_BTC_PCT --value -0.005
python scripts/overrides_cli.py set --key ENTRY_REGIME_LOOSE_BTC_PCT --value 0.005
python scripts/overrides_cli.py set --key ENTRY_REGIME_STRICT_RET5M_ADD --value 0.002
python scripts/overrides_cli.py set --key ENTRY_REGIME_STRICT_VSPIKE_ADD --value 0.2
python scripts/overrides_cli.py set --key ENTRY_REGIME_LOOSE_RET5M_SUB --value 0.001

echo ""
echo "=== Applying Sizing Controls ==="
python scripts/overrides_cli.py set --key EAGER_WALLET_RESERVE_USD --value 3.0

deactivate

# Start service
echo ""
echo "Starting service..."
sudo systemctl start alpha-sniper-async.service
sleep 3
sudo systemctl status alpha-sniper-async.service --no-pager

echo ""
echo "=== Monitoring for 30 seconds ==="
timeout 30s sudo journalctl -u alpha-sniper-async.service -f | grep -E 'EAGER|WINRATE|AUTOTUNE|FILTERS' || true

echo ""
echo "=== Installing Auto-Tune Service ==="
if [ -f "/opt/alpha-sniper/install_auto_tune.sh" ]; then
    echo "Setting up automatic parameter tuning (runs every 6 hours)..."
    /opt/alpha-sniper/install_auto_tune.sh <<EOF
y
EOF
else
    echo "⚠️  Auto-tune installer not found. You can install it later with:"
    echo "   /opt/alpha-sniper/install_auto_tune.sh"
fi

echo ""
echo "==================================================================="
echo "Deployment complete!"
echo "==================================================================="
echo ""
echo "Expected behavior:"
echo "  ✅ No more flow-based loosening (AUTOTUNE_PRO logs)"
echo "  ✅ Winrate adjustments every ~60 min max"
echo "  ✅ Tighter entry thresholds (1.8% momentum, 2x volume)"
echo "  ✅ 7 entry filters active (EMA, ACCEL, WICK, BTC, SPREAD, VOL_QUALITY, REGIME)"
echo "  ✅ Entry filter rejections logged as [EAGER_FILTERS]"
echo "  ✅ Regime-aware: stricter in BTC downtrends, looser in uptrends"
echo "  ✅ Sizing capped by reserve buffer (no more \$350 on \$170 balance)"
echo "  ✅ Fewer but higher quality trades (target 30-40% winrate)"
echo ""
echo "Monitoring commands:"
echo "  cd /opt/alpha-sniper/alpha-sniper"
echo ""
echo "  # Quick dashboard (recommended):"
echo "  ./monitor_entry_quality.sh \"6 hours ago\""
echo ""
echo "  # Get tuning suggestions:"
echo "  ./suggest_tuning.sh \"6 hours ago\""
echo ""
echo "  # Live tail filters:"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_THRESHOLDS"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_FILTERS"
echo "  sudo journalctl -u alpha-sniper-async.service -f | grep REGIME"
echo ""
