#!/bin/bash
# Quick balance check script for MEXC account

cd /opt/alpha-sniper || { echo "ERROR: /opt/alpha-sniper not found"; exit 1; }

# Load environment from systemd service
echo "Loading API credentials from systemd environment..."
eval $(sudo systemctl show-environment | grep ALPHA_)

# Source virtual environment
source venv/bin/activate

# Run balance test
echo ""
python test_balance.py
