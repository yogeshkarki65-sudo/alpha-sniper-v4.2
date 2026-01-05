# EAGER Breakout Feature - Deployment Guide

## Quick Start (One-Shot Deployment)

### 1. Copy Deployment Script to Production Server

```bash
# On your local machine
scp deploy_eager.sh verify_eager.sh ubuntu@YOUR_SERVER_IP:/opt/alpha-sniper/

# OR on production server, pull from git
ssh ubuntu@YOUR_SERVER_IP
cd /opt/alpha-sniper
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
```

### 2. Run One-Shot Deployment

```bash
# SSH to production server
ssh ubuntu@YOUR_SERVER_IP

# Navigate to repo
cd /opt/alpha-sniper

# Make scripts executable
chmod +x deploy_eager.sh verify_eager.sh

# Run deployment (requires sudo)
sudo bash deploy_eager.sh
```

The deployment script will:
- ✅ Create automatic backup
- ✅ Pull latest code
- ✅ Validate Python syntax
- ✅ Test configuration
- ✅ Fix permissions
- ✅ Restart service
- ✅ Show initial logs

### 3. Verify Deployment

```bash
# Run verification script
bash verify_eager.sh
```

This will check:
- Service status
- EAGER configuration
- Recent logs
- Feature extraction
- Near-miss visibility

---

## Configuration

### EAGER is Disabled by Default

By default, `EAGER_ONLY_LIVE_TEST=True` which means EAGER only runs when `LIVE_TEST_MODE=True`.

**To enable EAGER in production** (after testing):

```bash
cd /opt/alpha-sniper

# Disable the LIVE_TEST gate
python scripts/overrides_cli.py set --key EAGER_ONLY_LIVE_TEST --value false

# Restart service
sudo systemctl restart alpha-sniper-async.service

# Verify
bash verify_eager.sh
```

### Adjusting EAGER Parameters

```bash
# More conservative (higher vspike required)
python scripts/overrides_cli.py set --key EAGER_VSPIKE_MIN --value 4.0

# More aggressive (allow more negative momentum)
python scripts/overrides_cli.py set --key EAGER_MAX_NEG_RET5M --value -0.005

# Tighter stop loss
python scripts/overrides_cli.py set --key EAGER_SL_PCT --value 0.005

# View all overrides
python scripts/overrides_cli.py show
```

**Changes take effect immediately** via RuntimeSettings overlay (no restart needed for most changes).

---

## Monitoring

### Watch EAGER Activity

```bash
# Monitor EAGER logs
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered EAGER

# Watch near-miss logs (top 3 candidates)
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered EARLY_TOP

# Watch all trades
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered 'OPENED\|CLOSED'
```

### Expected Log Output

**Near-miss logs** (when no signals):
```
[EARLY_TOP] HYPE/USDT ret5m=-0.12% vspike=3.5 score=28.5 accel=False wick=False depth=$15000
[EARLY_TOP] DOGE/USDT ret5m=0.45% vspike=2.8 score=19.5 accel=True wick=False depth=$22000
[EARLY_TOP] SHIB/USDT ret5m=-0.05% vspike=3.2 score=26.0 accel=False wick=True depth=$18000
```

**EAGER candidate rejected** (below threshold):
```
[EAGER] HYPE/USDT rejected by validate_order: below min size
```

**EAGER trade opened**:
```
[EAGER] OPENED HYPE/USDT @ 1.00580 size=$50.00 tp=1.02089 sl=0.99775
```

---

## Rollback

If you need to rollback:

```bash
cd /opt/alpha-sniper

# Find backup location from deployment output
ls -la /tmp/alpha-sniper-backup-*

# Get previous commit from backup
PREV_COMMIT=$(cat /tmp/alpha-sniper-backup-YYYYMMDD-HHMMSS/previous_commit.txt)

# Reset to previous commit
git reset --hard $PREV_COMMIT

# Restart service
sudo systemctl restart alpha-sniper-async.service
```

---

## Troubleshooting

### EAGER Not Running

**Check 1**: Verify EAGER_ONLY_LIVE_TEST setting
```bash
bash verify_eager.sh
```

**Check 2**: Check for candidates in logs
```bash
sudo journalctl -u alpha-sniper-async.service -n 100 | grep EARLY_TOP
```

If you see high vspike candidates (≥3.0) but no EAGER trades, check:
- `EAGER_ONLY_LIVE_TEST` - must be False OR `LIVE_TEST_MODE` must be True
- Candidates may fail wick filter, ret5m floor, or lookback high check

### Near-Miss Logs Showing Zero Depth

This is expected if orderbook fetch fails or is cached. Depth is best-effort only.

### Feature Extraction Showing Zeros

Run verification:
```bash
bash verify_eager.sh
```

Check "Feature Extraction" section. If all zeros, check logs for errors.

---

## EAGER Feature Summary

**What it does**:
- Catches high-volume consolidation breakouts
- Arms on: vspike ≥3.0, ret5m ≥-0.3%, no wick
- Fires on: breakout of last 5-candle high
- Tight risk: 0.8% SL, 1.5% TP

**Safety**:
- Only 1 eager trade per scan
- Limit IOC orders (no lingering)
- Respects all circuit breakers
- Disabled by default (EAGER_ONLY_LIVE_TEST=True)

**Expected results**:
- 0-1 eager trades per hour in calm markets
- Complements standard pump signals (2-3/hour)

---

## Support

**View documentation**:
```bash
cat /opt/alpha-sniper/AUTOTUNE_PRO_AND_EAGER_IMPLEMENTATION.md
```

**Check logs**:
```bash
sudo journalctl -u alpha-sniper-async.service -n 200 --no-pager
```

**Service status**:
```bash
sudo systemctl status alpha-sniper-async.service
```
