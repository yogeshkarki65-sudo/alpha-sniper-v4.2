# Alpha Sniper V4.2 - Production Deployment Guide

Complete guide for deploying Alpha Sniper V4.2 on Ubuntu 22.04+ with systemd.

---

## Table of Contents

1. [Quick Start (Local Development)](#quick-start-local-development)
2. [Production Deployment (Ubuntu + systemd)](#production-deployment-ubuntu--systemd)
3. [Health Checks & Monitoring](#health-checks--monitoring)
4. [Operations](#operations)
5. [Safety Checklist](#safety-checklist)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- pip and virtualenv

### Setup

```bash
# 1. Clone the repository
cd ~/alpha-sniper-v4.2/alpha-sniper

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
nano .env  # Edit configuration

# 5. Run in SIM mode (safe)
python run.py --mode sim

# Or use Make
make dev
```

### Test Single Cycle

```bash
# Run one cycle then exit (for testing)
python run.py --mode sim --once

# Or
make dev-once
```

### Run Tests

```bash
make test
# Or manually:
python test_entry_dete.py
python test_dfe.py
python test_funding.py
```

---

## Production Deployment (Ubuntu + systemd)

### 1. Server Setup

#### Create dedicated user

```bash
sudo adduser --system --group --home /opt/alpha-sniper alpha-sniper
```

#### Create directories

```bash
# Application directory
sudo mkdir -p /opt/alpha-sniper
sudo chown alpha-sniper:alpha-sniper /opt/alpha-sniper

# Log directory
sudo mkdir -p /var/log/alpha-sniper
sudo chown alpha-sniper:alpha-sniper /var/log/alpha-sniper

# Runtime directory (for heartbeat)
sudo mkdir -p /var/run/alpha-sniper
sudo chown alpha-sniper:alpha-sniper /var/run/alpha-sniper

# Config directory
sudo mkdir -p /etc/alpha-sniper
sudo chown alpha-sniper:alpha-sniper /etc/alpha-sniper
```

### 2. Deploy Code

```bash
# Copy code to server (from your local machine)
rsync -avz --exclude venv --exclude logs --exclude __pycache__ \
  ~/alpha-sniper-v4.2/alpha-sniper/ \
  user@your-server:/opt/alpha-sniper/

# Or clone directly on server
sudo -u alpha-sniper git clone https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2.git /opt/alpha-sniper
```

### 3. Install Dependencies

```bash
# Switch to alpha-sniper user
sudo -u alpha-sniper -i

# Navigate to app directory
cd /opt/alpha-sniper

# Create virtual environment
python3 -m venv venv

# Install dependencies
./venv/bin/pip install -r requirements.txt

# Exit back to your user
exit
```

### 4. Configure Environment

#### For SIM mode:

```bash
# Copy template
sudo cp /opt/alpha-sniper/deployment/config/alpha-sniper-sim.env.example \
  /etc/alpha-sniper/alpha-sniper-sim.env

# Edit configuration
sudo nano /etc/alpha-sniper/alpha-sniper-sim.env

# Set ownership
sudo chown alpha-sniper:alpha-sniper /etc/alpha-sniper/alpha-sniper-sim.env
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-sim.env
```

**Required changes in alpha-sniper-sim.env:**
```bash
SIM_MODE=true
SIM_DATA_SOURCE=LIVE_DATA
STARTING_EQUITY=1000

# Optional: Add Telegram for notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

#### For LIVE mode:

```bash
# Copy template
sudo cp /opt/alpha-sniper/deployment/config/alpha-sniper-live.env.example \
  /etc/alpha-sniper/alpha-sniper-live.env

# Edit configuration
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Set ownership and strict permissions
sudo chown alpha-sniper:alpha-sniper /etc/alpha-sniper/alpha-sniper-live.env
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
```

**Required changes in alpha-sniper-live.env:**
```bash
SIM_MODE=false  # CRITICAL!

# REQUIRED: MEXC API keys
MEXC_API_KEY=your_live_api_key
MEXC_SECRET_KEY=your_live_secret_key

# REQUIRED: Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Review ALL risk parameters!
MAX_PORTFOLIO_HEAT=0.008
MAX_CONCURRENT_POSITIONS=3
RISK_PER_TRADE_BULL=0.0015
# ... etc
```

### 5. Install systemd Services

#### For SIM mode:

```bash
# Copy service file
sudo cp /opt/alpha-sniper/deployment/systemd/alpha-sniper-sim.service \
  /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable alpha-sniper-sim.service

# Start service
sudo systemctl start alpha-sniper-sim.service

# Check status
sudo systemctl status alpha-sniper-sim.service
```

#### For LIVE mode:

⚠️  **WARNING: Only after thorough testing in SIM mode!**

```bash
# Copy service file
sudo cp /opt/alpha-sniper/deployment/systemd/alpha-sniper-live.service \
  /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable alpha-sniper-live.service

# Start service
sudo systemctl start alpha-sniper-live.service

# Check status
sudo systemctl status alpha-sniper-live.service
```

---

## Health Checks & Monitoring

### HTTP Health Endpoint

The bot exposes a health check endpoint on port 8080:

```bash
# Check health via HTTP
curl http://localhost:8080/health

# Response (healthy):
{
  "status": "healthy",
  "timestamp": "2025-12-03T14:30:00",
  "message": "Bot is running normally",
  "bot_running": true
}
```

### Heartbeat File

The bot updates a heartbeat file every 30 seconds:

```bash
# Check heartbeat
cat /var/run/alpha-sniper/heartbeat.json

# Response:
{
  "timestamp": "2025-12-03T14:30:00",
  "status": "running",
  "pid": 12345,
  "open_positions": 2,
  "equity": 1050.25
}
```

### CLI Healthcheck

```bash
# Run healthcheck command
sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/python -m alpha_sniper.healthcheck

# Output:
# 📊 Alpha Sniper Health Status
#    Status: running
#    PID: 12345
#    Last heartbeat: 15s ago
#    Open positions: 2
#    Equity: $1050.25
# ✅ Status: HEALTHY

# Exit codes:
# 0 = Healthy
# 1 = Unhealthy
# 2 = Unknown/Error
```

### External Monitoring (Optional)

Set up a cron job to check health and alert if unhealthy:

```bash
# Create monitoring script
sudo nano /usr/local/bin/check-alpha-sniper.sh
```

```bash
#!/bin/bash
# Check Alpha Sniper health and restart if needed

/opt/alpha-sniper/venv/bin/python -m alpha_sniper.healthcheck

if [ $? -ne 0 ]; then
    echo "Bot unhealthy, restarting..."
    systemctl restart alpha-sniper-sim.service
    # Send alert via Telegram, email, etc.
fi
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/check-alpha-sniper.sh

# Add to crontab (check every 5 minutes)
sudo crontab -e
# Add: */5 * * * * /usr/local/bin/check-alpha-sniper.sh
```

---

## Operations

### Viewing Logs

#### Systemd Journal (real-time)

```bash
# SIM mode logs
sudo journalctl -u alpha-sniper-sim.service -f

# LIVE mode logs
sudo journalctl -u alpha-sniper-live.service -f

# Last 100 lines
sudo journalctl -u alpha-sniper-sim.service -n 100

# Since today
sudo journalctl -u alpha-sniper-sim.service --since today
```

#### Log Files

```bash
# INFO logs
tail -f /var/log/alpha-sniper/alpha-sniper-sim.log

# DEBUG logs
tail -f /var/log/alpha-sniper/alpha-sniper-sim-debug.log

# Or use Make
make logs
```

### Service Control

```bash
# Start service
sudo systemctl start alpha-sniper-sim.service

# Stop service
sudo systemctl stop alpha-sniper-sim.service

# Restart service
sudo systemctl restart alpha-sniper-sim.service

# Check status
sudo systemctl status alpha-sniper-sim.service

# Enable on boot
sudo systemctl enable alpha-sniper-sim.service

# Disable on boot
sudo systemctl disable alpha-sniper-sim.service
```

### Switching from SIM to LIVE

⚠️  **CRITICAL: Follow this checklist!**

1. **Stop SIM mode:**
```bash
sudo systemctl stop alpha-sniper-sim.service
sudo systemctl disable alpha-sniper-sim.service
```

2. **Review LIVE configuration:**
```bash
sudo nano /etc/alpha-sniper/alpha-sniper-live.env
```

3. **Verify checklist** (see Safety Checklist below)

4. **Start LIVE mode:**
```bash
sudo systemctl start alpha-sniper-live.service
```

5. **Monitor closely for first hour:**
```bash
sudo journalctl -u alpha-sniper-live.service -f
```

6. **Verify first trade executes correctly**

### Updating Code

```bash
# Stop service
sudo systemctl stop alpha-sniper-sim.service

# Pull updates
cd /opt/alpha-sniper
sudo -u alpha-sniper git pull

# Update dependencies (if changed)
sudo -u alpha-sniper ./venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl start alpha-sniper-sim.service

# Check logs
sudo journalctl -u alpha-sniper-sim.service -f
```

---

## Safety Checklist

### Before Enabling LIVE Mode

- [ ] **Tested thoroughly in SIM mode**
  - Run for at least 24 hours in SIM with LIVE_DATA
  - Review all trades executed in SIM
  - Verify Telegram notifications work
  - Confirm stop losses trigger correctly

- [ ] **API Keys configured**
  - MEXC_API_KEY set in /etc/alpha-sniper/alpha-sniper-live.env
  - MEXC_SECRET_KEY set in /etc/alpha-sniper/alpha-sniper-live.env
  - API key has correct permissions (spot trading)
  - API key IP whitelist configured (if applicable)

- [ ] **Mode consistency**
  - SIM_MODE=false in /etc/alpha-sniper/alpha-sniper-live.env
  - Using --mode live in systemd service file

- [ ] **Risk parameters reviewed**
  - MAX_PORTFOLIO_HEAT set conservatively (0.008 or lower)
  - MAX_CONCURRENT_POSITIONS set low initially (2-3)
  - RISK_PER_TRADE values appropriate for account size
  - ENABLE_DAILY_LOSS_LIMIT=true
  - MAX_DAILY_LOSS_PCT set (2-3% max)

- [ ] **Telegram notifications working**
  - TELEGRAM_BOT_TOKEN set correctly
  - TELEGRAM_CHAT_ID set correctly
  - Test message received successfully

- [ ] **Initial capital appropriate**
  - Starting with small amount you can afford to lose
  - Account funded with USDT on MEXC
  - STARTING_EQUITY matches actual account balance

- [ ] **Monitoring setup**
  - Health check endpoint accessible
  - Alerts configured for bot failures
  - Ready to monitor logs actively

- [ ] **Emergency procedures**
  - Know how to stop bot: `sudo systemctl stop alpha-sniper-live.service`
  - Know how to close all positions manually on MEXC
  - Have MEXC exchange access ready

### First Live Trade Verification

After starting LIVE mode, verify first trade:

1. **Wait for first signal**
2. **Check logs for entry:**
```bash
sudo journalctl -u alpha-sniper-live.service -f | grep "ENTRY"
```

3. **Verify on MEXC exchange:**
   - Order placed successfully
   - Position shows in account
   - Stop loss set correctly

4. **Monitor position closely**

5. **If anything looks wrong:**
```bash
sudo systemctl stop alpha-sniper-live.service
# Close positions manually on MEXC
```

---

## Troubleshooting

### Bot won't start

#### Check logs:
```bash
sudo journalctl -u alpha-sniper-sim.service -n 50
```

#### Common issues:

**1. API key error in LIVE mode:**
```
ERROR: Live mode requires MEXC_API_KEY and MEXC_SECRET_KEY
```
**Fix:** Add API keys to `/etc/alpha-sniper/alpha-sniper-live.env`

**2. Mode mismatch:**
```
SAFETY ERROR: Mode mismatch!
CLI flag: --mode live (wants LIVE)
.env SIM_MODE: true (means SIM)
```
**Fix:** Ensure SIM_MODE matches mode flag in env file

**3. Permission denied:**
```
PermissionError: [Errno 13] Permission denied: '/var/log/alpha-sniper/'
```
**Fix:** Check directory ownership:
```bash
sudo chown -R alpha-sniper:alpha-sniper /var/log/alpha-sniper
```

### Bot stops unexpectedly

#### Check system resources:
```bash
# Memory usage
free -h

# CPU usage
top

# Disk space
df -h
```

#### Check bot logs for errors:
```bash
sudo journalctl -u alpha-sniper-sim.service --since "10 minutes ago" | grep -i error
```

### Trades not executing

#### Check:
1. **Market conditions:** Are there any signals being generated?
```bash
sudo journalctl -u alpha-sniper-sim.service -f | grep "Signals Generated"
```

2. **Portfolio heat:** Is MAX_PORTFOLIO_HEAT reached?
```bash
sudo journalctl -u alpha-sniper-sim.service -f | grep "RISK"
```

3. **API connectivity:** Can bot reach MEXC?
```bash
# Check recent API errors
sudo journalctl -u alpha-sniper-live.service | grep -i "api"
```

### Health check failing

#### Test manually:
```bash
# Check HTTP endpoint
curl http://localhost:8080/health

# Check heartbeat file
cat /var/run/alpha-sniper/heartbeat.json

# Run CLI healthcheck
sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/python -m alpha_sniper.healthcheck
```

### High memory usage

Bot typically uses 200-500MB RAM. If higher:

```bash
# Check memory
ps aux | grep python

# Restart service
sudo systemctl restart alpha-sniper-sim.service
```

---

## Architecture Summary

```
/opt/alpha-sniper/              # Application code
├── run.py                      # Production entry point
├── main.py                     # Core bot logic (unchanged)
├── config.py                   # Config loader
├── alpha_sniper/               # Deployment package
│   ├── health.py               # Health check system
│   └── healthcheck.py          # CLI healthcheck
├── utils/
│   ├── logger_production.py   # Production logging
│   └── ...                     # Other utilities
├── deployment/
│   ├── systemd/                # Service files
│   └── config/                 # Environment templates
└── venv/                       # Python virtual environment

/etc/alpha-sniper/              # Configuration
├── alpha-sniper-sim.env        # SIM mode config
└── alpha-sniper-live.env       # LIVE mode config (secrets!)

/var/log/alpha-sniper/          # Logs
├── alpha-sniper-sim.log        # INFO logs (SIM)
├── alpha-sniper-sim-debug.log  # DEBUG logs (SIM)
├── alpha-sniper-live.log       # INFO logs (LIVE)
└── alpha-sniper-live-debug.log # DEBUG logs (LIVE)

/var/run/alpha-sniper/          # Runtime files
└── heartbeat.json              # Heartbeat file

/etc/systemd/system/            # systemd services
├── alpha-sniper-sim.service    # SIM mode service
└── alpha-sniper-live.service   # LIVE mode service
```

---

## Support

- **Documentation:** See README.md and PUMP_ONLY_MODE.md
- **Issues:** https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2/issues
- **Logs:** `/var/log/alpha-sniper/`

---

## Final Warning

⚠️  **LIVE mode trades with REAL MONEY. You can lose money.**

- Start with small position sizes
- Test thoroughly in SIM first
- Monitor closely initially
- Understand all risk parameters
- Never deploy untested changes to LIVE

**If in doubt, stay in SIM mode.**
