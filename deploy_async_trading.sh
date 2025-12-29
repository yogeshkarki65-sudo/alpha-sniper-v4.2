#!/usr/bin/env bash
#
# Deploy Alpha Sniper v4.2 Async Trading Bot to Production
#
# This script:
# 1. Pulls latest code with trading integration
# 2. Stops async service
# 3. Installs dependencies
# 4. Starts async service
# 5. Shows logs for verification
#

set -e  # Exit on error

echo "======================================================================"
echo "🚀 DEPLOYING ALPHA SNIPER V4.2 ASYNC TRADING BOT"
echo "======================================================================"
echo ""

# Change to repo directory
cd /opt/alpha-sniper || { echo "ERROR: /opt/alpha-sniper not found"; exit 1; }

echo "📥 Step 1: Pulling latest code..."
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
echo "✅ Code updated"
echo ""

echo "🛑 Step 2: Stopping async service..."
sudo systemctl stop alpha-sniper-async.service 2>/dev/null || true
echo "✅ Service stopped"
echo ""

echo "📦 Step 3: Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt
echo "✅ Dependencies installed"
echo ""

echo "🔍 Step 4: Verifying configuration..."
if [ ! -f "alpha-sniper/.env.async" ]; then
    echo "⚠️  WARNING: .env.async not found!"
    echo "Create it with ALPHA_ prefixed variables"
    echo "Example: ALPHA_MODE=LIVE, ALPHA_API_KEY=..., etc."
    exit 1
fi

# Check if key variables are set
if ! grep -q "ALPHA_API_KEY" alpha-sniper/.env.async; then
    echo "⚠️  WARNING: ALPHA_API_KEY not found in .env.async"
    exit 1
fi

echo "✅ Configuration verified"
echo ""

echo "🚀 Step 5: Starting async trading bot..."
sudo systemctl start alpha-sniper-async.service
sleep 3
echo "✅ Service started"
echo ""

echo "📊 Step 6: Service status..."
sudo systemctl status alpha-sniper-async.service --no-pager || true
echo ""

echo "======================================================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "======================================================================"
echo ""
echo "📺 Monitor logs:"
echo "  sudo journalctl -u alpha-sniper-async.service -f"
echo ""
echo "🔍 Check status:"
echo "  sudo systemctl status alpha-sniper-async.service"
echo ""
echo "🎯 What to watch for in logs:"
echo "  1. ✅ All components initialized"
echo "  2. 🔍 SCAN #1 | timestamp"
echo "  3. Market data fetched: 80/80 symbols"
echo "  4. Signals generated: X"
echo "  5. ✅ Position opened (if signals found)"
echo ""
echo "⚠️  LIVE_TEST_MODE active by default:"
echo "  - Max 3 orders per day"
echo "  - Max \$7.50 per order"
echo "  - Max \$22.50 total daily risk"
echo ""
echo "🎉 BOT IS NOW TRADING!"
echo "======================================================================"
