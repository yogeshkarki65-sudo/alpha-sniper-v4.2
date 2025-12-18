# Alpha Sniper V4.2 - Production Deployment (Quick Start)

## 🚨 Current Issue
Bot crashes with: **Read-only file system error on `/opt/alpha-sniper/logs/bot.log`**

## ✅ Fix (5 Minutes)

### On Production Server:

```bash
# 1. Navigate to bot directory
cd /opt/alpha-sniper

# 2. Pull latest code (includes deployment fixes)
git fetch origin
git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# 3. Stop the service
sudo systemctl stop alpha-sniper-live.service

# 4. Apply corrected systemd service file
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.service /etc/systemd/system/alpha-sniper-live.service

# 5. Fix all permissions
sudo mkdir -p /var/lib/alpha-sniper /opt/alpha-sniper/logs /opt/alpha-sniper/reports
sudo chmod 777 /var/lib/alpha-sniper
sudo chmod 775 /opt/alpha-sniper/logs /opt/alpha-sniper/reports
sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper /opt/alpha-sniper/logs /opt/alpha-sniper/reports

# 6. Clear Python cache
find /opt/alpha-sniper/alpha-sniper -type d -name "__pycache__" -exec sudo rm -rf {} + 2>/dev/null || true

# 7. Reset crash loop and restart
sudo systemctl reset-failed alpha-sniper-live.service
sudo systemctl daemon-reload
sudo systemctl start alpha-sniper-live.service

# 8. Check status
sudo systemctl status alpha-sniper-live.service

# 9. Watch live logs
sudo journalctl -u alpha-sniper-live.service -f
```

## ✅ Expected Output

You should see:
```
🛡️ SYNTHETIC STOP WATCHDOG started
   Check interval: 1.0s
   Hard stop threshold: 2.0%
📱 Telegram bot initialized
✅ Bot started in LIVE mode
🔍 Scan cycle starting...
```

## 📋 Update Environment Variables (Optional but Recommended)

Edit your env file to use new variable names:

```bash
sudo nano /etc/alpha-sniper/alpha-sniper-live.env
```

**Find and replace:**
```bash
# OLD (deprecated)
HARD_STOP_PCT_PUMP=0.02
HARD_STOP_WATCHDOG_INTERVAL=1.0

# NEW (use these instead)
PUMP_MAX_LOSS_PCT=0.02
PUMP_MAX_LOSS_WATCHDOG_INTERVAL=1.0
```

**Add new features:**
```bash
# Telegram full story alerts
TELEGRAM_TRADE_ALERTS=true
TELEGRAM_SCAN_SUMMARY=true
TELEGRAM_WHY_NO_TRADE=true
TELEGRAM_MAX_MSG_LEN=3500

# VPS performance optimization
SCAN_UNIVERSE_MAX=800
EXCHANGE_INFO_CACHE_SECONDS=300
```

Or use the complete template:
```bash
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.env.template /etc/alpha-sniper/alpha-sniper-live.env
sudo nano /etc/alpha-sniper/alpha-sniper-live.env  # Fill in API keys
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
sudo systemctl restart alpha-sniper-live.service
```

## 🎯 New Features in This Update

1. **PUMP_MAX_LOSS_PCT** - Renamed from HARD_STOP_PCT_PUMP (more accurate name)
   - Per-regime overrides: `PUMP_MAX_LOSS_PCT_SIDEWAYS`, `PUMP_MAX_LOSS_PCT_STRONG_BULL`, etc.

2. **Telegram Full Story** - Comprehensive alerts
   - Scan cycle summaries with regime and top signals
   - Detailed entry notifications (score, triggers, liquidity, stops)
   - Detailed exit notifications (PnL, hold time, reason)
   - "Why no trade" explanations

3. **VPS Performance** - Optimization for low-memory servers
   - `SCAN_UNIVERSE_MAX=800` limits symbols scanned
   - Exchange info caching reduces API calls
   - Configurable scan pacing

4. **CodeRabbit Fetcher** - Download PR reviews offline
   - Script: `/opt/alpha-sniper/scripts/fetch_coderabbit_report.sh`
   - Usage: `./scripts/fetch_coderabbit_report.sh yogeshkarki65-sudo alpha-sniper-v4.2 123`

## 🔍 Verification

After deployment, verify:

```bash
# Service is running
sudo systemctl status alpha-sniper-live.service
# Should show: active (running)

# Log file created
ls -lah /opt/alpha-sniper/logs/bot.log
# Should exist with recent timestamp

# No errors
sudo journalctl -u alpha-sniper-live.service --since "2 minutes ago" | grep -i error
# Should be empty or only startup warnings

# Watchdog active
sudo journalctl -u alpha-sniper-live.service --since "2 minutes ago" | grep WATCHDOG
# Should show watchdog initialization

# Telegram working
# Check your Telegram - you should receive scan summaries within 5 minutes
```

## ❓ Troubleshooting

**Issue: Still getting read-only filesystem error**
```bash
# Check systemd service has ReadWritePaths
grep ReadWritePaths /etc/systemd/system/alpha-sniper-live.service
# Should show 3 paths: /var/lib/alpha-sniper, /opt/alpha-sniper/logs, /opt/alpha-sniper/reports
```

**Issue: Permission denied on positions.json**
```bash
# Verify directory is writable
ls -lah /var/lib/alpha-sniper/
# Should show: drwxrwxrwx ubuntu ubuntu

# Test write access
sudo -u ubuntu touch /var/lib/alpha-sniper/test.tmp && sudo rm /var/lib/alpha-sniper/test.tmp
# Should complete without error
```

**Issue: Service in crash loop**
```bash
# Reset the failure counter
sudo systemctl reset-failed alpha-sniper-live.service
sudo systemctl start alpha-sniper-live.service
```

## 📚 Detailed Documentation

- **Deployment Fix Guide**: `/opt/alpha-sniper/deployment/DEPLOYMENT_FIX.md`
- **Full Configuration**: `/opt/alpha-sniper/deployment/alpha-sniper-live.env.template`
- **README**: `/opt/alpha-sniper/README.md` (updated with all new features)

## 🎉 Success Criteria

Bot is successfully deployed when:
1. ✅ Service status shows **active (running)**
2. ✅ No errors in logs
3. ✅ Log file exists: `/opt/alpha-sniper/logs/bot.log`
4. ✅ Telegram scan summary received
5. ✅ Watchdog monitoring active

---

**Need Help?** See `DEPLOYMENT_FIX.md` for detailed troubleshooting steps.
