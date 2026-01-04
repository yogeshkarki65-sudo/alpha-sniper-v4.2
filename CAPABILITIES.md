# Alpha Sniper V4.2 - Current Capabilities

**Last Updated**: 2026-01-04

## Executive Summary

**Status**: Bot is FULLY FUNCTIONAL but generating 0 trades due to **static thresholds being too strict for current market conditions**. No auto-tuning mechanism exists to adapt thresholds automatically.

---

## ✅ Core Features (WORKING)

### 1. Exchange Integration
- ✅ MEXC async API integration via ccxt
- ✅ Real-time ticker data fetching
- ✅ OHLCV data retrieval with configurable timeframes
- ✅ Order placement (market orders with IOC flag)
- ✅ Order book depth checking
- ✅ Testnet support for safe testing

### 2. Trading Modes
- ✅ **SIM Mode**: Paper trading with simulated fills
- ✅ **LIVE Mode**: Real trading with actual capital
- ✅ **LIVE_TEST_MODE**: Real orders with small test sizes

### 3. Signal Engines
- ✅ **Pump Engine**: Early pump detection (5-min momentum + volume spike)
  - Detects rapid price increases (1.5%+ in 5 minutes)
  - Identifies volume spikes (1.5x+ vs 20-bar average)
  - Checks price acceleration (current > previous candle)
  - Composite scoring system (score threshold: 15+)

- ✅ **Long Engine**: Multi-timeframe trend following
- ✅ **Short Engine**: Bearish trend detection
- ✅ **Bear Micro Engine**: Micro-scalping in bear markets

### 4. Risk Management
- ✅ **Regime-Based Position Sizing**:
  - BULL: 5% per trade, max 20% total
  - SIDEWAYS: 3% per trade, max 12% total
  - MILD_BEAR: 2% per trade, max 6% total
  - DEEP_BEAR: 1% per trade, max 3% total

- ✅ **Circuit Breakers**:
  - Max 3% daily drawdown limit
  - Max 5 losing trades in a row
  - Emergency cooldown after circuit breaker trips

- ✅ **Position Limits**:
  - Max concurrent positions (default: 4)
  - Per-symbol position limits
  - Total portfolio exposure caps

### 5. Hold Brain (Position Management)
- ✅ **Promote/Demote Logic**: Scales positions up/down based on performance
- ✅ **Trailing Stop**: Dynamic stop-loss that follows price
- ✅ **Take Profit Targets**: Configurable TP levels by regime
- ✅ **Time-Based Exits**: Maximum hold time limits

### 6. Safety Features
- ✅ **Wick Filter**: Blocks entries on abnormal volatility spikes (ATR-based)
- ✅ **Depth Floor**: Ensures minimum liquidity before entry ($15k default)
- ✅ **Cooldown Period**: Prevents re-entry too quickly after exit (5 min default)
- ✅ **IOC Tracking**: Monitors immediately-or-cancel order fill rates

---

## ✅ Phase 1.1 Features (WORKING)

1. ✅ **Per-Symbol Cooldown**: 5-minute cooldown after closing position
2. ✅ **Wick Filter**: ATR-based volatility filter (1.5x multiplier)
3. ✅ **Depth Floor**: Minimum order book depth check ($15k USD)
4. ✅ **Daily Digest**: 24-hour performance summary via Telegram
5. ✅ **IOC Fill Tracking**: Monitors market order fill quality

---

## ✅ Phase 1.2 Features (WORKING)

1. ✅ **60-Second Scan Interval**: Fast scanning for pump detection (down from 5 min)
2. ✅ **Universe Quality Filters**:
   - Exclude stablecoins/pegged pairs: USDC, FDUSD, DAI, TUSD, USDD, EUR, PAXG, WBTC, BTCB
   - Regex pattern exclusions (e.g., `^USDC/USDT$`)
   - Top 100 by 24h quote volume (min $100k volume)

3. ✅ **Diagnostic Tools**:
   - `scripts/diagnostics.py`: Full system health check
   - `scripts/why_no_trade.py`: Analyzes filter failures
   - `scripts/print_settings.py`: Configuration dump

4. ✅ **Scanner Enhancements**:
   - Concurrent OHLCV fetching (default: 5 concurrent requests)
   - Pandas-based technical indicators
   - Signature-safe parameter handling

---

## ❌ Missing Features (NOT IMPLEMENTED)

### 1. Auto-Tuner / Self-Learning Mechanism
**Status**: ❌ **DOES NOT EXIST**

**What You Expected**:
- Automatic threshold adjustment based on signal flow
- Lower thresholds when 0 signals generated for extended period
- Raise thresholds when too many signals trigger
- Self-optimizing parameters based on market conditions

**Current Reality**:
- All thresholds are **STATIC** (read from `.env` at startup)
- No runtime adjustment mechanism exists
- Bot will sit idle forever if market doesn't meet static thresholds
- Requires manual `.env` editing and service restart to change thresholds

**Why This Matters**:
- Your bot has been running 2 days with 0 trades because:
  - MIN_SCORE threshold = 15, but current market best score = 0-1
  - EARLY_RET_5M_MIN = 1.5%, but current best return = 1.43%
  - EARLY_VOL_SPIKE_MIN = 1.5x, but current best spike = 0.45x
- Without auto-tuner, these thresholds never adapt to low-volatility periods

---

## 🔍 Current Issue Analysis

### Why 0 Trades After 2 Days?

**Diagnostic Results** (2026-01-04):
```
Symbols scanned: 100
Signals generated: 0

Filter Failures:
  score_low:      100 (100.0%)  ← All symbols score < 15 (threshold)
  ret5m_low:       99 (99.0%)   ← Best return: 1.43% (need 1.5%)
  volspike_low:    90 (90.0%)   ← Best spike: 0.45x (need 1.5x)
  no_accel:        60 (60.0%)   ← 60 symbols not accelerating
```

**Root Cause**: Static thresholds are too strict for current low-volatility market conditions.

**Current Thresholds** (`.env`):
```env
ALPHA_MIN_SCORE=15                # Too high for current market (best: 0-1)
ALPHA_EARLY_RET_5M_MIN=0.015      # 1.5% (market best: 1.43%)
ALPHA_EARLY_VOL_SPIKE_MIN=1.5     # 1.5x (market best: 0.45x)
ALPHA_EARLY_ACCEL_REQUIRED=true   # Strict acceleration requirement
```

**What's Happening**:
1. Bot scans 100 symbols every 60 seconds ✅
2. Applies universe exclusions (stables/pegs filtered) ✅
3. Fetches OHLCV data and calculates indicators ✅
4. Evaluates each symbol against pump thresholds ✅
5. **ALL symbols fail thresholds** ❌
6. 0 signals generated → 0 trades placed ❌

---

## 🚨 Immediate Options

### Option A: Emergency Manual Fix (Quick)
Lower thresholds manually to match current market volatility:

```bash
# Edit production .env
sudo nano /opt/alpha-sniper/.env

# Change these lines:
ALPHA_MIN_SCORE=5                    # Down from 15
ALPHA_EARLY_RET_5M_MIN=0.010         # Down from 0.015 (1.0% vs 1.5%)
ALPHA_EARLY_VOL_SPIKE_MIN=1.2        # Down from 1.5
ALPHA_EARLY_ACCEL_REQUIRED=false     # Disable strict acceleration check

# Restart bot
sudo systemctl restart alpha-sniper-async.service

# Monitor for signals
journalctl -u alpha-sniper-async.service -f | grep -E "EARLY signal|Opened"
```

**Pros**: Immediate fix, will start generating signals
**Cons**: Still requires manual intervention, thresholds might be too loose

---

### Option B: Build Auto-Tuner System (Robust)

Implement adaptive threshold adjustment system:

**Features**:
1. **Signal Flow Monitoring**:
   - Track signals generated per hour
   - Target: 1-3 signals per hour (configurable)

2. **Automatic Threshold Adjustment**:
   - If 0 signals for 6+ hours → lower thresholds by 10%
   - If 10+ signals per hour → raise thresholds by 10%
   - Min/max bounds to prevent runaway adjustment

3. **Runtime Settings Proxy**:
   - Wraps Pydantic Settings with mutable overlay
   - Allows threshold changes without restart
   - Persists adjustments to disk for restart safety

4. **Telegram Admin Commands**:
   - `/thresholds` - View current values
   - `/tune auto` - Enable auto-tuner
   - `/tune manual MIN_SCORE=10` - Manual override
   - `/tune reset` - Restore defaults

**Implementation Time**: ~2-3 hours
**Pros**: Self-optimizing, handles all market conditions
**Cons**: More complex, needs testing

---

## 📊 Feature Comparison

| Feature | Status | Notes |
|---------|--------|-------|
| Early pump detection | ✅ Working | 5-min momentum + volume spike |
| Universe selection | ✅ Working | Top 100, excludes stables/pegs |
| 60s scan cadence | ✅ Working | Fast scanning enabled |
| Risk management | ✅ Working | Regime-based sizing, circuit breakers |
| Position management | ✅ Working | Promote/demote, trailing stop |
| Safety filters | ✅ Working | Wick filter, depth floor, cooldown |
| Telegram alerts | ✅ Working | Digest, trade notifications |
| Diagnostic tools | ✅ Working | Health check, why-no-trade analysis |
| **Auto-tuner** | ❌ **Missing** | **Never implemented** |
| **Adaptive thresholds** | ❌ **Missing** | **All static from .env** |

---

## 🎯 Recommended Next Step

**For Immediate Trading**:
- Use **Option A** (manual threshold adjustment) to start generating signals TODAY
- Monitor for 24 hours to validate signal quality

**For Long-Term Reliability**:
- Implement **Option B** (auto-tuner system) to handle all market conditions
- Enables hands-off operation without manual tuning

---

## 📝 System Configuration

**Production Deployment**:
- Location: `/opt/alpha-sniper/`
- Service: `alpha-sniper-async.service`
- Logs: `journalctl -u alpha-sniper-async.service`
- Config: `/opt/alpha-sniper/.env`

**Current Settings**:
- Exchange: MEXC (live)
- Mode: LIVE (real capital)
- Scan interval: 60s
- Universe size: 100 symbols
- Regime: AUTO (currently: BULL)

**Diagnostic Commands**:
```bash
# Check bot status
sudo systemctl status alpha-sniper-async.service

# Run health check
python /opt/alpha-sniper/alpha-sniper/scripts/diagnostics.py

# Analyze filter failures
python /opt/alpha-sniper/alpha-sniper/scripts/why_no_trade.py

# View recent trades
sqlite3 /opt/alpha-sniper/alpha_sniper.db "SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;"
```

---

## ⚠️ Key Takeaway

**The bot is fully functional - it's doing exactly what it was designed to do**:
1. ✅ Scanning market every 60 seconds
2. ✅ Filtering for high-quality pump candidates
3. ✅ Correctly rejecting symbols that don't meet strict thresholds

**The problem**: Static thresholds don't adapt to low-volatility market conditions. You need either:
- **Quick fix**: Lower thresholds manually
- **Robust fix**: Build auto-tuner to adapt automatically

**Bottom line**: You're not getting trades because the market isn't volatile enough to trigger your current thresholds, and there's no self-learning mechanism to lower them automatically.
