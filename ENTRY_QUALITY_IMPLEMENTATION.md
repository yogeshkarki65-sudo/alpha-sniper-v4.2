# Entry Quality Implementation Summary

## Status: ✅ COMPLETE

### Implementation Overview

This implementation addresses the 14.39% win rate issue by implementing quality-first entry selection and eliminating AutoTune oscillation. All changes have been completed and are ready for deployment.

---

## ✅ Completed Changes

### 1. Settings Parameters Added (`settings.py`)

**AutoTune Control Parameters:**
- `AUTOTUNE_FLOW_ENABLE = False` - Disable flow-based loosening to prevent oscillation
- `WINRATE_ADJUST_ENABLE = True` - Enable win-rate-based tightening
- `AUTOTUNE_MIN_DWELL_MIN = 60` - Minimum 60 minutes between adjustments
- `AUTOTUNE_RET5M_STEP = 0.001` - Configurable step size (±0.10%)
- `AUTOTUNE_VSPIKE_STEP = 0.1` - Configurable volume step size (±0.10x)
- `AUTOTUNE_RET5M_BOUNDS = (0.014, 0.035)` - Raised floor from 0.008 to 0.014 (1.4%)
- `AUTOTUNE_VSPIKE_BOUNDS = (1.8, 4.00)` - Raised floor from 1.1 to 1.8 (1.8x)

**Entry Quality Filter Flags:**
- `ENTRY_TREND_EMA_CHECK_ENABLE = True` - EMA trend filter
- `ENTRY_ACCEL_ENABLE = True` - Momentum acceleration filter
- `ENTRY_WICK_FILTER_ENABLE = True` - Enhanced wick filter
- `BTC_GUARD_ENABLE = True` - BTC correlation guard
- `BTC_RET5M_MIN = -0.003` - BTC 5m return threshold (-0.3%)

**Sizing Controls:**
- `EAGER_WALLET_RESERVE_USD = 3.0` - Reserve buffer to prevent oversize orders
- `ENTRY_WICK_BODY_MULT = 0.3` - Upper wick threshold (30% of body)
- `ENTRY_WICK_BODY_MIN_PCT = 0.0005` - Minimum body size (0.05%)

**Location:** `alpha-sniper/config/settings.py`

---

### 2. AutoTune Modified (`autotune.py`)

**Changes:**
- Flow-based loosening (`maybe_tune()`) now gated by `AUTOTUNE_FLOW_ENABLE` flag (disabled by default)
- Win-rate adjustment (`maybe_adjust_for_low_winrate()`) respects `WINRATE_ADJUST_ENABLE` flag
- Dwell time enforcement: Minimum 60 minutes between adjustments to prevent rapid oscillation
- Step sizes now configurable via `AUTOTUNE_RET5M_STEP` and `AUTOTUNE_VSPIKE_STEP`
- Bounds respect new raised floors (1.4% ret5m, 1.8x vspike)

**Location:** `alpha-sniper/core/autotune.py`

---

### 3. Entry Quality Filters Implemented (`app_async.py`)

**Added 4 entry filters in EAGER scanner (lines 979-1053):**

#### Filter 1: EMA Trend Check
- Calculates EMA50 on 1-minute candles
- Calculates EMA20 on 5-minute candles (using every 5th 1m candle)
- Rejects if current price ≤ EMA50 or current price ≤ EMA20
- Logging: `[EAGER_FILTERS] {sym} REJECT=EMA_TREND price={x} ema50={y} ema20={z}`

#### Filter 2: Acceleration Check (Enhanced)
- Compares current 5m return (last 5 candles) vs previous 5m return (candles -6 to -10)
- Rejects if current 5m return ≤ previous 5m return (momentum not accelerating)
- Logging: `[EAGER_FILTERS] {sym} REJECT=ACCEL current={x} prev={y}`

#### Filter 3: Wick Filter (Enhanced)
- Analyzes latest candle OHLC structure
- Calculates body, upper wick, and body percentage
- Rejects if upper_wick > 0.3 × body OR body_pct < 0.05%
- Configurable via `ENTRY_WICK_BODY_MULT` and `ENTRY_WICK_BODY_MIN_PCT`
- Logging: `[EAGER_FILTERS] {sym} REJECT=WICK upper_wick={x} body={y} body_pct={z}`

#### Filter 4: BTC Guard
- Fetches BTC/USDT 5m return from market_data
- Rejects longs if BTC 5m return < -0.3% (configurable via `BTC_RET5M_MIN`)
- Prevents entering longs during BTC downtrends
- Logging: `[EAGER_FILTERS] {sym} REJECT=BTC_GUARD btc_ret5m={x} min={y}`

**Location:** `app_async.py` lines 979-1053

---

### 4. Sizing Clamp Fix (`app_async.py`)

**Changes (lines 1080-1096):**
- Added wallet reserve buffer (`EAGER_WALLET_RESERVE_USD = 3.0`)
- Cap calculation: `cap = max(0.0, free_usdt - reserve)`
- Size clamping: `size_usd = min(size_usd, cap)`
- Applied BEFORE `LIVE_TEST_MODE` cap for proper precedence
- Added affordability check after clamps
- Prevents $350 order attempts on $170 balance

**Logging:**
- `[EAGER] {sym} size capped by reserve: ${old} → ${new} (reserve=${r}, free=${f})`
- `[EAGER] {sym} skipped: unaffordable after clamp (need≥${x}, capped=${y})`

**Location:** `app_async.py` lines 1080-1096

---

### 5. Threshold Logging (`app_async.py`)

**Changes (lines 942-948):**
- Added `[EAGER_THRESHOLDS]` logging once per scan cycle
- Logs effective thresholds: ret5m, vspike, score, depth
- Helps diagnose if settings are being applied correctly

**Format:**
```
[EAGER_THRESHOLDS] ret5m≥0.0180 vsp≥2.00 score≥6 depth≥$8000
```

**Location:** `app_async.py` lines 942-948

---

### 6. Deployment Script Created

**File:** `deploy_entry_quality.sh`

**Capabilities:**
- Stops service, pulls latest code from branch
- Applies all new default settings via overrides_cli.py
- Configures AutoTune controls (disable flow, enable winrate, 60min dwell)
- Enables all 4 entry quality filters
- Sets quality-first thresholds (1.8% momentum, 2x volume, $8000 depth)
- Configures universe exclusions (stables + memes)
- Starts service and monitors logs for 30 seconds

**Usage:**
```bash
cd /home/user/alpha-sniper-v4.2
sudo bash deploy_entry_quality.sh
```

**Location:** `deploy_entry_quality.sh`

---

## 📊 Expected Improvements

### Before (Baseline):
- **Win Rate:** 14.39% (2,119 trades)
- **Trades/Day:** ~40-60 trades
- **Issue:** AutoTune oscillation every 2 hours
- **Issue:** $350 order attempts on $170 balance
- **Issue:** Low quality entries (stables, memes, false breakouts)

### After (Target):
- **Win Rate:** 30-40%+ (quality over quantity)
- **Trades/Day:** 10-20 trades (fewer but higher conviction)
- **Fix:** No more AutoTune oscillation (flow-based disabled)
- **Fix:** Proper sizing with reserve buffer (no oversize orders)
- **Fix:** 4 entry quality filters reject low-probability setups

---

## 🚀 Deployment Instructions

### Pre-Deployment Checklist:
- ✅ All code changes committed to branch `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
- ✅ Deployment script created and tested locally
- ✅ Backup of current settings/database recommended

### Step 1: Deploy to Production
```bash
# On production server
cd /opt/alpha-sniper/alpha-sniper
sudo bash /home/user/alpha-sniper-v4.2/deploy_entry_quality.sh
```

### Step 2: Monitor Initial Behavior (30-60 minutes)
```bash
# Watch for threshold logging
sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_THRESHOLDS

# Watch for filter rejections
sudo journalctl -u alpha-sniper-async.service -f | grep EAGER_FILTERS

# Watch for AutoTune behavior
sudo journalctl -u alpha-sniper-async.service -f | grep -E 'AUTOTUNE|WINRATE'

# Watch for sizing clamps
sudo journalctl -u alpha-sniper-async.service -f | grep 'capped by reserve'
```

### Step 3: Validate Expected Behavior

**✅ Success Indicators:**
- [ ] No more `AUTOTUNE_PRO` loosening logs
- [ ] `[EAGER_THRESHOLDS]` shows ret5m≥0.0180, vsp≥2.00
- [ ] `[EAGER_FILTERS]` rejection logs appearing (EMA_TREND, ACCEL, WICK, BTC_GUARD)
- [ ] No oversize order attempts (sizing properly capped)
- [ ] Trades decreasing to 10-20/day range
- [ ] Win rate improving over 4-8 hours

**⚠️ Rollback If:**
- No trades after 2 hours (filters too strict)
- Service crashes or errors
- Unexpected behavior

### Step 4: Long-Term Monitoring (24-48 hours)

**Metrics to Track:**
- Win rate trend (target: 30-40%+)
- Trade frequency (target: 10-20/day)
- Average hold time for winners vs losers
- P&L trend (should improve if filters working)

---

## 📝 Files Modified

1. `/home/user/alpha-sniper-v4.2/alpha-sniper/config/settings.py` - New parameters
2. `/home/user/alpha-sniper-v4.2/alpha-sniper/core/autotune.py` - Flow gating + dwell time
3. `/home/user/alpha-sniper-v4.2/app_async.py` - Entry filters, sizing clamp, logging
4. `/home/user/alpha-sniper-v4.2/deploy_entry_quality.sh` - Deployment script (new)
5. `/home/user/alpha-sniper-v4.2/ENTRY_QUALITY_IMPLEMENTATION.md` - This document

---

## 🔧 Troubleshooting

### Issue: No trades after deployment
**Solution:** Check logs for `[EAGER_FILTERS]` rejections. If filters too strict, disable one at a time:
```bash
python scripts/overrides_cli.py set --key ENTRY_TREND_EMA_CHECK_ENABLE --value false
```

### Issue: Still seeing oscillation
**Solution:** Verify `AUTOTUNE_FLOW_ENABLE` is false:
```bash
python scripts/overrides_cli.py get --key AUTOTUNE_FLOW_ENABLE
# Should return: false
```

### Issue: Still seeing oversize orders
**Solution:** Verify reserve buffer is set:
```bash
python scripts/overrides_cli.py get --key EAGER_WALLET_RESERVE_USD
# Should return: 3.0
```

---

## 📈 Next Steps After Deployment

1. **Monitor for 24 hours** - Watch win rate trend
2. **Analyze rejection reasons** - Which filters are most active?
3. **Fine-tune thresholds** - If too strict/loose, adjust incrementally
4. **Document results** - Compare before/after metrics

---

**Implementation Date:** 2026-01-14
**Branch:** `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Status:** ✅ READY FOR DEPLOYMENT
