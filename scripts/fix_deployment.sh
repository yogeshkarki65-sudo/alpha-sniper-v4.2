#!/bin/bash
#
# Quick fix for Alpha Sniper deployment issues
# Run this on production server: bash fix_deployment.sh
#

set -e

echo "=========================================="
echo "🔧 Alpha Sniper Deployment Fix"
echo "=========================================="
echo ""

# 1. Create missing directories
echo "1️⃣ Creating missing directories..."
sudo mkdir -p /opt/alpha-sniper/logs
sudo mkdir -p /var/lib/alpha-sniper
sudo mkdir -p /opt/alpha-sniper/data

# Set ownership
sudo chown -R ubuntu:ubuntu /opt/alpha-sniper/logs
sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper
sudo chown -R ubuntu:ubuntu /opt/alpha-sniper/data

echo "✓ Directories created"
echo ""

# 2. Install Python dependencies
echo "2️⃣ Installing Python dependencies..."
cd /opt/alpha-sniper
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✓ Dependencies installed"
echo ""

# 3. Verify .env file exists and has API keys
echo "3️⃣ Checking .env file..."
if [ ! -f "/opt/alpha-sniper/alpha-sniper/.env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please create /opt/alpha-sniper/alpha-sniper/.env with your API keys"
    exit 1
fi

if ! grep -q "MEXC_API_KEY=" "/opt/alpha-sniper/alpha-sniper/.env"; then
    echo "❌ ERROR: MEXC_API_KEY not found in .env"
    exit 1
fi

echo "✓ .env file validated"
echo ""

# 4. Stop any running service
echo "4️⃣ Stopping service..."
sudo systemctl stop alpha-sniper-live.service 2>/dev/null || true
echo "✓ Service stopped"
echo ""

# 5. Test Python imports
echo "5️⃣ Testing Python imports..."
python3 -c "import dotenv, ccxt, pandas; print('✓ All dependencies OK')"
echo ""

# 6. Start service
echo "6️⃣ Starting service..."
sudo systemctl start alpha-sniper-live.service

# Wait a moment
sleep 2

# Check status
if sudo systemctl is-active --quiet alpha-sniper-live.service; then
    echo "✅ Service started successfully!"
else
    echo "⚠️  Service may have issues. Checking status..."
    sudo systemctl status alpha-sniper-live.service --no-pager
fi

echo ""
echo "=========================================="
echo "✅ Deployment fix complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Monitor logs: sudo journalctl -u alpha-sniper-live.service -f"
echo "  2. Check status: sudo systemctl status alpha-sniper-live.service"
echo "  3. View bot logs: tail -f /opt/alpha-sniper/logs/bot.log"
echo ""
