# Critical LIVE Mode Fixes - Deployment Guide

**Commit:** `99953f9`
**Branch:** `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Status:** ✅ Ready for immediate deployment

---

## 🔴 Problems Fixed

### Problem 1: Equity Sync Catastrophic Drop Loop
**Symptom:** Bot permanently stuck in DEFENSE mode on every restart

**Root cause:**
- Config `starting_equity = $1000`
- Real MEXC balance = $58
- SafeEquitySync saw 94% deviation every time
- Rejected update and forced DDL into DEFENSE permanently

**Fix:** First-run detection logic
- On first sync in LIVE mode: detect if `current_equity == config_starting_equity`
- If true: ACCEPT MEXC balance as ground truth baseline
- Skip all deviation checks on first run
- Log: `[EQUITY_SYNC] FIRST RUN DETECTED: Using MEXC balance as baseline`

### Problem 2: Positions Path Fragmentation
**Symptom:** Positions file written to wrong location, permission errors

**Root cause:**
- PathManager defaulted to `/opt/alpha-sniper/data/` (tier 2 fallback)
- systemd only allowed `/var/lib/alpha-sniper/`
- Fragmented data across multiple directories

**Fix:** Unified data path via environment variable
- Added `ALPHA_SNIPER_DATA_DIR=/var/lib/alpha-sniper` to systemd
- Forces PathManager to use tier 1 (env var)
- All data now unified under `/var/lib/alpha-sniper/`

---

## 📂 Files Changed

1. **`alpha-sniper/core/safe_equity_sync.py`**
   - Added `config_starting_equity` parameter
   - First-run detection (lines 135-162)
   - Accept MEXC balance on first run

2. **`alpha-sniper/main.py`**
   - Pass `config_starting_equity` to `sync_equity()` call

3. **`deployment/alpha-sniper-live.service`**
   - Added `Environment="ALPHA_SNIPER_DATA_DIR=/var/lib/alpha-sniper"`

---

## 🚀 Deployment Instructions

### On Production Server:

```bash
# 1. Navigate to repo
cd /opt/alpha-sniper

# 2. Pull latest changes
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# 3. Clear Python cache (CRITICAL!)
find /opt/alpha-sniper -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /opt/alpha-sniper -type f -name "*.pyc" -delete 2>/dev/null || true

# 4. Backup current service file
sudo cp /etc/systemd/system/alpha-sniper-live.service /etc/systemd/system/alpha-sniper-live.service.backup

# 5. Copy updated service file
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.service /etc/systemd/system/alpha-sniper-live.service

# 6. Reload systemd daemon
sudo systemctl daemon-reload

# 7. Verify service file loaded correctly
sudo systemctl cat alpha-sniper-live.service | grep ALPHA_SNIPER_DATA_DIR
# Should output: Environment="ALPHA_SNIPER_DATA_DIR=/var/lib/alpha-sniper"

# 8. Restart service
sudo systemctl restart alpha-sniper-live.service

# 9. Monitor logs for first-run detection
sudo journalctl -u alpha-sniper-live.service -f --no-hostname -o cat | grep -E "EQUITY_SYNC|FIRST_RUN|📂|💰"
```

---

## ✅ Expected Log Output (First Run)

### Before Fix (OLD - BROKEN):
```
Starting Equity: $1000.00
[EQUITY_SYNC] Large deviation: 94.1% ($1000.00 → $58.56)
[EQUITY_SYNC] CATASTROPHIC DROP PREVENTED
[EQUITY_SYNC] Success | prev=$1000 | computed=$58.56 | final=$1000
[ERROR] Forcing DDL to DEFENSE mode due to equity sync anomaly
```

### After Fix (NEW - CORRECT):
```
Starting Equity: $1000.00
[EQUITY_SYNC] FIRST RUN DETECTED: config_starting_equity=$1000.00, MEXC_balance=$58.56. Using MEXC balance as baseline (ignoring config value in LIVE mode).
[EQUITY_SYNC] Success | prev=$1000.00 | computed=$58.56 | final=$58.56 | coverage=100.0% | priced=5 | unpriced=0
💰 Equity updated: $1000.00 → $58.56 (+0.00%)
📂 Positions file: /var/lib/alpha-sniper/positions/positions.json
```

### Subsequent Runs (No Longer First Run):
```
[EQUITY_SYNC] Portfolio valuation: USDT=$45.23 | Other=$13.33 | Total=$58.56 | Priced=5 | Unpriced=0
[EQUITY_SYNC] Success | prev=$58.56 | computed=$58.56 | final=$58.56 | coverage=100.0% | priced=5 | unpriced=0
💰 Equity updated: $58.56 → $58.56 (+0.00%)
```

---

## 🔍 Verification Checklist

After deployment, verify:

### ✅ Equity Sync Works Correctly
- [ ] See `[EQUITY_SYNC] FIRST RUN DETECTED` on first startup
- [ ] Equity updates from $1000 → $58 (or actual MEXC balance)
- [ ] NO "CATASTROPHIC DROP PREVENTED" error
- [ ] NO "Forcing DDL to DEFENSE" error
- [ ] DDL stays in GRIND or HARVEST (based on opportunity density)

### ✅ Data Path Unified
- [ ] Positions file written to: `/var/lib/alpha-sniper/positions/positions.json`
- [ ] NO permission errors
- [ ] NO references to `/opt/alpha-sniper/data/positions/positions.json`
- [ ] All metrics/quarantine/DDL state under `/var/lib/alpha-sniper/`

### ✅ Bot Behavior Normal
- [ ] DDL switches modes based on density (not stuck in DEFENSE)
- [ ] Positions can be opened (if signals generated)
- [ ] Override values show in `[DDL_ACTIVE]` logs
- [ ] No repeated equity sync warnings

---

## 🔧 Troubleshooting

### Issue: Still seeing "CATASTROPHIC DROP PREVENTED"

**Cause:** Python cache not cleared, old code still loaded

**Fix:**
```bash
# Stop service
sudo systemctl stop alpha-sniper-live.service

# Clear cache thoroughly
find /opt/alpha-sniper -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find /opt/alpha-sniper -type f -name "*.pyc" -delete 2>/dev/null || true
find /home/ubuntu/.cache/Python* -type d -name "*alpha*" -exec rm -rf {} + 2>/dev/null || true

# Verify new code
grep -n "FIRST RUN DETECTED" /opt/alpha-sniper/alpha-sniper/core/safe_equity_sync.py
# Should show the new code on line ~142

# Restart
sudo systemctl start alpha-sniper-live.service
```

### Issue: Positions file still at /opt/alpha-sniper/data/

**Cause:** Systemd env var not loaded

**Fix:**
```bash
# Verify env var in service
sudo systemctl cat alpha-sniper-live.service | grep ALPHA_SNIPER_DATA_DIR

# If missing, ensure service file copied correctly
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.service /etc/systemd/system/alpha-sniper-live.service
sudo systemctl daemon-reload
sudo systemctl restart alpha-sniper-live.service

# Verify PathManager picked up env var
sudo journalctl -u alpha-sniper-live.service -n 100 | grep "Positions file:"
# Should show: /var/lib/alpha-sniper/positions/positions.json
```

### Issue: DDL still stuck in DEFENSE

**Cause:** DDL state persisted from previous run

**Fix:**
```bash
# Remove old DDL state
sudo rm -f /var/lib/alpha-sniper/metrics/ddl_state.json
sudo rm -f /opt/alpha-sniper/data/metrics/ddl_state.json
sudo systemctl restart alpha-sniper-live.service
```

---

## 🎯 Key Behavioral Changes

### Before Fix:
1. **Every restart:** Equity sync fails → DDL forced to DEFENSE
2. **Positions:** Written to `/opt/alpha-sniper/data/` (wrong path)
3. **Data:** Fragmented across multiple directories
4. **Trading:** Severely limited (DEFENSE = 0.5x size, 1 position max)

### After Fix:
1. **First run:** MEXC balance accepted as baseline (~$58)
2. **Subsequent runs:** Normal equity sync with deviation checks
3. **Positions:** Unified at `/var/lib/alpha-sniper/positions/`
4. **Data:** All under `/var/lib/alpha-sniper/`
5. **Trading:** Normal behavior (DDL adapts to market, not stuck in DEFENSE)

---

## 📊 DDL Mode Comparison

| Mode | Size Multiplier | Max Positions | Scratch Timeout | When Active |
|------|----------------|---------------|-----------------|-------------|
| **HARVEST** | 1.2x | 3 | 30s | High density (>0.70) |
| **GRIND** | 1.0x | 2 | 60s | Medium density (0.40-0.70) |
| **DEFENSE** | 0.5x | 1 | 20s | Low density (<0.25) |
| **OBSERVE** | 0.0x (paper) | 0 | N/A | Disabled |

**Before fix:** Bot always started in DEFENSE (due to equity sync failure)
**After fix:** Bot starts in GRIND, adapts based on real market density

---

## 📝 Commit Details

**Commit:** `99953f9`
**Message:** `fix: Critical LIVE mode fixes - equity sync first-run + unified data path`
**Files changed:** 3
**Lines changed:** +36 -2

---

## 🔒 Safety Notes

- These fixes are **safe** for live trading
- First-run detection only triggers once (when equity == config value)
- After first run, normal deviation checks resume
- Data path unification prevents permission errors
- No risk to existing positions or trading logic

---

## 🆘 Rollback (If Needed)

If critical issues arise:

```bash
# Stop service
sudo systemctl stop alpha-sniper-live.service

# Restore backup service file
sudo cp /etc/systemd/system/alpha-sniper-live.service.backup /etc/systemd/system/alpha-sniper-live.service

# Rollback code
cd /opt/alpha-sniper
git reset --hard 36c5a76  # Previous commit

# Clear cache
find /opt/alpha-sniper -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl start alpha-sniper-live.service
```

---

**END OF DEPLOYMENT GUIDE**
