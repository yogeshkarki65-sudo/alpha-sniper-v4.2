# Alpha Sniper Entry Quality v2.0 - Complete Deployment Guide

## 🎯 What We Built

A complete entry quality improvement system with **7 intelligent filters**, **automated monitoring**, and **data-driven tuning suggestions** to fix the 14.39% win rate issue.

---

## 📦 Complete Feature List

### **Entry Quality Filters (7 Total)**

1. **EMA Trend Check** - Requires price above EMA50(1m) and EMA20(5m)
2. **Acceleration Check** - Current 5m momentum must exceed previous 5m
3. **Wick Filter** - Rejects wicks (upper_wick ≤ 0.3×body, body ≥ 0.05%)
4. **BTC Guard** - Skips longs when BTC 5m return < -0.3%
5. **Spread Cap** (NEW) - Rejects wide bid-ask spreads > 0.30%
6. **Volume Quality** (NEW) - Requires sustained 3-bar volume (4x 20-bar avg)
7. **Regime-Aware** (NEW) - Dynamic thresholds based on BTC momentum

### **AutoTune Fixes**

- ✅ Flow-based loosening disabled (stops oscillation)
- ✅ Win-rate-based tightening enabled
- ✅ 60-minute dwell time enforced
- ✅ Raised threshold bounds (1.4%-3.5% ret5m, 1.8x-4.0x vspike)

### **Monitoring & Tuning Tools**

- ✅ `monitor_entry_quality.sh` - Performance dashboard
- ✅ `suggest_tuning.sh` - Auto-generated optimization recommendations
- ✅ Enhanced Telegram notifications (complete portfolio breakdown)

### **Sizing & Safety**

- ✅ $3 wallet reserve buffer (prevents oversize orders)
- ✅ Proper cap sequencing (reserve → test mode → affordability)

---

## 🚀 Deployment Instructions

### **Step 1: Deploy to Production**

Run these commands on your **production server**:

```bash
cd /opt/alpha-sniper/alpha-sniper

# Pull all latest changes
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Run automated deployment script
sudo bash deploy_entry_quality.sh
```

**The script will:**
- Stop the service
- Pull latest code
- Apply all 20+ settings overrides
- Start the service
- Monitor logs for 30 seconds

---

### **Step 2: Verify Deployment (Immediate)**

**Check Telegram Notification:**

You should receive a startup message showing:
```
🚀 Alpha Sniper v4.2 ASYNC
💰 Total Portfolio Value: $171.XX
📊 Breakdown:
  • Free USDT: $XX.XX
  • Other Assets: $XX.XX
    BTC: 0.XXXX ($XX.XX)
    [other holdings...]
📈 Active Positions: X
⚙️ Test Mode: True
Status: ✅ ONLINE
```

**Check Logs:**

```bash
cd /opt/alpha-sniper/alpha-sniper

# Should see threshold logging
sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_THRESHOLDS
# Expected: [EAGER_THRESHOLDS] ret5m≥0.0180 vsp≥2.00 score≥6 depth≥$8000
```

---

### **Step 3: Monitor Performance (2-6 Hours)**

**Run the monitoring dashboard:**

```bash
cd /opt/alpha-sniper/alpha-sniper

# After 2 hours
./monitor_entry_quality.sh "2 hours ago"

# After 6 hours
./monitor_entry_quality.sh "6 hours ago"
```

**What to Look For:**

✅ **Good Signs:**
- Filter rejections appearing (EMA_TREND, WICK, SPREAD, VOL_QUALITY)
- No AUTOTUNE_PRO logs (oscillation stopped)
- Candidates/cycle: 0.3-1.0
- Attempt rate: 20-60%
- Open rate: 40-90%

⚠️ **Warning Signs:**
- No trades after 2 hours (filters too strict)
- Win rate still <20% after 10+ trades
- Many "capped by reserve" logs (balance too low)

---

### **Step 4: Get Tuning Suggestions (4-8 Hours)**

**Run the auto-tuning advisor:**

```bash
./suggest_tuning.sh "6 hours ago"
```

**It will analyze:**
- Win rate vs target (30-40%)
- Trade frequency (target 10-20/day)
- Flow rates (candidates, attempts, opens)
- Filter effectiveness

**And provide exact commands like:**

```bash
# If winrate low (<25%):
python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.020

# If trades too few (cand<0.2, wr>35%):
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 1.8

# If open rate low (<25%):
python scripts/overrides_cli.py set --key EAGER_EPS_PCT --value 0.0012

# If winrate good (>30%):
python scripts/overrides_cli.py set --key RISK_PER_TRADE --value 0.0025
```

---

## 📊 Understanding the Filters

### **Filter Execution Order:**

```
1. Basic checks (vspike, ret5m, wick, accel)
   ↓
2. EMA Trend (price > EMA50 & EMA20)
   ↓
3. Acceleration (current 5m > previous 5m)
   ↓
4. Wick Filter (reject long wicks, tiny bodies)
   ↓
5. BTC Guard (skip if BTC dropping)
   ↓
6. Spread Cap (reject illiquid books)
   ↓
7. Volume Quality (sustained volume check)
   ↓
8. Regime-Aware (dynamic threshold adjustment)
   ↓
9. ✅ PASS → Calculate sizing → Place order
```

### **What Each Filter Does:**

**Spread Cap (NEW)**
- **Problem**: Wide bid-ask spreads cause high slippage
- **Solution**: Reject if spread > 0.30%
- **Impact**: Protects from illiquid books, saves $$ on slippage

**Volume Quality (NEW)**
- **Problem**: One-print manipulations (single large candle, then dies)
- **Solution**: Require 3-bar avg volume > 4x 20-bar average
- **Impact**: Filters pump-and-dump schemes

**Regime-Aware (NEW)**
- **Problem**: Same thresholds in all market conditions
- **Solution**:
  - BTC down >0.5% → tighten (ret5m +0.2%, vspike +0.2x)
  - BTC up >0.5% → loosen (ret5m -0.1%)
- **Impact**: More selective in downtrends, rides uptrend beta

---

## 🎛️ Tuning Playbook

### **Scenario A: Low Win Rate (<25%)**

**Problem**: Taking too many losing trades

**Solution**: Tighten entry thresholds

```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Option 1: Tighten momentum
python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.020

# Option 2: Tighten volume
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 2.2

# Option 3: Stricter wick filter
python scripts/overrides_cli.py set --key ENTRY_WICK_BODY_MIN_PCT --value 0.0007

deactivate
```

**Monitor for 2-4 hours, then re-run `./monitor_entry_quality.sh`**

---

### **Scenario B: Too Few Trades (cand/cycle < 0.2, winrate > 35%)**

**Problem**: Filters too strict, missing good opportunities

**Solution**: Loosen thresholds slightly

```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Option 1: Loosen volume first (safer)
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 1.8

# Option 2: If still dry, loosen momentum
python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.016

deactivate
```

**Monitor for 2-4 hours, then re-run `./monitor_entry_quality.sh`**

---

### **Scenario C: Low Open Rate (<25%)**

**Problem**: Limit orders not filling (IOC rejected)

**Solution**: Increase trigger epsilon or depth requirement

```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Option 1: Bump trigger epsilon
python scripts/overrides_cli.py set --key EAGER_EPS_PCT --value 0.0012

# Option 2: Increase depth requirement
python scripts/overrides_cli.py set --key EAGER_MIN_DEPTH_USD --value 10000

deactivate
```

---

### **Scenario D: Good Win Rate (≥30%)**

**Problem**: System working well, ready to scale

**Solution**: Gradually increase position size

```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Increase risk per trade in small steps
# Current: 0.0020 (0.20%)
python scripts/overrides_cli.py set --key RISK_PER_TRADE --value 0.0025

# Monitor for 2-4 hours, then repeat if stable
# Next step: 0.0030, then 0.0035, etc.

deactivate
```

---

## 🔍 Live Monitoring Commands

### **Quick Dashboard (Recommended)**

```bash
cd /opt/alpha-sniper/alpha-sniper
./monitor_entry_quality.sh "6 hours ago"
```

### **Live Tail Specific Events**

```bash
# Watch thresholds (logged once per cycle)
sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_THRESHOLDS

# Watch filter rejections
sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_FILTERS

# Watch regime adjustments
sudo journalctl -u alpha-sniper-async.service -f | grep REGIME

# Watch AutoTune (should see NO "AUTOTUNE_PRO")
sudo journalctl -u alpha-sniper-async.service -f | grep AUTOTUNE

# Watch sizing clamps
sudo journalctl -u alpha-sniper-async.service -f | grep "capped by reserve"

# Watch everything important
sudo journalctl -u alpha-sniper-async.service -f -o cat \
| grep --line-buffered -E 'EAGER_THRESHOLDS|EAGER_FILTERS|REGIME|AUTOTUNE|capped'
```

---

## 📈 Expected Results

### **Before (Baseline):**
- Win Rate: 14.39% (2,119 trades)
- Trades/Day: 40-60
- AutoTune oscillation every 2 hours
- $350 order attempts on $170 balance
- Low quality entries (stables, memes, false breakouts)

### **After (Target):**
- Win Rate: **35-40%+** (quality over quantity)
- Trades/Day: **10-20** (fewer but higher conviction)
- **NO** AutoTune oscillation (flow-based disabled)
- Proper sizing with reserve buffer
- 7 filters reject low-probability setups
- Regime-aware adjustments for market conditions

---

## ⚙️ All Settings Applied

**Core Thresholds:**
- `EARLY_RET_5M_MIN = 0.018` (1.8% momentum)
- `EARLY_VOL_SPIKE_MIN = 2.0` (2x volume)
- `MIN_SCORE = 6`
- `EAGER_MIN_DEPTH_USD = 8000` ($8000 liquidity)
- `RISK_PER_TRADE = 0.0020` (0.20% per trade)

**AutoTune Controls:**
- `AUTOTUNE_FLOW_ENABLE = false` (disabled - stops oscillation)
- `WINRATE_ADJUST_ENABLE = true` (enabled)
- `AUTOTUNE_MIN_DWELL_MIN = 60` (60-minute minimum)

**Entry Filters (v1):**
- `ENTRY_TREND_EMA_CHECK_ENABLE = true`
- `ENTRY_ACCEL_ENABLE = true`
- `ENTRY_WICK_FILTER_ENABLE = true`
- `BTC_GUARD_ENABLE = true`
- `BTC_RET5M_MIN = -0.003` (-0.3%)

**Entry Filters (v2 - NEW):**
- `ENTRY_SPREAD_CAP_ENABLE = true`
- `ENTRY_SPREAD_MAX_PCT = 0.0030` (0.30%)
- `ENTRY_VOLUME_QUALITY_ENABLE = true`
- `ENTRY_VOLUME_QUALITY_MULT = 4.0`
- `ENTRY_REGIME_AWARE_ENABLE = true`
- `ENTRY_REGIME_STRICT_BTC_PCT = -0.005` (-0.5%)
- `ENTRY_REGIME_LOOSE_BTC_PCT = 0.005` (+0.5%)
- `ENTRY_REGIME_STRICT_RET5M_ADD = 0.002` (+0.2%)
- `ENTRY_REGIME_STRICT_VSPIKE_ADD = 0.2` (+0.2x)
- `ENTRY_REGIME_LOOSE_RET5M_SUB = 0.001` (-0.1%)

**Sizing:**
- `EAGER_WALLET_RESERVE_USD = 3.0` ($3 reserve)

**Universe:**
- `UNIVERSE_EXCLUDE_REGEX` - Excludes stables and memes

---

## 🛠️ Troubleshooting

### **Issue: No trades after 2 hours**

**Check:**
```bash
./monitor_entry_quality.sh "2 hours ago"
```

**Look at filter breakdown** - which filter is rejecting most?

**Solution:**
- If many SPREAD rejections: Normal, protecting from slippage
- If many EMA_TREND rejections: Market may be choppy, wait
- If many VOL_QUALITY rejections: Loosen `ENTRY_VOLUME_QUALITY_MULT` to 3.0
- If candidates/cycle < 0.1: Loosen `EARLY_VOL_SPIKE_MIN` to 1.8

---

### **Issue: Still seeing oscillation**

**Check:**
```bash
sudo journalctl -u alpha-sniper-async.service --since "1 hour ago" | grep AUTOTUNE_PRO
```

**If you see AUTOTUNE_PRO logs:**
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python scripts/overrides_cli.py get --key AUTOTUNE_FLOW_ENABLE
# Should return: false
deactivate
```

**If it's true, set it to false:**
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python scripts/overrides_cli.py set --key AUTOTUNE_FLOW_ENABLE --value false
sudo systemctl restart alpha-sniper-async.service
deactivate
```

---

### **Issue: Win rate improving but P&L still negative**

**This is normal!** It takes time for good trades to outweigh past losses.

**Check:**
```bash
./monitor_entry_quality.sh "24 hours ago"
```

**Look at avg_winner vs avg_loser:**
- Target: avg_winner ≥ |avg_loser| (at least 1:1 risk-reward)
- If avg_winner < |avg_loser|: Hold Brain may be cutting winners too early
- Solution: Let it run 48+ hours to see full cycle

---

## 📚 Files Modified

1. **app_async.py** - Added 3 new filters (66 lines), enhanced startup notification (90 lines)
2. **alpha-sniper/config/settings.py** - Added 11 new parameters
3. **deploy_entry_quality.sh** - Updated with v2 filter settings
4. **monitor_entry_quality.sh** - NEW: 200+ line monitoring dashboard
5. **suggest_tuning.sh** - NEW: 180+ line auto-tuning advisor
6. **DEPLOYMENT_GUIDE.md** - NEW: This comprehensive guide

---

## ✅ Deployment Checklist

- [ ] Code deployed to production (`git reset --hard origin/...`)
- [ ] Deployment script executed (`sudo bash deploy_entry_quality.sh`)
- [ ] Telegram startup notification received (portfolio breakdown shown)
- [ ] Threshold logging visible (`[EAGER_THRESHOLDS]` in logs)
- [ ] Filter rejections appearing (`[EAGER_FILTERS]` in logs)
- [ ] No AUTOTUNE_PRO logs (oscillation stopped)
- [ ] Monitoring dashboard runs (`./monitor_entry_quality.sh`)
- [ ] Tuning script runs (`./suggest_tuning.sh`)

---

## 🎯 Success Criteria (24-48 Hours)

**After 24 hours:**
- [ ] Win rate trending upward (>20%)
- [ ] Trade frequency 10-25/day
- [ ] No AutoTune oscillation
- [ ] No oversize orders
- [ ] Filter rejections balanced (no single filter rejecting >70%)

**After 48 hours:**
- [ ] Win rate ≥30%
- [ ] Trade frequency 10-20/day
- [ ] Avg winner ≥ avg loser (1:1 risk-reward minimum)
- [ ] P&L trend positive (recent 24h > previous 24h)

---

**Branch**: `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Status**: ✅ READY FOR DEPLOYMENT
**Version**: v2.0 (7 filters + monitoring tools)
**Date**: 2026-01-14
