#!/bin/bash
# Deploy Phase 1.1 + Hold Brain Async Bot to Production
# Run this script from your server: bash scripts/deploy_async_bot.sh

set -e  # Exit on error

echo "🚀 Deploying Alpha Sniper v4.2 (Async) with Phase 1.1 + Hold Brain..."

# 1. Check current directory
if [ ! -f "app_async.py" ]; then
    echo "❌ Error: Must run from alpha-sniper-v4.2 root directory"
    echo "   cd /home/user/alpha-sniper-v4.2 && bash scripts/deploy_async_bot.sh"
    exit 1
fi

# 2. Check if .env exists
if [ ! -f "alpha-sniper/.env" ]; then
    echo "❌ Error: No .env file found in alpha-sniper/"
    echo "   Copy your production .env file first:"
    echo "   cp /opt/alpha-sniper/alpha-sniper/.env alpha-sniper/.env"
    echo "   OR create a new one with your API keys"
    exit 1
fi

# 3. Validate .env has required settings
if ! grep -q "ALPHA_API_KEY" alpha-sniper/.env; then
    echo "⚠️  Warning: .env file may be missing ALPHA_API_KEY"
    echo "   Make sure your .env has:"
    echo "   - ALPHA_API_KEY=your_mexc_api_key"
    echo "   - ALPHA_API_SECRET=your_mexc_secret"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 4. Create data directory
echo "📁 Creating data directory..."
mkdir -p data logs

# 5. Check if old bot is running
if sudo systemctl is-active --quiet alpha-sniper-async; then
    echo "⏸️  Stopping old async bot..."
    sudo systemctl stop alpha-sniper-async
fi

# 6. Create systemd service
echo "📝 Creating systemd service..."
sudo tee /etc/systemd/system/alpha-sniper-async.service > /dev/null <<EOF
[Unit]
Description=Alpha Sniper v4.2 Async Trading Bot (Phase 1.1 + Hold Brain)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(pwd)
Environment="PYTHONUNBUFFERED=1"
ExecStart=$(which python3) $(pwd)/app_async.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 7. Reload systemd
echo "♻️  Reloading systemd..."
sudo systemctl daemon-reload

# 8. Enable service
echo "✅ Enabling service..."
sudo systemctl enable alpha-sniper-async

# 9. Start service
echo "🚀 Starting bot..."
sudo systemctl start alpha-sniper-async

# 10. Wait and check status
sleep 3
echo ""
echo "📊 Bot Status:"
sudo systemctl status alpha-sniper-async --no-pager -l | head -20

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "   View logs:    sudo journalctl -u alpha-sniper-async -f"
echo "   Stop bot:     sudo systemctl stop alpha-sniper-async"
echo "   Restart bot:  sudo systemctl restart alpha-sniper-async"
echo "   Bot status:   sudo systemctl status alpha-sniper-async"
echo ""
echo "🎯 Phase 1.1 Features Active:"
echo "   - Per-symbol cooldown (120s)"
echo "   - Wick filter (ATR-based)"
echo "   - Absolute depth floor (\$25k)"
echo "   - Daily digest (midnight UTC)"
echo "   - IOC/slippage tracking"
echo ""
echo "🧠 Hold Brain Features Active:"
echo "   - Promote winners (2.5R+)"
echo "   - Demote losers (2min flat)"
echo "   - Trailing stops (2% @ 1.5R)"
echo "   - Hard cap (8h max hold)"
