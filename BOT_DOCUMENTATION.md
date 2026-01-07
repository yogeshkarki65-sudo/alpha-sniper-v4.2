# Alpha Sniper v4.2 - Complete Bot Documentation

**Date**: 2026-01-06
**Branch**: `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Account Balance**: $172.53 USDT
**Status**: ✅ Fully Deployed and Trading

---

## Table of Contents

1. [System Overview](#system-overview)
2. [How the Bot Works](#how-the-bot-works)
3. [AutoTune Pro System](#autotune-pro-system)
4. [EAGER Breakout Feature](#eager-breakout-feature)
5. [Position Sizing & Risk Management](#position-sizing--risk-management)
6. [Current Configuration](#current-configuration)
7. [Implementation History](#implementation-history)
8. [Monitoring & Troubleshooting](#monitoring--troubleshooting)
9. [File Structure](#file-structure)

---

## System Overview

Alpha Sniper v4.2 is an **autonomous cryptocurrency trading bot** that:
- Scans 250 symbols on Binance/MEXC every 60 seconds
- Detects pump signals using volume spikes + price momentum
- Places automated long trades with tight risk management
- Adapts thresholds dynamically using AutoTune Pro
- Uses EAGER breakout feature for consolidation patterns

### Core Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Main Loop (60s)                      │
├─────────────────────────────────────────────────────────┤
│ 1. Scan 250 symbols (OHLCV 1-minute data)              │
│ 2. Calculate features (ret5m, vspike, accel, wick)      │
│ 3. Generate pump signals (standard logic)               │
│ 4. Generate EAGER signals (breakout logic)              │
│ 5. AutoTune Pro adjusts thresholds                      │
│ 6. Place orders via exchange API                        │
│ 7. Manage positions (SL/TP, breakeven, hold brain)     │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Language**: Python 3.12.3
- **Exchange Library**: CCXT 4.5.29
- **Exchange**: MEXC (primary), Binance (supported)
- **Async Framework**: asyncio
- **Settings**: Pydantic v2 (with RuntimeSettings overlay)
- **Database**: SQLite with WAL mode
- **Service**: systemd (`alpha-sniper-async.service`)

---

## How the Bot Works

### 1. Market Scanning

Every 60 seconds, the bot:

```python
# Fetch OHLCV data for all symbols
market_data = await scan_symbols(
    symbols=symbols,        # 250 symbols from universe
    timeframe='1m',         # 1-minute candles
    exchange=exchange,      # MEXC
    concurrency=5,          # Max 5 parallel requests
    limit=500               # 500 candles per symbol
)
```

**Output**: Dictionary of symbol → OHLCV DataFrame + raw OHLCV array

### 2. Feature Calculation

From raw OHLCV data `[timestamp, open, high, low, close, volume]`:

```python
# 5-minute return (momentum)
ret5m = (close[-1] / close[-5]) - 1.0

# Volume spike (vs 20-candle average)
vspike = volume[-1] / mean(volume[-20:])

# Acceleration (rising price)
accel = close[-1] > close[-2]

# Wick filter (ATR-based rejection)
atr14 = mean([max(H-L, |H-C_prev|, |L-C_prev|) for last 14 candles])
body_top = max(open[-1], close[-1])
wick_flag = (high[-1] - body_top) >= 2.0 * atr14

# Composite score
score = (ret5m * 100) + max((vspike - 1) * 10, 0)
```

### 3. Standard Pump Signal Generation

**Criteria** (from `pump_engine.py`):

```python
signal = (
    ret5m >= EARLY_RET_5M_MIN           # e.g., >= 0.8%
    and vspike >= EARLY_VOL_SPIKE_MIN   # e.g., >= 1.1x
    and score >= MIN_SCORE              # e.g., >= 3
    and (accel or not EARLY_ACCEL_REQUIRED)
    and not wick_flag
)
```

**Current Thresholds** (after AutoTune):
- `EARLY_RET_5M_MIN`: 0.008 (0.8%)
- `EARLY_VOL_SPIKE_MIN`: 1.1
- `MIN_SCORE`: 3
- `EARLY_ACCEL_REQUIRED`: False (toggled by AutoTune)

### 4. EAGER Breakout Signal Generation

**Arming Conditions**:

```python
eager_armed = (
    vspike >= 3.0                      # High volume
    and ret5m >= -0.003                # Flat/slightly negative OK
    and not wick_flag                  # No large upper wick
)
```

**Firing Logic** (breakout confirmation):

```python
# Calculate lookback high (last 5 highs)
lookback_high = max(highs[-6:-1])

# Trigger = lookback_high + epsilon
trigger = lookback_high * 1.0008  # +0.08%

# Fire if current price >= trigger
if close[-1] >= trigger:
    place_eager_trade()
```

### 5. Order Execution

**Standard Pump Orders**:
- Order type: Market or Limit
- Stop loss: ~2-3% (dynamic based on ATR)
- Take profit: 2R, 4R levels
- Max hold: 8 hours (hold brain can extend/reduce)

**EAGER Orders**:
- Order type: **Limit IOC** (immediate-or-cancel)
- Entry: Breakout trigger price
- Stop loss: **0.8%** (tight)
- Take profit: **1.5%** (tight)
- Max hold: Uses HOLD_BRAIN_MAX_HOLD_HOURS

### 6. Position Management

```python
# Breakeven Logic
if unrealized_pnl >= 1.0R:
    move_stop_to_breakeven()

# Partial TP
if price >= tp_2r:
    close_50_percent()

if price >= tp_4r:
    close_remaining()

# Hold Brain
if price_flat_for_2_minutes and pnl < 1.5R:
    demote_position()  # Exit early

if momentum_strong and pnl >= 2.5R:
    promote_position()  # Extend deadline
```

---

## AutoTune Pro System

AutoTune Pro is a **3-tier adaptive threshold system** that maintains consistent signal flow.

### Tier 1: Threshold Tuning

**Trigger**: When signals/hour deviates from target (3-5/hour)

**Adjusts**:
- `EARLY_RET_5M_MIN`: 0.008 ↔ 0.035 (0.8% to 3.5%)
- `EARLY_VOL_SPIKE_MIN`: 1.1 ↔ 4.0
- `MIN_SCORE`: 3 ↔ 40

**Logic**:

```python
signals_per_hour = sum(scan_window) / (scans * scan_interval) * 3600

if signals_per_hour < TARGET_LOW:
    # Loosen thresholds by 10%
    EARLY_RET_5M_MIN *= 0.9
    EARLY_VOL_SPIKE_MIN *= 0.9
    MIN_SCORE = max(3, MIN_SCORE - 1)

elif signals_per_hour > TARGET_HIGH:
    # Tighten thresholds by 10%
    EARLY_RET_5M_MIN *= 1.1
    EARLY_VOL_SPIKE_MIN *= 1.1
    MIN_SCORE = min(40, MIN_SCORE + 1)
```

**Cooldown**: 40 scans between adjustments

### Tier 2: Flow Loosening

**Trigger**: 30 consecutive scans with 0 signals

**Adjusts**:
- `UNIVERSE_SIZE`: 100 → 250 (expand symbol universe)
- `UNIVERSE_MIN_QUOTE_VOLUME`: 100k → 25k (allow lower volume coins)
- `MIN_DEPTH_USD_ABSOLUTE`: 15k → 8k (allow thinner orderbooks)

**Purpose**: Cast wider net in dead markets

### Tier 3: Second Notch (Extreme Quiet)

**Trigger**: At max loosening + floor thresholds for extended period

**Adjusts**:
1. **Toggle `EARLY_ACCEL_REQUIRED` to False**
   - Removes acceleration filter (biggest blocker in sideways markets)
   - Allows flat/declining coins with volume spikes

2. **Relax `MIN_DEPTH_MULTIPLE`**: 200 → 120
   - Accepts thinner orderbooks

**Auto-Restore**: When signal flow returns (≥2 signals for 10 consecutive scans)

### Current AutoTune State

```json
{
  "EARLY_ACCEL_REQUIRED": false,        // Toggled by second notch
  "EARLY_RET_5M_MIN": 0.008,           // At floor
  "EARLY_VOL_SPIKE_MIN": 1.1,          // At floor
  "MIN_SCORE": 3,                      // At floor
  "UNIVERSE_SIZE": 250,                // At maximum
  "UNIVERSE_MIN_QUOTE_VOLUME": 25000,  // At floor
  "MIN_DEPTH_USD_ABSOLUTE": 8000,      // At floor
  "MIN_DEPTH_MULTIPLE": 120            // Relaxed
}
```

**Interpretation**: Bot has been in extremely quiet market for 2+ days, all adaptive mechanisms engaged.

---

## EAGER Breakout Feature

### Problem Statement

Standard pump logic requires:
- **Positive momentum** (ret5m > 0.8%)
- **Acceleration** (price rising)

This misses a critical pattern:
- **High volume spike** (3x+) on **flat/slightly negative price**
- Often precedes explosive breakout within minutes (accumulation → breakout)

### Solution: EAGER Entry Path

A second, independent entry mechanism that:

1. **Arms** when high volume appears on consolidation
2. **Fires** only on confirmed breakout of recent range
3. Uses **tight risk** (0.8% SL, 1.5% TP)
4. **Coexists** with standard pump signals

### Configuration

```python
# Settings (alpha-sniper/config/settings.py)
EAGER_ENABLE: bool = True
EAGER_VSPIKE_MIN: float = 3.0              # Need ≥3x volume
EAGER_MAX_NEG_RET5M: float = -0.003        # Allow -0.3% momentum
EAGER_LOOKBACK_HIGH_N: int = 5             # Breakout of last 5 highs
EAGER_EPS_PCT: float = 0.0008              # +0.08% above high
EAGER_SL_PCT: float = 0.008                # 0.8% stop
EAGER_TP_PCT: float = 0.015                # 1.5% target
EAGER_MAX_PER_SCAN: int = 1                # Max 1 per scan
EAGER_REQUIRE_ACCEL: bool = False          # Accel not required
EAGER_ONLY_LIVE_TEST: bool = True          # Safety gate
```

### Execution Flow

```python
# 1. Filter candidates
for symbol in sorted_symbols:
    if vspike < 3.0:
        continue
    if ret5m < -0.003:
        continue
    if wick_flag:
        continue

    # 2. Calculate breakout trigger
    lookback_high = max(highs[-6:-1])  # Last 5 highs
    trigger = lookback_high * 1.0008   # +0.08%

    # 3. Check if breakout occurred
    if current_price >= trigger:
        # 4. Calculate position size
        sl_price = entry_px * 0.992    # 0.8% stop
        size_usd = (account_balance * RISK_PCT) / SL_PCT

        # 5. Place limit IOC order
        order = await exchange.create_order_idempotent(
            symbol=symbol,
            side='buy',
            order_type='limit',
            amount=qty,
            price=trigger,
            params={'timeInForce': 'IOC'}
        )

        # 6. Register position with tight SL/TP
        tp = entry_px * 1.015  # 1.5% target
        await risk.add_position_async(position)
        break  # Max 1 per scan
```

### Example Scenario

**Symbol**: POPCAT/USDT at 12:05

**Market Data**:
```
Time    Close   Volume   High
12:00   0.500   100k     0.505
12:01   0.498   120k     0.502
12:02   0.497   150k     0.500
12:03   0.496   200k     0.499
12:04   0.495   350k     0.498  ← vspike = 2.33x
12:05   0.502   450k     0.505  ← vspike = 3.0x ✅
```

**Calculation**:
- ret5m = (0.502 / 0.500) - 1 = +0.4% ✅
- vspike = 450k / 150k = 3.0x ✅
- wick = False ✅
- lookback_high = max([0.505, 0.502, 0.500, 0.499, 0.498]) = 0.505
- trigger = 0.505 * 1.0008 = 0.50540
- current_price = 0.502 < trigger → **WAIT**

**Next Candle** (12:06):
- Close = 0.507 (breakout!)
- 0.507 > 0.50540 → **FIRE EAGER ENTRY**
- Entry: 0.50540 (limit IOC)
- SL: 0.50540 * 0.992 = 0.50136
- TP: 0.50540 * 1.015 = 0.51298

---

## Position Sizing & Risk Management

### Formula

```python
# Base calculation
risk_amount = account_balance * RISK_PER_TRADE
position_size = risk_amount / stop_loss_percentage

# Example (current settings):
account = $172.53
risk_pct = 0.001391 (0.139%)  # Auto-calculated
sl_pct = 0.008 (0.8%)

risk_amount = $172.53 * 0.001391 = $0.24
position_size = $0.24 / 0.008 = $30
```

### Auto-Sizing Logic

The `fix_eager_autosize.sh` script automatically calculates optimal `RISK_PER_TRADE`:

```bash
# Target: $30 position sizes (safe above $1 min, safe below balance)
# Formula: (target_position * SL%) / account_balance

TARGET = $30
SL = 0.008 (0.8%)
BALANCE = $172.53

RISK_PER_TRADE = ($30 * 0.008) / $172.53
               = 0.24 / $172.53
               = 0.001391 (0.139%)
```

### Why $30 Target?

1. ✅ **Above minimum notional**: MEXC requires ≥$1.0
2. ✅ **Below account balance**: $30 << $172.53
3. ✅ **Safe margin for slippage**: 3000% above minimum
4. ✅ **Multiple trades possible**: Can open 5+ positions simultaneously

### Risk Limits

```python
# Hard limits (from settings.py)
SIZING_RISK_MIN: 0.0025 (0.25%)    # Cannot go below
SIZING_RISK_MAX: 0.0100 (1.0%)     # Cannot go above
MAX_POSITIONS: 5                    # Max simultaneous positions
MAX_DAILY_DRAWDOWN_PCT: 0.05       # Stop trading at -5% daily loss
```

### Sizing Autopilot (Currently Disabled)

**Purpose**: Dynamically adjust `RISK_PER_TRADE` based on performance

**Logic**:
```python
if avg_r >= 0.60 and winrate >= 0.52:
    RISK_PER_TRADE += 0.00025  # Increase by 0.025%

if avg_r <= -0.25:
    RISK_PER_TRADE -= 0.00025  # Decrease by 0.025%
```

**Status**: Disabled to prevent drift during initial EAGER deployment

---

## Current Configuration

### Runtime Overrides

**File**: `/opt/alpha-sniper/data/overrides.json`

```json
{
  "EAGER_ENABLE": true,
  "EAGER_ONLY_LIVE_TEST": false,
  "EARLY_ACCEL_REQUIRED": false,
  "EARLY_RET_5M_MIN": 0.008,
  "EARLY_VOL_SPIKE_MIN": 1.1,
  "MIN_DEPTH_MULTIPLE": 120.0,
  "MIN_DEPTH_USD_ABSOLUTE": 8000.0,
  "MIN_SCORE": 3,
  "RISK_PER_TRADE": 0.001391,
  "SIZING_AUTOPILOT_ENABLE": false,
  "UNIVERSE_MIN_QUOTE_VOLUME": 25000.0,
  "UNIVERSE_SIZE": 250
}
```

### Key Settings Explained

| Setting | Value | Meaning |
|---------|-------|---------|
| `EAGER_ENABLE` | true | EAGER breakout feature active |
| `EAGER_ONLY_LIVE_TEST` | false | EAGER will execute real trades |
| `EARLY_ACCEL_REQUIRED` | false | AutoTune toggled off (extreme quiet) |
| `RISK_PER_TRADE` | 0.001391 | 0.139% risk = ~$30 positions |
| `SIZING_AUTOPILOT_ENABLE` | false | Manual control of position sizing |
| `UNIVERSE_SIZE` | 250 | Scanning maximum symbols |

---

## Implementation History

### Phase 1: AutoTune Pro (Pre-EAGER)

**Problem**: 0 trades for 2+ days despite bot running

**Root Cause**: Thresholds already at floor, universe at max, but `EARLY_ACCEL_REQUIRED` still True

**Solution**: Implemented AutoTune Pro "second notch"
- Auto-toggle `EARLY_ACCEL_REQUIRED` when at max+floor
- Startup check to trigger immediately if already maxed
- Auto-restore when signal flow returns

**Commits**:
- `e494d788`: Auto-toggle accel on startup + fix near-miss extraction
- `6550f023`: Comprehensive AutoTune Pro documentation

### Phase 2: EAGER Breakout Implementation

**Problem**: Bot still generating 0-1 trades/day even with AutoTune

**Analysis**: Missing high-volume consolidation → breakout pattern

**Solution**: Implement EAGER breakout entry path

**Commits**:
- `93df7333`: Add EAGER feature (settings + pipeline + depth snapshot)
- `db5e53a8`: Add deployment and verification scripts
- `42d0bc2e`: Add Pydantic Field() definitions for type safety

### Phase 3: Bug Fixes

**Issue 1**: `'float' object cannot be interpreted as an integer`

**Root Causes** (multiple):
1. Time import conflict (line 920, 831)
2. `current_regime` undefined (line 858)
3. EAGER settings using bare type hints instead of Field()
4. Exchange precision values as floats in round()
5. Slice operations with float indices

**Fixes**:
- `038d5288`: Remove redundant time imports
- `dff1acf4`: Fix regime='SIDEWAYS' hardcode
- `42d0bc2e`: Add Field() validation
- `ff04ddb2`: Cast precision to int
- `5628c0b9`: Explicit int() for slice operations

**Issue 2**: Illegal characters in client order ID

**Root Cause**: Symbol name `GOOGLON/USDT` contains `/` which MEXC rejects

**Fix**:
- `f4c8a6a7`: Sanitize symbol name (remove `/` and `-`)

**Issue 3**: Position sizing errors

**Root Causes**:
1. `RISK_PER_TRADE` too low → `notional<1.0` errors
2. `RISK_PER_TRADE` too high → `Insufficient position` errors
3. Balance locked in other positions
4. Sizing autopilot drifting risk percentage

**Fix**:
- `deb3d867`: Auto-sizing script to calculate optimal risk
- `eeb2d7a2`: Increase TARGET_POSITION to $50 for safer margins

### Phase 4: Comprehensive EAGER Hardening (2026-01-07)

**Problem**: After 24+ hours of deployment, EAGER still generating 0 trades

**Root Causes** (critical analysis):
1. **Bad symbols in universe**: MEXC API rejecting stock tokens (NVDAON/USDT), leveraged ETFs (3L/3S, 5L/5S), causing {"code":10007,"msg":"symbol not support api"}
2. **Order spam**: Loop attempted multiple orders per scan when first candidate failed (eager_opened only incremented on success), causing "Insufficient position" from cumulative notional
3. **False notional rejections**: Min-notional validation used hardcoded $1.0 instead of exchange-specific `limits.cost.min`
4. **No cooldown**: Same failing symbol retried every 60 seconds
5. **No depth/balance guards**: Thin orderbooks and low balances not checked before order attempts

**Solutions Implemented**:

#### 1. Exchange Validation Hardening (`exchange_async.py`)

**Changes**:
- Added `markets` property to expose cached markets dict
- Added `fetch_balance_cached()` with 10-second TTL to reduce API calls
- Completely rewrote `validate_order()` with:
  - Market type validation (reject inactive, non-spot, wrong type)
  - Regex filters for bad symbols:
    - `.*ON/USDT$` (stock tokens: NVDAON, QCOMON, AMDON, etc.)
    - `.*3L/USDT$`, `.*3S/USDT$`, `.*5L/USDT$`, `.*5S/USDT$` (leveraged ETFs)
    - `.*UP/USDT$`, `.*DOWN/USDT$` (directional tokens)
  - Correct notional calculation: `px * qty` in quote terms
  - Exchange-specific min cost from `limits.cost.min` (fallback $1.0)
  - Floor-based precision rounding: `floor(x * 10^prec) / 10^prec`
  - Balance check: notional ≤ 98% of free quote balance
  - Returns validated `px` and `qty` in details dict for caller to use

**Example rejection log**:
```
[EAGER] NVDAON/USDT rejected by validate_order: unsupported_symbol_pattern
```

#### 2. Universe Filtering (`universe/select.py`)

**Changes**:
- Added `_is_tradable_symbol()` function with same filters as validation
- Applied filtering before ticker processing in `select_top_liquid_symbols()`
- Logs count of filtered symbols: `"Universe tradability filter: removed N non-tradable symbols"`

**Impact**: Stock tokens, leveraged ETFs never enter universe, eliminating 10007 errors at source

#### 3. EAGER Loop Hardening (`app_async.py`)

**Changes**:
- Added module-level tracking:
  ```python
  EAGER_LAST_ATTEMPT = {}  # sym -> timestamp
  EAGER_BACKOFF_SEC = 90   # Configurable via settings
  ```
- **Balance check once before loop**: Fetch cached balance, skip EAGER if `free_usdt < MIN_VIABLE_TRADE_USD * 2`
- **Per-symbol cooldown**: Skip if `now - last_attempt < EAGER_BACKOFF_SEC` (default 90 sec)
- **Depth guard**: Skip if `depth_usd < MIN_DEPTH_USD_ABSOLUTE` (default $5000)
- **Single attempt per scan**: `eager_attempted` flag, break after first attempt (success OR failure)
- **Use validated px/qty**: Take `det["px"]` and `det["qty"]` from `validate_order()` and pass to `create_order_idempotent()`
- **Update cooldown after attempt**: `EAGER_LAST_ATTEMPT[sym] = now` even if order fails
- **Telemetry summary**: Log `[EAGER_SUMMARY] candidates=X attempted=Y opened=Z free_usdt=W` after each scan

**Before** (problematic):
```python
for row in _rows:
    if eager_opened >= eager_max_per_scan:  # Only checks successes
        break
    # ... multiple attempts per scan possible
    qty = size_usd / entry_px  # Unvalidated qty
```

**After** (fixed):
```python
for row in _rows:
    if eager_attempted > 0:  # Stop after ANY attempt
        break
    # Cooldown check
    if now - EAGER_LAST_ATTEMPT.get(sym, 0) < backoff_sec:
        continue
    # Depth check
    if depth_usd < MIN_DEPTH_USD_ABSOLUTE:
        continue
    # ... validate and get rounded values
    validated_px = det["px"]
    validated_qty = det["qty"]
    eager_attempted = 1
    EAGER_LAST_ATTEMPT[sym] = now
    # ... create order with validated values
```

#### 4. Settings Update (`settings.py`)

**Changes**:
- Added `EAGER_BACKOFF_SEC: int = Field(default=90, ge=30, le=300, description="Per-symbol cooldown between EAGER attempts (sec)")`

**Purpose**: Prevents rapid-fire retries of failing symbols, reduces exchange rate limit pressure

#### 5. Position Sizing Improvement (`fix_eager_autosize.sh`)

**Changes**:
- Increased `TARGET_POSITION` from $30 to $50
- New calculation: `OPTIMAL_RISK = ($50 * 0.008) / $172 = 0.00232 (0.232%)`
- Result: Position size = $50 (safely above all exchange minimums)

**Why $50 vs $30**:
- Many low-priced symbols (PEPE, LUNC, MOG) need larger qty to reach $1+ notional
- $50 provides comfortable margin above exchange minimums
- Still safely below account balance ($172)

**Expected Behavior After Fixes**:

1. **Universe selection**: No stock tokens, leveraged ETFs, or inactive markets
2. **Validation**: All symbols pre-checked, correct notional calculation
3. **Order attempts**: Maximum 1 per minute, cooldown prevents spam
4. **Logs**: Clean rejections with specific reasons instead of exchange errors
5. **Success rate**: Should see first EAGER fills within 2-3 hours of high-volume consolidations

**Monitoring Commands**:
```bash
# Watch for clean behavior
sudo journalctl -u alpha-sniper-async.service -f | grep -E "EAGER|EAGER_SUMMARY"

# Should see:
# [EAGER_SUMMARY] candidates=5 attempted=1 opened=0 free_usdt=172.53
# [EAGER] PEPE/USDT rejected by validate_order: notional<min_cost
# (At most ONE attempt per minute, no "symbol not support api" errors)

# When conditions align:
# [EAGER] OPENED CHZ/USDT @ 0.12345 size=$50.00 tp=0.12530 sl=0.12247
```

**Commits**:
- `[current]`: Exchange validation hardening + universe filtering + EAGER cooldown + settings

---

## Monitoring & Troubleshooting

### Monitor EAGER Trades

```bash
# Watch for EAGER trades
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered "EAGER.*OPENED"

# Watch near-miss candidates (top 3 per scan)
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered "EARLY_TOP"

# Watch all trades (standard + EAGER)
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered "OPENED\|CLOSED"
```

### Expected Log Output

**Near-miss logs** (every 60 seconds when no signals):
```json
{"time": "2026-01-06 13:00:15", "level": "INFO",
 "message": "[EARLY_TOP] POPCAT/USDT ret5m=-0.12% vspike=3.5 score=28.5 accel=False wick=False depth=$15000"}
```

**EAGER trade**:
```json
{"time": "2026-01-06 13:01:23", "level": "INFO",
 "message": "[EAGER] OPENED POPCAT/USDT @ 0.50540 size=$30.00 tp=0.51298 sl=0.50136"}
```

**Standard pump trade**:
```json
{"time": "2026-01-06 13:05:45", "level": "INFO",
 "message": "🎯 HYPE/USDT | score=45 | entry=$1.23456"}
```

### Quick Verification

```bash
cd /opt/alpha-sniper

# Run quick verification script
bash quick_verify.sh

# Should show:
# ✓ Service running
# ✓ EAGER code present
# ✓ Near-miss logs found
# ✓ EAGER activity found
```

### Common Issues

#### 1. No EAGER Trades

**Check**:
```bash
# View recent candidates
sudo journalctl -u alpha-sniper-async.service -n 100 | grep EARLY_TOP
```

**If seeing high vspike (≥3.0) but no trades**:
- Check `EAGER_ONLY_LIVE_TEST` (should be False)
- Check position size errors in logs
- Verify breakout not occurring (price < trigger)

#### 2. Position Size Errors

**`notional<1.0`**: Position too small
```bash
# Increase risk
cd /opt/alpha-sniper
bash fix_eager_autosize.sh  # Auto-calculates optimal
```

**`Insufficient position`**: Position too large
```bash
# Check free balance
sudo journalctl -u alpha-sniper-async.service --since "1 minute ago" | grep equity
```

#### 3. Service Not Running

```bash
# Check status
sudo systemctl status alpha-sniper-async.service

# View errors
sudo journalctl -u alpha-sniper-async.service -n 50 --no-pager

# Restart
sudo systemctl restart alpha-sniper-async.service
```

### View Current Overrides

```bash
cd /opt/alpha-sniper
source venv/bin/activate

# Show all overrides
python scripts/overrides_cli.py show

# Get specific value
python scripts/overrides_cli.py get --key RISK_PER_TRADE

# Set value
python scripts/overrides_cli.py set --key EAGER_VSPIKE_MIN --value 2.5

# Reset to default
python scripts/overrides_cli.py reset --key EAGER_VSPIKE_MIN

deactivate
```

---

## File Structure

### Core Files

```
/opt/alpha-sniper/
├── app_async.py                      # Main trading loop
│   ├── Lines 770-857: Market scanning + feature extraction
│   ├── Lines 858-876: Standard pump signal generation
│   ├── Lines 877-949: EAGER breakout pipeline
│   └── Lines 950+: Order execution + position management
│
├── alpha-sniper/
│   ├── config/
│   │   ├── settings.py              # All configuration knobs
│   │   │   ├── Lines 151-161: EAGER settings
│   │   │   └── Lines 164-165: Depth snapshot settings
│   │   └── runtime_settings.py      # JSON overlay system
│   │
│   ├── core/
│   │   ├── autotune.py              # AutoTune Pro logic
│   │   │   ├── Lines 71-97: Startup second notch check
│   │   │   ├── Lines 240-310: Threshold tuning
│   │   │   └── Lines 311-370: Flow loosening + second notch
│   │   ├── exchange_async.py        # Exchange API wrapper
│   │   │   └── Lines 380-390: Precision handling (fixed)
│   │   └── risk_manager.py          # Position sizing + limits
│   │
│   ├── signals/
│   │   └── pump_engine.py           # Standard pump detection
│   │
│   └── scanner/
│       └── runner.py                # OHLCV fetching
│           └── Line 91: Store raw OHLCV for EAGER
│
├── data/
│   ├── overrides.json               # Runtime config overrides
│   ├── positions.json               # Active positions state
│   └── equity_snapshots.csv         # Equity history
│
├── scripts/
│   ├── overrides_cli.py             # Manage runtime overrides
│   ├── fix_eager_autosize.sh        # Auto-size position calculator
│   ├── deploy_eager.sh              # Deployment automation
│   ├── quick_verify.sh              # Quick health check
│   └── verify_eager.sh              # Detailed verification
│
└── logs/
    └── bot.log                      # Application logs
```

### Configuration Flow

```
┌─────────────────────┐
│   settings.py       │  Base configuration
│   (defaults)        │  with Pydantic Field()
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  .env file          │  Environment overrides
│  (optional)         │  (LIVE_TEST_MODE, etc.)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  overrides.json     │  Runtime overrides
│  (persistent)       │  (AutoTune + manual)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  RuntimeSettings    │  Final merged config
│  (in memory)        │  used by bot
└─────────────────────┘
```

---

## Summary

### What's Working

✅ **AutoTune Pro v3**
- Threshold tuning (ret5m, vspike, score)
- Flow loosening (universe expansion)
- Second notch (accel toggle + depth relax)
- Automatic startup check
- Auto-restore on signal flow return

✅ **EAGER Breakout Feature**
- High-volume consolidation detection (vspike ≥3.0)
- Breakout confirmation (last 5-candle high +0.08%)
- Tight risk management (0.8% SL, 1.5% TP)
- Limit IOC orders (no lingering)
- Max 1 per scan (hard cap)
- Coexists with standard signals

✅ **Position Sizing**
- Auto-calculated optimal risk (0.139%)
- ~$30 positions (safe above $1 min, safe below balance)
- Sizing autopilot disabled (manual control)
- All circuit breakers active

✅ **Near-Miss Visibility**
- Top 3 candidates logged every scan
- Real-time feature values (ret5m, vspike, depth)
- Helps understand why symbols don't trigger

### Expected Performance

**With AutoTune Pro + EAGER**:
- Standard pump signals: 2-3/hour (momentum trades)
- EAGER signals: 0-1/hour (breakout trades)
- **Total**: ~3-4 trades/hour even in extremely calm markets

**Current Market State**: Extremely quiet (2+ days, 0 trades)
- All AutoTune mechanisms engaged (floor + max + accel off)
- EAGER now active to catch consolidation breakouts
- Should see first trades within hours

### Next Steps

1. **Monitor for trades** (2-3 hours)
2. **Analyze EAGER performance** (win rate, avg R)
3. **Tune if needed** (adjust vspike threshold, epsilon, etc.)
4. **Re-enable sizing autopilot** after stable performance
5. **Consider additional patterns** (mean reversion, range breakout, etc.)

---

## Appendix: Key Metrics

### Account Status
- **Balance**: $172.53 USDT
- **Risk per trade**: 0.139% ($0.24)
- **Position size**: ~$30
- **Max positions**: 5
- **Max exposure**: ~$150 (5 × $30)

### Current Thresholds
- **RET5M**: 0.008 (0.8%) - at floor
- **VSpike**: 1.1 - at floor
- **Score**: 3 - at floor
- **Accel**: Not required - toggled off
- **Universe**: 250 symbols - at maximum
- **Volume floor**: 25k - at minimum

### EAGER Settings
- **Enable**: True
- **VSpike min**: 3.0
- **Max neg ret5m**: -0.003 (-0.3%)
- **Lookback**: 5 candles
- **Epsilon**: 0.08%
- **Stop loss**: 0.8%
- **Take profit**: 1.5%
- **Max per scan**: 1

---

**End of Documentation**

For latest updates, see git log:
```bash
git log --oneline --graph --decorate
```

Last updated: 2026-01-06 13:05 UTC
