#!/bin/bash
########################################
# Deploy Updated Files to AWS Server
########################################

echo "This script will upload updated files to your AWS server"
echo ""
read -p "Enter AWS server IP or hostname: " SERVER_HOST

if [ -z "$SERVER_HOST" ]; then
    echo "Error: Server hostname required"
    exit 1
fi

echo ""
echo "Uploading files to $SERVER_HOST..."
echo ""

# Upload Python files
scp alpha-sniper/config.py ubuntu@$SERVER_HOST:/tmp/config.py.new
scp alpha-sniper/signals/pump_engine.py ubuntu@$SERVER_HOST:/tmp/pump_engine.py.new
scp alpha-sniper/utils/telegram.py ubuntu@$SERVER_HOST:/tmp/telegram.py.new
scp alpha-sniper/utils/telegram_alerts.py ubuntu@$SERVER_HOST:/tmp/telegram_alerts.py.new

# Upload env file
scp alpha-sniper-live.env.optimized ubuntu@$SERVER_HOST:/tmp/alpha-sniper-live.env.new

echo ""
echo "Files uploaded! Now SSH to server and run:"
echo ""
echo "ssh ubuntu@$SERVER_HOST"
echo ""
echo "Then run these commands on the server:"
echo ""
cat << 'SERVERCOMMANDS'
# Stop bot
sudo systemctl stop alpha-sniper-live.service

# Backup current files
sudo cp /opt/alpha-sniper/alpha-sniper/config.py /opt/alpha-sniper/alpha-sniper/config.py.backup
sudo cp /opt/alpha-sniper/alpha-sniper/signals/pump_engine.py /opt/alpha-sniper/alpha-sniper/signals/pump_engine.py.backup
sudo cp /opt/alpha-sniper/alpha-sniper/utils/telegram.py /opt/alpha-sniper/alpha-sniper/utils/telegram.py.backup
sudo cp /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py.backup
sudo cp /etc/alpha-sniper/alpha-sniper-live.env /etc/alpha-sniper/alpha-sniper-live.env.backup

# Copy new files
sudo cp /tmp/config.py.new /opt/alpha-sniper/alpha-sniper/config.py
sudo cp /tmp/pump_engine.py.new /opt/alpha-sniper/alpha-sniper/signals/pump_engine.py
sudo cp /tmp/telegram.py.new /opt/alpha-sniper/alpha-sniper/utils/telegram.py
sudo cp /tmp/telegram_alerts.py.new /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py
sudo cp /tmp/alpha-sniper-live.env.new /etc/alpha-sniper/alpha-sniper-live.env

# Set permissions
sudo chown alpha-sniper:alpha-sniper /opt/alpha-sniper/alpha-sniper/config.py
sudo chown alpha-sniper:alpha-sniper /opt/alpha-sniper/alpha-sniper/signals/pump_engine.py
sudo chown alpha-sniper:alpha-sniper /opt/alpha-sniper/alpha-sniper/utils/telegram.py
sudo chown alpha-sniper:alpha-sniper /opt/alpha-sniper/alpha-sniper/utils/telegram_alerts.py
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env

# Restart bot
sudo systemctl restart alpha-sniper-live.service

# Monitor logs
sudo journalctl -u alpha-sniper-live.service -f
SERVERCOMMANDS

echo ""
echo "Script complete!"
