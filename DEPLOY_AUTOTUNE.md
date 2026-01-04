# Deploy AutoTune Pro to Production

**Version**: v4.2 + AutoTune Pro
**Date**: 2026-01-04
**Commit**: be0efcf1

## What's New

🤖 **AutoTune Pro** - Self-adjusting threshold system that eliminates 0-trade periods by automatically adapting to market conditions.

### Features
- ✅ Auto-adjust signal thresholds to target 1-8 signals/hour
- ✅ Sizing autopilot (scales risk based on performance)
- ✅ Auto-disable LIVE_TEST_MODE after 20+ profitable trades
- ✅ Runtime overrides (no restart needed)
- ✅ CLI for manual threshold management
- ✅ Daily digest includes autotune metrics

---

## Pre-Deployment Checklist

- [ ] Bot is running on production server at `/opt/alpha-sniper`
- [ ] You have SSH access to the server
- [ ] Current branch is pushed to git: `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`

---

## Deployment Steps

### Step 1: SSH to Production Server

```bash
ssh user@your-server-ip
cd /opt/alpha-sniper
```

### Step 2: Pull Latest Changes

```bash
# Fetch latest from git
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Switch to the branch
git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Pull latest commits
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
```

### Step 3: Verify New Files Exist

```bash
# Check new AutoTune files
ls -lh alpha-sniper/config/runtime_settings.py
ls -lh alpha-sniper/core/autotune.py
ls -lh scripts/overrides_cli.py

# Verify updated files
ls -lh alpha-sniper/config/settings.py
ls -lh app_async.py
```

**Expected output**: All files should exist and have recent timestamps.

### Step 4: Create Data Directory for Overrides

```bash
# Create data directory if it doesn't exist
mkdir -p /opt/alpha-sniper/data
chmod 755 /opt/alpha-sniper/data
```

### Step 5: Restart the Bot

```bash
sudo systemctl restart alpha-sniper-async.service
```

### Step 6: Verify Startup

```bash
# Watch startup logs
sudo journalctl -u alpha-sniper-async.service -f
```

**Look for these log lines:**
```
Loading runtime overrides...
Initializing AutoTune Pro...
AutoTune Pro initialized (enabled: True)
```

Press `Ctrl+C` to stop watching logs.

### Step 7: Check First Scan

Wait for the first scan cycle (60 seconds), then check:

```bash
# Check recent logs
sudo journalctl -u alpha-sniper-async.service -n 100 --no-pager | grep -E "AUTOTUNE|Signals generated"
```

**Expected**: You should see autotune tracking signal counts.

---

## Monitoring AutoTune

### Watch Threshold Adjustments

```bash
# Watch for autotune adjustments in real-time
sudo journalctl -u alpha-sniper-async.service -f | grep AUTOTUNE_PRO
```

**Example log:**
```
[AUTOTUNE_PRO] signals/hr=0.32 -> RET5M=0.0140, VSP=1.40, SCORE=14
```

### View Current Overrides

```bash
# Show all current overrides
python /opt/alpha-sniper/scripts/overrides_cli.py show
```

**Example output:**
```json
{
  "EARLY_RET_5M_MIN": 0.012,
  "EARLY_VOL_SPIKE_MIN": 1.3,
  "MIN_SCORE": 10
}
```

### Manual Override (if needed)

```bash
# Lower MIN_SCORE manually
python /opt/alpha-sniper/scripts/overrides_cli.py set --key MIN_SCORE --value 8

# Verify change
python /opt/alpha-sniper/scripts/overrides_cli.py get --key MIN_SCORE

# Reset all overrides
python /opt/alpha-sniper/scripts/overrides_cli.py reset
```

**Note**: Changes take effect immediately (no restart needed).

---

## Expected Behavior

### First Hour
- Bot starts with default thresholds (RET5M=0.015, VSpike=1.5, Score=15)
- If 0 signals for ~30 mins, autotune starts lowering thresholds
- Adjustments every 5 scans (~5 minutes)

### After 1-2 Hours
- Thresholds should stabilize in range that generates 1-8 signals/hour
- Check daily digest for summary

### After 20+ Trades (with good performance)
- If avgR ≥ 0.60, winrate ≥ 55%, low slippage, low IOC rejects
- Bot automatically flips LIVE_TEST_MODE=False
- Check logs for: `[LIVE_FLIP] LIVE_TEST_MODE=False`

---

## Rollback Plan (if needed)

If something goes wrong:

```bash
# Switch back to main branch
cd /opt/alpha-sniper
git checkout main
git pull origin main

# Restart service
sudo systemctl restart alpha-sniper-async.service

# Verify rollback
sudo journalctl -u alpha-sniper-async.service -n 50 --no-pager
```

---

## Configuration Reference

### AutoTune Settings (in .env or runtime override)

```env
# Enable/disable autotune
ALPHA_AUTOTUNE_ENABLE=true

# Target signals per hour (autotune adjusts to hit this range)
ALPHA_AUTOTUNE_TARGET_MIN_HOURLY=1
ALPHA_AUTOTUNE_TARGET_MAX_HOURLY=8

# Adjustment step sizes
ALPHA_AUTOTUNE_STEP_RET5M=0.001     # ±0.10% per step
ALPHA_AUTOTUNE_STEP_VSPIKE=0.10     # ±0.10x per step
ALPHA_AUTOTUNE_STEP_SCORE=1         # ±1 per step

# Safety bounds
ALPHA_AUTOTUNE_RET5M_BOUNDS=(0.008, 0.035)   # 0.8%-3.5%
ALPHA_AUTOTUNE_VSPIKE_BOUNDS=(1.10, 4.00)    # 1.1x-4.0x
ALPHA_AUTOTUNE_SCORE_BOUNDS=(3, 40)          # 3-40

# Sizing autopilot
ALPHA_SIZING_AUTOPILOT_ENABLE=true
ALPHA_SIZING_UP_AVG_R_MIN=0.60
ALPHA_SIZING_DOWN_AVG_R_MAX=-0.25

# Live flip guardrails
ALPHA_LIVE_FLIP_ENABLE=true
ALPHA_LIVE_FLIP_MIN_TRADES=20
ALPHA_LIVE_FLIP_MIN_AVG_R=0.60
ALPHA_LIVE_FLIP_MIN_WINRATE=0.55
```

---

## Troubleshooting

### Problem: Bot not adjusting thresholds

**Check:**
```bash
python /opt/alpha-sniper/scripts/overrides_cli.py show
```

**If empty**, autotune hasn't triggered yet. Wait for 30+ mins of 0 signals.

**If not empty**, check cooldown:
```bash
# Autotune adjusts every 5 scans minimum
# With 60s scans, that's ~5 minutes between adjustments
```

### Problem: "No module named 'config.runtime_settings'"

**Solution:**
```bash
cd /opt/alpha-sniper
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
sudo systemctl restart alpha-sniper-async.service
```

### Problem: Too many signals

**Manual fix:**
```bash
# Raise thresholds temporarily
python /opt/alpha-sniper/scripts/overrides_cli.py set --key MIN_SCORE --value 20
python /opt/alpha-sniper/scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.020
```

Autotune will continue adjusting from these new values.

---

## Daily Digest Enhancement

After deployment, your daily Telegram digest will include:

```
📊 Daily Digest - 2026-01-04

Trades: 12 (8W / 4L)
Win Rate: 66.7%
PnL: $145.23

Orders: 15/18 filled
IOC Rejects: 2
Avg Slippage: 28.3 bps

Open Positions: 2

🤖 AutoTune Pro
Signals/hr: 3.2  Slip(p95): 35bps
IOC Rej: 11%  AvgR: 0.82  Win: 67%
RET5M: 0.0125  VSpk: 1.35
Score: 12  Risk: 0.0038
Test Mode: False
```

---

## Success Criteria

✅ **Bot starts successfully** with autotune logs
✅ **Thresholds adjust** within first hour (if 0 signals)
✅ **Signals generated** within 2 hours
✅ **Daily digest** includes autotune snapshot
✅ **Runtime overrides** work via CLI

---

## Support

**Check logs:**
```bash
sudo journalctl -u alpha-sniper-async.service -n 500 --no-pager
```

**Check service status:**
```bash
sudo systemctl status alpha-sniper-async.service
```

**Restart service:**
```bash
sudo systemctl restart alpha-sniper-async.service
```

**View autotune state:**
```bash
python /opt/alpha-sniper/scripts/overrides_cli.py show
```
