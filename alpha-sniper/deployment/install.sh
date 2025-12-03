#!/bin/bash
# Alpha Sniper V4.2 - Production Installation Script
# Run this script on a fresh Ubuntu 22.04+ server

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_USER="alpha-sniper"
APP_DIR="/opt/alpha-sniper"
LOG_DIR="/var/log/alpha-sniper"
RUN_DIR="/var/run/alpha-sniper"
CONFIG_DIR="/etc/alpha-sniper"

echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}Alpha Sniper V4.2 Installation${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (use sudo)${NC}"
    exit 1
fi

# Check Ubuntu version
if ! grep -q "Ubuntu" /etc/os-release; then
    echo -e "${YELLOW}Warning: This script is designed for Ubuntu. Proceed anyway? (y/n)${NC}"
    read -r response
    if [ "$response" != "y" ]; then
        exit 1
    fi
fi

echo -e "${GREEN}[1/8] Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv git curl

echo -e "${GREEN}[2/8] Creating alpha-sniper user...${NC}"
if id "$APP_USER" &>/dev/null; then
    echo "User $APP_USER already exists, skipping creation"
else
    adduser --system --group --home $APP_DIR $APP_USER
    echo "User $APP_USER created"
fi

echo -e "${GREEN}[3/8] Creating directories...${NC}"
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p $RUN_DIR
mkdir -p $CONFIG_DIR

chown $APP_USER:$APP_USER $APP_DIR
chown $APP_USER:$APP_USER $LOG_DIR
chown $APP_USER:$APP_USER $RUN_DIR
chown $APP_USER:$APP_USER $CONFIG_DIR

echo -e "${GREEN}[4/8] Deploying application code...${NC}"
if [ ! -f "$APP_DIR/main.py" ]; then
    echo -e "${YELLOW}Please copy your Alpha Sniper code to $APP_DIR${NC}"
    echo "You can use: rsync -avz /path/to/alpha-sniper/ $APP_DIR/"
    echo ""
    echo -e "${YELLOW}Press Enter once code is deployed...${NC}"
    read -r
else
    echo "Code already present in $APP_DIR"
fi

echo -e "${GREEN}[5/8] Setting up Python virtual environment...${NC}"
if [ ! -d "$APP_DIR/venv" ]; then
    sudo -u $APP_USER python3 -m venv $APP_DIR/venv
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install --upgrade pip
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
    echo "Virtual environment created and dependencies installed"
else
    echo "Virtual environment already exists"
    echo -e "${YELLOW}Updating dependencies...${NC}"
    sudo -u $APP_USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
fi

echo -e "${GREEN}[6/8] Installing systemd services...${NC}"
if [ -f "$APP_DIR/deployment/systemd/alpha-sniper-sim.service" ]; then
    cp $APP_DIR/deployment/systemd/alpha-sniper-sim.service /etc/systemd/system/
    cp $APP_DIR/deployment/systemd/alpha-sniper-live.service /etc/systemd/system/
    systemctl daemon-reload
    echo "systemd services installed"
else
    echo -e "${YELLOW}Warning: systemd service files not found${NC}"
fi

echo -e "${GREEN}[7/8] Setting up configuration files...${NC}"
if [ ! -f "$CONFIG_DIR/alpha-sniper-sim.env" ]; then
    if [ -f "$APP_DIR/deployment/config/alpha-sniper-sim.env.example" ]; then
        cp $APP_DIR/deployment/config/alpha-sniper-sim.env.example $CONFIG_DIR/alpha-sniper-sim.env
        cp $APP_DIR/deployment/config/alpha-sniper-live.env.example $CONFIG_DIR/alpha-sniper-live.env
        chown $APP_USER:$APP_USER $CONFIG_DIR/*.env
        chmod 600 $CONFIG_DIR/*.env
        echo "Configuration templates copied"
    fi
else
    echo "Configuration files already exist, skipping"
fi

echo -e "${GREEN}[8/8] Setting up log rotation...${NC}"
cat > /etc/logrotate.d/alpha-sniper <<EOF
$LOG_DIR/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 $APP_USER $APP_USER
    sharedscripts
    postrotate
        systemctl reload alpha-sniper-sim.service > /dev/null 2>&1 || true
        systemctl reload alpha-sniper-live.service > /dev/null 2>&1 || true
    endscript
}
EOF
echo "Log rotation configured"

echo ""
echo -e "${GREEN}=================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}=================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Configure environment:"
echo "   sudo nano $CONFIG_DIR/alpha-sniper-sim.env"
echo ""
echo "2. Test the bot manually (SIM mode):"
echo "   sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/run.py --mode sim --once"
echo ""
echo "3. Start the SIM service:"
echo "   sudo systemctl start alpha-sniper-sim.service"
echo "   sudo systemctl status alpha-sniper-sim.service"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u alpha-sniper-sim.service -f"
echo "   tail -f $LOG_DIR/alpha-sniper-sim.log"
echo ""
echo "5. Enable on boot (optional):"
echo "   sudo systemctl enable alpha-sniper-sim.service"
echo ""
echo -e "${RED}IMPORTANT:${NC}"
echo "- Review ALL configuration in $CONFIG_DIR/alpha-sniper-sim.env"
echo "- Test thoroughly in SIM mode before considering LIVE mode"
echo "- See $APP_DIR/DEPLOYMENT.md for complete documentation"
echo ""
