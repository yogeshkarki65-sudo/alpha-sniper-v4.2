# Phase 1-3 Deployment Guide

## 🎯 What Was Implemented

### Phase 1: Regime-Specific Configuration
- ✅ Max loss per regime (0.01-0.03)
- ✅ Min score per regime (0.70-0.90)
- ✅ Position size per regime (0.03-0.15)

### Phase 2: Exit Logic Improvements
- ✅ **2A: Trailing Stops** - Let winners run while protecting profits
- ✅ **2B: Partial Take Profits** - Scale out at multiple levels
- ✅ **2C: Position Size Scaling** - Bigger positions on higher scores

### Phase 3: Entry Logic Enhancements
- ✅ **3A: Confirmation Candles** - Require N candles showing volume + price strength
- ✅ **3B: ATR-Based Stops** - Dynamic stops based on volatility

---

## 🚀 DEPLOYMENT STEPS

### Step 1: Deploy to Production Server

```bash
# Pull all changes
cd /opt/alpha-sniper
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
```

### Step 2: Apply Phase 1 Config Changes

```bash
# Run the env optimizer script
sudo ./deployment/apply_phase1_optimizations.sh
```

This will add ALL config parameters for:
- Regime-specific overrides
- Trailing stops
- Partial TPs
- Position scaling
- Confirmation candles
- ATR stops

### Step 3: Review & Adjust Settings (Optional)

```bash
# Edit env file to customize
sudo nano /etc/alpha-sniper/alpha-sniper-live.env
```

**Recommended Starting Configuration:**

```bash
# Enable features
PUMP_TRAILING_ENABLED=true           # Let winners run
PUMP_PARTIAL_TP_ENABLED=true         # Lock in partial profits
POSITION_SCALE_WITH_SCORE=true       # Bigger bets on better signals

# Confirmation candles (DISABLE initially to test)
PUMP_CONFIRMATION_CANDLES=0          # Set to 2 after testing

# ATR stops (DISABLE initially - more complex)
PUMP_USE_ATR_STOPS=false             # Keep false for now

# Regime-specific settings (ENABLED automatically)
PUMP_MAX_LOSS_PCT_SIDEWAYS=0.015     # Tighter in sideways (current regime)
MIN_SCORE_PUMP_SIDEWAYS=0.80         # Stricter quality filter
POSITION_SIZE_PCT_SIDEWAYS=0.07      # Smaller positions
```

### Step 4: Restart Service

```bash
# Restart to apply new config
sudo systemctl restart alpha-sniper-live.service

# Watch logs for 2-3 minutes
sudo journalctl -u alpha-sniper-live.service -f
```

**Look for:**
- ✅ `🛡️ SYNTHETIC STOP WATCHDOG started`
- ✅ `📨 Scan summary sent to Telegram`
- ✅ No errors on startup

### Step 5: Verify Features Are Working

```bash
# Run verification script
sudo ./deployment/verify_all.sh
```

**Expected:**
- Health Score: **90-100%**
- ✅ All critical checks pass
- ✅ Trailing stops initialized
- ✅ Partial TP config loaded

---

## 📊 TESTING PLAN

### Week 1: Core Features Only
**Enable:**
- ✅ Trailing stops (PUMP_TRAILING_ENABLED=true)
- ✅ Partial TPs (PUMP_PARTIAL_TP_ENABLED=true)
- ✅ Position scaling (POSITION_SCALE_WITH_SCORE=true)
- ✅ Regime overrides (automatic)

**Disable:**
- ❌ Confirmation candles (PUMP_CONFIRMATION_CANDLES=0)
- ❌ ATR stops (PUMP_USE_ATR_STOPS=false)

**Monitor:**
- Win rate improvement
- Trades reaching partial TPs
- Position size scaling logs
- Trailing stop triggers

### Week 2: Add Confirmation Candles
**Enable:**
- ✅ Confirmation candles (PUMP_CONFIRMATION_CANDLES=2)

**Monitor:**
- Signal reduction (should filter out ~20-30%)
- Win rate increase
- False signal reduction

### Week 3+: Consider ATR Stops
**Enable (carefully):**
- ✅ ATR stops (PUMP_USE_ATR_STOPS=true)

**Monitor:**
- Stop placement quality
- Drawdown reduction
- R-multiple improvements

---

## 🔍 MONITORING COMMANDS

### Check Trailing Stops
```bash
sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager | grep "WATCHDOG.*Trailing"
```

### Check Partial TPs
```bash
sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager | grep "PARTIAL_TP"
```

### Check Position Scaling
```bash
sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager | grep "ScoreScaling"
```

### Check Confirmation Candles
```bash
sudo journalctl -u alpha-sniper-live.service --since "1 hour ago" --no-pager | grep "CONFIRMATION"
```

### Check Overall Health
```bash
sudo ./deployment/verify_all.sh
```

---

## 🎯 EXPECTED IMPROVEMENTS

### Before Optimizations (Baseline)
- Win Rate: 30%
- 98% hit time limits
- No trades reached targets
- Fixed position sizes
- No trailing protection

### After Phase 1-2 (Week 1)
**Expected:**
- Win Rate: **40-45%**
- Partial TPs captured: **30-40% of trades**
- Trailing stops protecting: **15-20% of trades**
- Position sizes optimized: **High scores get 1.3-1.5x size**
- Drawdowns reduced: **Tighter stops in SIDEWAYS**

### After Phase 3 (Week 2-3)
**Expected:**
- Win Rate: **50-55%**
- False signals reduced: **20-30% fewer bad trades**
- Better stop placement: **ATR adapts to volatility**
- Overall ROI improvement: **2-3x**

---

## ⚠️ ROLLBACK PLAN

If issues occur:

```bash
# 1. Stop service
sudo systemctl stop alpha-sniper-live.service

# 2. Restore backup env file
sudo cp /etc/alpha-sniper/alpha-sniper-live.env.backup.phase1.* /etc/alpha-sniper/alpha-sniper-live.env

# 3. Restart
sudo systemctl start alpha-sniper-live.service
```

---

## 📝 CONFIG REFERENCE

### Trailing Stops
```bash
PUMP_TRAILING_ENABLED=true
PUMP_TRAILING_PCT=0.03              # Trail 3% below peak
PUMP_TRAILING_ACTIVATION_PCT=0.05   # Activate after +5% profit
```

### Partial Take Profits
```bash
PUMP_PARTIAL_TP_ENABLED=true
PUMP_PARTIAL_TP_LEVELS=0.05:0.5,0.10:1.0  # 50% at +5%, rest at +10%
```

### Position Scaling
```bash
POSITION_SCALE_WITH_SCORE=true
POSITION_SCALE_MAX=1.5              # Max 1.5x size for score=1.0
```

### Confirmation Candles
```bash
PUMP_CONFIRMATION_CANDLES=2
PUMP_CONFIRMATION_VOLUME_MULT=3.0   # 3x volume required
PUMP_CONFIRMATION_PRICE_CHANGE_PCT=0.02  # +2% per candle
```

### ATR Stops
```bash
PUMP_USE_ATR_STOPS=false            # Start disabled
PUMP_ATR_PERIOD=14
PUMP_ATR_MULTIPLIER=2.0
```

### Regime Overrides (Auto-Applied)
```bash
# SIDEWAYS (current regime - strictest)
PUMP_MAX_LOSS_PCT_SIDEWAYS=0.015
MIN_SCORE_PUMP_SIDEWAYS=0.80
POSITION_SIZE_PCT_SIDEWAYS=0.07

# STRONG_BULL (most aggressive)
PUMP_MAX_LOSS_PCT_STRONG_BULL=0.03
MIN_SCORE_PUMP_STRONG_BULL=0.70
POSITION_SIZE_PCT_STRONG_BULL=0.15

# MILD_BEAR (conservative)
PUMP_MAX_LOSS_PCT_MILD_BEAR=0.012
MIN_SCORE_PUMP_MILD_BEAR=0.85
POSITION_SIZE_PCT_MILD_BEAR=0.05

# FULL_BEAR (very tight)
PUMP_MAX_LOSS_PCT_FULL_BEAR=0.01
MIN_SCORE_PUMP_FULL_BEAR=0.90
POSITION_SIZE_PCT_FULL_BEAR=0.03
```

---

## 🎉 SUCCESS METRICS

After 1 week, you should see:

1. ✅ Win rate increased (30% → 40%+)
2. ✅ More trades reaching profit targets
3. ✅ Trailing stops protecting winners
4. ✅ Partial TPs reducing drawdowns
5. ✅ Better position sizing on quality signals
6. ✅ Health score consistently 95%+

---

END OF DEPLOYMENT GUIDE
