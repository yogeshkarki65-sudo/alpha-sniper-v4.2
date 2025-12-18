# Fix Read-Only Filesystem Error - Deployment Guide

## Problem
Bot crashes with: `OSError: [Errno 30] Read-only file system: '/opt/alpha-sniper/logs/bot.log'`

## Root Cause
Systemd service file doesn't grant write permissions to logs directory.

## Solution

### Step 1: Stop the Service
```bash
sudo systemctl stop alpha-sniper-live.service
```

### Step 2: Update Systemd Service File
```bash
# Copy the corrected service file
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.service /etc/systemd/system/alpha-sniper-live.service

# Verify the file was copied
cat /etc/systemd/system/alpha-sniper-live.service | grep ReadWritePaths
```

Expected output should show:
```
ReadWritePaths=/var/lib/alpha-sniper
ReadWritePaths=/opt/alpha-sniper/logs
ReadWritePaths=/opt/alpha-sniper/reports
```

### Step 3: Fix Permissions Manually (Failsafe)
```bash
# Create directories
sudo mkdir -p /var/lib/alpha-sniper
sudo mkdir -p /opt/alpha-sniper/logs
sudo mkdir -p /opt/alpha-sniper/reports

# Set permissions
sudo chmod 777 /var/lib/alpha-sniper
sudo chmod 775 /opt/alpha-sniper/logs
sudo chmod 775 /opt/alpha-sniper/reports

# Set ownership
sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper
sudo chown -R ubuntu:ubuntu /opt/alpha-sniper/logs
sudo chown -R ubuntu:ubuntu /opt/alpha-sniper/reports
```

### Step 4: Clear Python Cache
```bash
find /opt/alpha-sniper/alpha-sniper -type d -name "__pycache__" -exec sudo rm -rf {} + 2>/dev/null || true
```

### Step 5: Reset Crash Loop and Restart
```bash
# Reset systemd failure counter
sudo systemctl reset-failed alpha-sniper-live.service

# Reload systemd configuration
sudo systemctl daemon-reload

# Start the service
sudo systemctl start alpha-sniper-live.service

# Check status
sudo systemctl status alpha-sniper-live.service
```

### Step 6: Verify Logs
```bash
# Watch live logs
sudo journalctl -u alpha-sniper-live.service -f

# Check for successful startup
sudo journalctl -u alpha-sniper-live.service --since "1 minute ago" | grep -i "watchdog\|telegram\|started"
```

## Expected Output

You should see:
```
✓ SYNTHETIC STOP WATCHDOG started
✓ Check interval: 1.0s
✓ Hard stop threshold: 2.0%
✓ Telegram bot initialized
✓ Bot started in LIVE mode
```

## Verification Checklist

- [ ] Service starts without errors
- [ ] `/opt/alpha-sniper/logs/bot.log` file is created
- [ ] No "Read-only file system" errors
- [ ] No "Permission denied" errors
- [ ] Watchdog initialized
- [ ] Telegram alerts working (check your Telegram)

## Troubleshooting

### If service still fails with read-only error:
```bash
# Check current systemd protection
sudo systemctl show alpha-sniper-live.service | grep ProtectSystem

# Should be empty or "false", NOT "strict" or "full"
```

### If positions.json errors occur:
```bash
# Verify write permissions
ls -lah /var/lib/alpha-sniper/
# Should show: drwxrwxrwx ubuntu ubuntu

# Test write access
sudo -u ubuntu touch /var/lib/alpha-sniper/test.tmp && sudo rm /var/lib/alpha-sniper/test.tmp
```

### Alternative: Disable File Logging (Last Resort)
If systemd approach fails, edit logger to use journal only:

```bash
# Edit logger.py
sudo nano /opt/alpha-sniper/alpha-sniper/utils/logger.py

# Comment out line 21:
# fh_info = logging.FileHandler("logs/bot.log")

# Comment out lines that add fh_info to logger
```

## Updated Environment Variables

Make sure `/etc/alpha-sniper/alpha-sniper-live.env` has the new variable names:

```bash
# Old (deprecated):
# HARD_STOP_PCT_PUMP=0.02
# HARD_STOP_WATCHDOG_INTERVAL=1.0

# New (required):
PUMP_MAX_LOSS_PCT=0.02
PUMP_MAX_LOSS_WATCHDOG_INTERVAL=1.0

# New Telegram controls:
TELEGRAM_TRADE_ALERTS=true
TELEGRAM_SCAN_SUMMARY=true
TELEGRAM_WHY_NO_TRADE=true
TELEGRAM_MAX_MSG_LEN=3500

# New VPS performance:
SCAN_UNIVERSE_MAX=800
SCAN_SLEEP_SECS=0
EXCHANGE_INFO_CACHE_SECONDS=300
```

## Success Criteria

Bot is successfully running when:
1. `systemctl status alpha-sniper-live.service` shows **active (running)**
2. No errors in `journalctl -u alpha-sniper-live.service -n 50`
3. Log file exists: `ls -lah /opt/alpha-sniper/logs/bot.log`
4. Telegram messages received (scan summary when next cycle runs)
5. Watchdog is monitoring: grep "WATCHDOG" in logs shows activity

## Support

If issues persist after following all steps:
1. Check full logs: `sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" --no-pager`
2. Verify git pull was successful: `cd /opt/alpha-sniper && git log -1`
3. Confirm Python version: `/opt/alpha-sniper/venv/bin/python --version` (should be 3.12+)
