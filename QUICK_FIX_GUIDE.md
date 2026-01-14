# Quick Fix Guide - Deploy Issues Resolved

## ✅ What Was Fixed

### 1. Missing Settings Error
**Error**: `ERROR: Unknown setting: EAGER_WALLET_RESERVE_USD`

**Fixed**: Added 3 missing settings to `settings.py`:
- `EAGER_WALLET_RESERVE_USD = 3.0`
- `ENTRY_WICK_BODY_MULT = 0.3`
- `ENTRY_WICK_BODY_MIN_PCT = 0.0005`

### 2. Auto-Tune System Added
**NEW**: Fully automatic parameter tuning every 6 hours
- No more manual adjustments needed
- System self-optimizes based on performance
- Safety limits prevent extreme values

---

## 🚀 Redeploy Instructions

**On production server, run:**

```bash
cd /opt/alpha-sniper/alpha-sniper

# Pull the fixes
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Redeploy (should work now)
cd /opt/alpha-sniper
sudo bash deploy_entry_quality.sh
```

This time it should complete without errors and install the auto-tune cron job.

---

## 📊 What You're Seeing (Current Performance)

From your monitoring output:

### ✅ **Good Signs:**
1. **Filters Working**: 47 rejections (33 EMA_TREND, 9 WICK, 5 ACCEL)
2. **Sizing Clamp Working**: Orders capped from $298 to $14-28 (respecting low balance)
3. **Thresholds Raised**: Now at ret5m=2.0% (from 0.8-1.0%)

### ⚠️ **Issues Detected:**
1. **AUTOTUNE_PRO still running** (at 13:13 - this should NOT happen!)
   - This means the oscillation fix didn't fully apply yet
   - Need to redeploy for AUTOTUNE_FLOW_ENABLE=False to take effect

2. **Zero trades in last 6 hours**
   - Filters may be TOO strict now
   - OR not enough time passed yet (filters just deployed)
   - Auto-tune will loosen if needed after 6 hours

---

## 🤖 How Auto-Tune Works

Once installed (after redeployment), the system will:

**Every 6 Hours (00:15, 06:15, 12:15, 18:15):**

1. **Check Performance**:
   - Win rate (target: 30-40%)
   - Trade frequency (target: 10-20/day)
   - Open rate (target: 40-90%)

2. **Auto-Adjust** (ONE change per cycle):

   - **Low Win Rate (<25%)**:
     - Tighten ret5m by +0.2%
     - Example: 1.8% → 2.0% → 2.2%

   - **Too Few Trades** (cand/cycle <0.2, wr>35%):
     - Loosen vspike by -0.2x
     - Example: 2.0x → 1.8x → 1.6x

   - **Low Open Rate** (<25%):
     - Increase epsilon by +0.03%
     - Example: 0.08% → 0.11% → 0.14%

   - **Good Win Rate** (≥30%):
     - Scale up risk by +0.05%
     - Example: 0.20% → 0.25% → 0.30%

3. **Safety Limits**:
   - ret5m: 1.4% - 3.5%
   - vspike: 1.5x - 4.0x
   - epsilon: 0.05% - 0.3%
   - risk: 0.10% - 0.5%

---

## 📝 Monitoring After Redeploy

### **Check Auto-Tune Is Installed:**
```bash
crontab -l | grep auto_tune
```
Should show:
```
15 */6 * * * /opt/alpha-sniper/auto_tune_service.sh '6 hours ago' >> /opt/alpha-sniper/logs/auto_tune_cron.log 2>&1
```

### **Watch Auto-Tune Decisions:**
```bash
tail -f /opt/alpha-sniper/logs/auto_tune.log
```

### **Run Manual Test (Don't Wait for Cron):**
```bash
/opt/alpha-sniper/auto_tune_service.sh '6 hours ago'
```

### **Monitor Performance:**
```bash
cd /opt/alpha-sniper
./monitor_entry_quality.sh "6 hours ago"
```

---

## 🎯 Expected Timeline

**Hour 0 (Now)**: Redeploy with fixes
- Filters active (EMA, ACCEL, WICK, BTC, SPREAD, VOL_QUALITY, REGIME)
- AutoTune oscillation stopped (AUTOTUNE_FLOW_ENABLE=False)
- Auto-tune cron installed

**Hour 6**: First auto-tune run
- Analyzes last 6 hours
- If 0 trades: Loosens vspike by -0.2x (2.0x → 1.8x)
- Logs decision to /opt/alpha-sniper/logs/auto_tune.log

**Hour 12**: Second auto-tune run
- If still few trades: Loosens more OR loosens ret5m
- If winrate low: Tightens instead

**Hour 24-48**: System converges
- Finds optimal balance between trade frequency and win rate
- Should stabilize at 30-40% win rate, 10-20 trades/day

---

## 🔧 Troubleshooting

### **Issue: Still seeing AUTOTUNE_PRO logs after redeploy**

**Check:**
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python scripts/overrides_cli.py get --key AUTOTUNE_FLOW_ENABLE
```

Should return: `False`

**If it returns True, manually fix:**
```bash
python scripts/overrides_cli.py set --key AUTOTUNE_FLOW_ENABLE --value false
sudo systemctl restart alpha-sniper-async.service
deactivate
```

### **Issue: Auto-tune not running**

**Check cron:**
```bash
crontab -l | grep auto_tune
```

**If missing, install manually:**
```bash
cd /opt/alpha-sniper
/opt/alpha-sniper/install_auto_tune.sh
```

### **Issue: Still no trades after 12 hours**

**Manual intervention (one-time):**
```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Loosen filters slightly
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 1.6
python scripts/overrides_cli.py set --key ENTRY_VOLUME_QUALITY_MULT --value 3.0

deactivate
```

Then let auto-tune take over after 6 hours.

---

## ✅ Success Criteria (24-48 Hours)

After redeployment and 24-48 hours of auto-tuning:

- [ ] No AUTOTUNE_PRO logs (oscillation stopped)
- [ ] Auto-tune running every 6 hours (check logs)
- [ ] Win rate trending upward (>20% after 24h, >30% after 48h)
- [ ] Trade frequency: 10-25/day
- [ ] Filter rejections balanced (no single filter >70%)
- [ ] Auto-tune making 1 adjustment per cycle (documented in logs)

---

**Status**: Ready for redeployment
**Branch**: `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Latest Commit**: `e0aa2361` (missing settings fixed)
