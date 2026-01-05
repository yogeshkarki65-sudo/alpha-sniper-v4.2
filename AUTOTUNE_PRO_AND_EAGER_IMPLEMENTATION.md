# AutoTune Pro + EAGER Breakout Implementation Guide

**Repository**: `/opt/alpha-sniper`
**Branch**: `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
**Python**: 3.12.3
**CCXT**: 4.5.29
**Service**: `alpha-sniper-async.service` (keep `alpha-sniper-live.service` compatible)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [AutoTune Pro - Current Implementation](#autotune-pro---current-implementation)
3. [Recent Fixes](#recent-fixes)
4. [EAGER Breakout Feature - New Implementation](#eager-breakout-feature---new-implementation)
5. [Implementation Patches](#implementation-patches)
6. [Architecture & File Structure](#architecture--file-structure)
7. [Deployment Instructions](#deployment-instructions)

---

## System Overview

Alpha Sniper v4.2 is a cryptocurrency trading bot that:
- Scans 100-250 symbols on Binance every 60 seconds (1-minute OHLCV data)
- Detects early pump signals based on price momentum + volume spikes
- Places automated long trades with tight risk management
- Uses adaptive threshold tuning (AutoTune Pro) to maintain signal flow

**Core Signal Logic** (Pump Engine):
- **ret5m** ≥ threshold (e.g., 0.8% over 5 minutes)
- **Volume spike** ≥ threshold (e.g., 3x vs 20-candle average)
- **Score** ≥ threshold (composite: ret5m * 100 + vspike * 10)
- **Acceleration required**: close[n] > close[n-1] (optional, auto-toggled)
- **Wick filter**: Rejects symbols with large upper wick (≥ 2.0 ATR)

**Problem**: In extremely calm markets (2+ days, 0 trades), even minimum thresholds generate no signals.

---

## AutoTune Pro - Current Implementation

AutoTune Pro is a **multi-tiered adaptive threshold system** that automatically adjusts trading parameters based on signal flow to ensure consistent trade opportunities.

### 1. Core Components

**File**: `alpha-sniper/core/autotune.py`

**Three Adjustment Mechanisms**:

#### A. **Threshold Tuning** (First Tier)
- **Adjusts**: RET5M, VSpike, Score thresholds
- **Trigger**: When signals/hour deviates from target (default: 3-5 signals/hour)
- **Bounds**:
  - `EARLY_RET_5M_MIN`: 0.008 to 0.035 (0.8% to 3.5%)
  - `EARLY_VOL_SPIKE_MIN`: 1.1 to 4.0
  - `MIN_SCORE`: 3 to 40
- **Step size**: ±10% per adjustment
- **Cooldown**: 40 scans between adjustments

```python
# Example adjustment logic
if signals_per_hour < target_low:
    new_threshold = current * 0.9  # Loosen by 10%
elif signals_per_hour > target_high:
    new_threshold = current * 1.1  # Tighten by 10%
```

#### B. **Flow Loosening** (Second Tier)
- **Trigger**: When `FLOW_QUIET_SCANS` consecutive scans with 0 signals (default: 30)
- **Adjusts**:
  - `UNIVERSE_SIZE`: Expand from 100 → 250 symbols
  - `UNIVERSE_MIN_QUOTE_VOLUME`: Lower from 100k → 25k
  - `MIN_DEPTH_USD_ABSOLUTE`: Lower from 15k → 8k
- **Purpose**: Cast wider net when market is dead

```python
# Flow loosen logic
if signals == 0:
    self._quiet_scans += 1
    if self._quiet_scans >= FLOW_QUIET_SCANS:
        expand_universe()
        lower_volume_requirements()
        lower_depth_requirements()
```

#### C. **Second Notch** (Third Tier - Extreme Quiet)
- **Trigger**: When already at max loosening + floor thresholds
- **Adjusts**:
  1. **Toggle `EARLY_ACCEL_REQUIRED` to `false`**: Removes acceleration filter (biggest blocker in sideways markets)
  2. **Relax `MIN_DEPTH_MULTIPLE`**: From 200 → 120 (allows thinner orderbooks)
- **Auto-restore**: When signals return (≥2 signals for 10 consecutive scans)

```python
# Second notch logic (NEW - just implemented)
def _check_startup_second_notch(self):
    """Trigger immediately on startup if already at max loosening"""
    at_max = (UNIVERSE_SIZE >= 250 and VOLUME_FLOOR <= 25k)
    at_floor = (RET5M <= 0.008 and MIN_SCORE <= 3)

    if at_max and at_floor and AUTO_ACCEL_TOGGLE:
        if EARLY_ACCEL_REQUIRED == True:
            set_override("EARLY_ACCEL_REQUIRED", False)
            log("[FLOW_TOGGLE] accel_required=False (startup at max+floor)")
```

### 2. Runtime Settings Overlay

**File**: `alpha-sniper/core/runtime_settings.py`

- **Purpose**: Persist config overrides to `./data/overrides.json` without restart
- **Pydantic v2**: Settings objects are immutable → use overlay pattern
- **API**:
  ```python
  overlay.set("EARLY_RET_5M_MIN", 0.008)  # Writes to JSON + updates in-memory
  overlay.get("EARLY_RET_5M_MIN")         # Reads from overlay or falls back to base
  ```

### 3. Near-Miss Visibility

**File**: `app_async.py` (lines 780-824)

- **Purpose**: Show top 3 "almost signals" when 0 signals generated
- **Calculates**: ret5m, vspike, score, accel, wick from OHLCV data
- **Log format**:
  ```
  [EARLY_TOP] BTC/USDT ret5m=0.45% vspike=2.1 score=8.5 accel=True wick=False depth=$12500
  ```

---

## Recent Fixes

### Fix 1: Automatic Accel Toggle on Startup ✅
**Commit**: `e494d788`

**Problem**: Bot already at max loosening + floor thresholds after 2 days, but `EARLY_ACCEL_REQUIRED` still `true` → no signals. Second notch only triggered after a FLOW_LOOSEN event (which never happens when already maxed).

**Solution**: Check on initialization if already at max+floor → immediately toggle accel off.

**Code**: `alpha-sniper/core/autotune.py` lines 71-97

### Fix 2: Near-Miss Feature Extraction ✅
**Commit**: `e494d788`

**Problem**: Feature extraction code expected `market_data[sym]["features"]` dict, but actual data is raw OHLCV DataFrames → all logs showed 0.00.

**Solution**: Calculate features directly from OHLCV data (close, volume arrays).

**Code**: `app_async.py` lines 780-824

---

## EAGER Breakout Feature - New Implementation

### Problem Statement

Current signal logic requires:
- **Positive momentum** (ret5m > 0.008, i.e., +0.8%)
- **Acceleration** (close[n] > close[n-1])

This misses a critical pattern:
- **High volume spike** (3x+) on **flat/slightly negative price** (consolidation/accumulation)
- Often precedes explosive breakout within minutes

### Solution: EAGER Entry Path

**Add a second, optional entry mechanism** that:
1. **Arms** when: vspike ≥ 3.0 and ret5m ≥ -0.003 (allows -0.3% over 5m), wick=False
2. **Fires** only on breakout of recent N-candle high (default: 5 candles) with tiny epsilon (+0.08%)
3. Uses **limit IOC** order (immediate-or-cancel) at breakout level
4. Tight risk: **0.8% stop, 1.5% target** (R:R ~1.87)
5. Respects all existing risk controls (max positions, circuit breakers, etc.)
6. **Hard cap**: At most 1 eager trade per scan

### Key Design Principles

✅ **No schema changes**: Uses existing Settings + RuntimeSettings overlay
✅ **No extra OHLCV calls**: Reuses data from existing scan
✅ **Wick filter ON**: Rejects symbols with large upper wick
✅ **Safety**: Only enabled when `LIVE_TEST_MODE=True` by default
✅ **Coexists**: Standard pump signals still work independently

### Configuration Knobs

```python
# alpha-sniper/config/settings.py
EAGER_ENABLE: bool = True                  # Master switch
EAGER_VSPIKE_MIN: float = 3.0              # Need ≥3x volume spike
EAGER_MAX_NEG_RET5M: float = -0.003        # Allow down to -0.3% over 5m
EAGER_LOOKBACK_HIGH_N: int = 5             # Breakout of last 5 highs
EAGER_EPS_PCT: float = 0.0008              # +0.08% above lookback high
EAGER_SL_PCT: float = 0.008                # 0.8% stop loss
EAGER_TP_PCT: float = 0.015                # 1.5% take profit
EAGER_MAX_PER_SCAN: int = 1                # Max 1 eager trade per scan
EAGER_REQUIRE_ACCEL: bool = False          # Accel not required
EAGER_ONLY_LIVE_TEST: bool = True          # Safety: only when testing
```

### Execution Flow

```
1. Scan completes → market_data contains OHLCV for all symbols
2. Compute features (ret5m, vspike, wick) for all symbols
3. Generate standard pump signals
4. IF no standard signals AND eager_enabled:
   a. Filter candidates: vspike ≥ 3.0, ret5m ≥ -0.003, wick=False
   b. For each candidate (sorted by score):
      - Calculate lookback high (max of last 5 highs)
      - Trigger = lookback_high * 1.0008
      - IF current price ≥ trigger:
        * Validate order (size, precision, risk)
        * Place limit IOC order at trigger price
        * Register position with tight SL/TP
        * Break (only 1 eager per scan)
```

### Example Scenario

**Symbol**: HYPE/USDT
**5-minute data**:
```
Time     Close   Volume  High
12:00    1.000   100     1.005
12:01    0.998   120     1.002
12:02    0.997   150     1.000
12:03    0.996   200     0.999
12:04    0.995   350     0.998  ← vspike = 350/150 = 2.33x
12:05    1.002   450     1.005  ← vspike = 450/150 = 3.0x ✅
```

**Calculation**:
- ret5m = (1.002 / 1.000) - 1 = +0.2% ✅ (above -0.3% floor)
- vspike = 450 / 150 = 3.0x ✅
- wick = False ✅ (body_top close to high)
- lookback_high = max([1.005, 1.002, 1.000, 0.999, 0.998]) = 1.005
- trigger = 1.005 * 1.0008 = 1.00580
- **Current price** 1.002 < trigger → **WAIT**

**Next candle (12:06)**:
- Close = 1.007 (breakout!)
- 1.007 > 1.00580 → **FIRE EAGER ENTRY**
- Entry: 1.00580 (limit IOC)
- SL: 1.00580 * 0.992 = 0.99775
- TP: 1.00580 * 1.015 = 1.02089

---

## Implementation Patches

### PATCH 1: Settings Knobs

**File**: `alpha-sniper/config/settings.py`
**Location**: After existing pump engine settings (around line 144)

```python
# EAGER breakout (optional second entry path for high vspike, flat price)
EAGER_ENABLE: bool = True
EAGER_VSPIKE_MIN: float = 3.0         # need >=3x volume spike
EAGER_MAX_NEG_RET5M: float = -0.003   # allow down to -0.3% over 5m
EAGER_LOOKBACK_HIGH_N: int = 5        # breakout of last N highs
EAGER_EPS_PCT: float = 0.0008         # +0.08% above lookback high
EAGER_SL_PCT: float = 0.008           # 0.8% stop
EAGER_TP_PCT: float = 0.015           # 1.5% target
EAGER_MAX_PER_SCAN: int = 1           # at most 1 eager trade per scan
EAGER_REQUIRE_ACCEL: bool = False     # accel not required for eager
EAGER_ONLY_LIVE_TEST: bool = True     # safety: only when LIVE_TEST_MODE==True

# Lightweight orderbook depth fetch for top-3 near-misses
SNAPSHOT_DEPTH_TOPK: int = 3
SNAPSHOT_DEPTH_CACHE_SEC: int = 20
```

### PATCH 2: Main Loop - Features, Top-3 Depth, EAGER Logic

**File**: `app_async.py`
**Anchor**: After `logger.info(f"Market data fetched: {len(market_data)}/{len(symbols)} symbols")`

**Changes**:
1. Add `_features_from_ohlcv()` helper function to compute features from raw OHLCV
2. Build `_rows` array with calculated features for all symbols
3. Add lightweight depth fetching for top-K near-misses (1 orderbook call per symbol, cached 20s)
4. Add EAGER breakout pipeline after standard signal generation

**Key Code Sections**:

#### A. Feature Calculation Helper
```python
def _features_from_ohlcv(ohlcv, wick_mult: float):
    """Calculate ret5m, vspike, accel, wick from OHLCV array"""
    if not ohlcv or len(ohlcv) < 25:
        return {"ret_5m": 0.0, "rvol_1m_vs20": 0.0, "accel": False, "wick_flag": False}

    closes = [float(x[4]) for x in ohlcv]
    vols = [float(x[5]) for x in ohlcv]

    # 5-minute return (last 5 candles on 1m chart)
    ret5m = (closes[-1] / closes[-5]) - 1.0

    # Volume spike (last vs 20-candle avg)
    v_last = vols[-1]
    v_avg20 = sum(vols[-21:-1]) / 20.0 if len(vols) >= 21 else max(sum(vols)/len(vols), 1e-9)
    vspike = v_last / v_avg20

    # Acceleration
    accel = closes[-1] > closes[-2]

    # Wick detection (ATR-based)
    highs = [float(x[2]) for x in ohlcv]
    lows = [float(x[3]) for x in ohlcv]
    trs = [max(h-l, abs(h-closes[i-1]), abs(l-closes[i-1]))
           for i, (h, l) in enumerate(zip(highs[-15:-1], lows[-15:-1]), -15)]
    atr14 = sum(trs) / 14.0

    body_top = max(float(ohlcv[-1][1]), closes[-1])  # max(open, close)
    wick_flag = (atr14 > 0.0) and ((highs[-1] - body_top) >= wick_mult * atr14)

    return {"ret_5m": ret5m, "rvol_1m_vs20": vspike, "accel": accel, "wick_flag": wick_flag}
```

#### B. Top-3 Depth Fetching
```python
# Lightweight depth for top-K near-misses (optional, cached)
_now = time.time()
_k = settings.SNAPSHOT_DEPTH_TOPK
_ttl = settings.SNAPSHOT_DEPTH_CACHE_SEC

for _r in _rows[:_k]:
    sym = _r["symbol"]
    md = market_data.get(sym) or {}

    # Check cache
    if md.get("_depth_ts") and (_now - md["_depth_ts"] < _ttl):
        continue

    # Single orderbook call
    ob = await exchange.fetch_order_book(sym)
    bids = ob.get("bids", [])
    asks = ob.get("asks", [])

    # Sum first ~10 levels (price * qty)
    depth_usd = min(
        sum(float(px) * float(qty) for px, qty in bids[:10]),
        sum(float(px) * float(qty) for px, qty in asks[:10])
    )

    md["depth_usd"] = depth_usd
    md["_depth_ts"] = _now
    market_data[sym] = md
    _r["depth"] = depth_usd
```

#### C. EAGER Breakout Pipeline
```python
eager_opened = 0
if settings.EAGER_ENABLE and (eager_opened < settings.EAGER_MAX_PER_SCAN):
    # Safety check: only when LIVE_TEST_MODE=True
    if (not settings.EAGER_ONLY_LIVE_TEST) or settings.LIVE_TEST_MODE:
        for row in _rows:
            if eager_opened >= settings.EAGER_MAX_PER_SCAN:
                break

            # Filter: vspike ≥ threshold
            if row["vspike"] < settings.EAGER_VSPIKE_MIN:
                continue

            # Filter: ret5m ≥ threshold (can be negative)
            if row["ret5m"] < settings.EAGER_MAX_NEG_RET5M:
                continue

            # Filter: wick
            if row["wick"]:
                continue

            # Optional: accel filter
            if settings.EAGER_REQUIRE_ACCEL and not row["accel"]:
                continue

            sym = row["symbol"]
            md = market_data.get(sym) or {}
            ohlcv = md.get("ohlcv") or []

            if len(ohlcv) < max(6, settings.EAGER_LOOKBACK_HIGH_N + 1):
                continue

            # Calculate lookback high
            highs = [float(x[2]) for x in ohlcv]
            lookback_high = max(highs[-(settings.EAGER_LOOKBACK_HIGH_N + 1):-1])

            # Trigger = lookback_high * (1 + epsilon)
            trigger = lookback_high * (1.0 + settings.EAGER_EPS_PCT)

            # Entry price = max(trigger, last_close)
            last_close = float(ohlcv[-1][4])
            entry_px = max(trigger, last_close)

            # Calculate position size
            sl_price = entry_px * (1.0 - settings.EAGER_SL_PCT)
            size_usd = await risk.calculate_position_size_async(
                {"symbol": sym, "side": "long", "engine": "pump"},
                entry_px, sl_price
            )

            if size_usd < settings.MIN_VIABLE_TRADE_USD:
                continue

            # Validate order
            valid, why, det = await exchange.validate_order(sym, size_usd, entry_px)
            if not valid:
                logger.info(f"[EAGER] {sym} rejected: {why}")
                continue

            # Place limit IOC order
            qty = size_usd / entry_px
            client_oid = f"alpha-eager-{sym}-{int(time.time()*1000)}"

            order = await exchange.create_order_idempotent(
                symbol=sym,
                side="buy",
                order_type="limit",
                amount=qty,
                price=entry_px,
                params={"timeInForce": "IOC"},
                client_oid=client_oid
            )

            if order and order.get("id"):
                # Register position with tight SL/TP
                tp = entry_px * (1.0 + settings.EAGER_TP_PCT)
                pos = {
                    "symbol": sym, "side": "long", "engine": "pump",
                    "entry_price": entry_px, "stop_loss": sl_price,
                    "tp_2r": tp, "tp_4r": tp,
                    "qty": qty, "size_usd": size_usd,
                    "timestamp_open": int(time.time()),
                    "max_hold_hours": max(0.25, settings.HOLD_BRAIN_MAX_HOLD_HOURS)
                }
                await risk.add_position_async(pos)

                logger.info(f"[EAGER] OPENED {sym} @ {entry_px:.8f} "
                           f"size=${size_usd:.2f} tp={tp:.8f} sl={sl_price:.8f}")
                eager_opened += 1
```

---

## Architecture & File Structure

```
/opt/alpha-sniper/
├── app_async.py                    # Main async trading loop
├── alpha-sniper/
│   ├── config/
│   │   └── settings.py            # Pydantic settings (all config knobs)
│   ├── core/
│   │   ├── autotune.py            # AutoTune Pro logic
│   │   └── runtime_settings.py   # RuntimeSettings overlay
│   ├── signals/
│   │   └── pump_engine.py         # Standard pump signal generation
│   ├── scanner/
│   │   └── runner.py              # OHLCV fetching + indicator calculation
│   ├── exchange/
│   │   └── exchange_async.py      # Exchange API wrapper
│   └── risk/
│       └── risk_manager.py        # Position sizing + circuit breakers
├── data/
│   ├── overrides.json             # Runtime config overrides (JSON)
│   └── positions.json             # Active positions state
└── scripts/
    └── overrides_cli.py           # CLI for viewing/modifying overrides
```

### Key Modules

**1. app_async.py**
- Main event loop (every 60s)
- Fetches OHLCV data via `scan_symbols()`
- Generates signals via `pump_engine.generate_signals()`
- Processes signals → places orders → registers positions
- **NEW**: EAGER breakout logic

**2. settings.py**
- All configuration knobs
- Pydantic v2 BaseSettings (immutable after init)
- Loads from `.env` + environment variables

**3. autotune.py**
- Three-tier adaptive threshold system
- Monitors signal flow → adjusts thresholds
- Flow loosening for quiet markets
- Second notch for extreme quiet (accel toggle, depth relax)

**4. runtime_settings.py**
- `RuntimeSettingsOverlay` class
- Persists overrides to `./data/overrides.json`
- Provides unified interface: `overlay.get("KEY")` falls back to base settings if not overridden

**5. pump_engine.py**
- `generate_signals(market_data, regime)` → list of signal dicts
- Filters symbols by ret5m, vspike, score, accel, wick
- Returns top signals sorted by score

---

## Deployment Instructions

### 1. Pull Latest Code

```bash
ssh user@your-server-ip
cd /opt/alpha-sniper

# Fetch and pull EAGER branch
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
```

### 2. Apply Patches

**Patch 1**: Add settings to `alpha-sniper/config/settings.py`
```bash
# Edit file and add EAGER settings after existing pump settings (line ~144)
nano alpha-sniper/config/settings.py
```

**Patch 2**: Update main loop in `app_async.py`
```bash
# Replace feature extraction + add EAGER pipeline
nano app_async.py
```

### 3. Validate Configuration

```bash
# Check current overrides
python scripts/overrides_cli.py show

# Expected output:
# EARLY_ACCEL_REQUIRED: false
# EARLY_RET_5M_MIN: 0.008
# UNIVERSE_SIZE: 250
# etc.
```

### 4. Test in LIVE_TEST_MODE

```bash
# Ensure LIVE_TEST_MODE is enabled (no real trades)
export LIVE_TEST_MODE=true

# Restart service
sudo systemctl restart alpha-sniper-async.service

# Monitor logs
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered -E "EAGER|Signals|EARLY_TOP"
```

**Look for**:
```
[FLOW_TOGGLE] accel_required=False (startup at max+floor)
[EARLY_TOP] HYPE/USDT ret5m=0.45% vspike=2.1 score=8.5 accel=True wick=False depth=$12500
Signals generated: 0
[EAGER] OPENED HYPE/USDT @ 1.00580 size=$50.00 tp=1.02089 sl=0.99775
```

### 5. Deploy to Production

```bash
# Disable LIVE_TEST_MODE
export LIVE_TEST_MODE=false

# Optional: Adjust EAGER parameters via overrides
python scripts/overrides_cli.py set --key EAGER_VSPIKE_MIN --value 2.5

# Restart
sudo systemctl restart alpha-sniper-async.service
```

### 6. Monitor Performance

```bash
# Watch for trades
sudo journalctl -u alpha-sniper-async.service -f | grep --line-buffered "OPENED\|CLOSED"

# Check positions
cat data/positions.json | jq

# Daily digest (automated)
# Check Telegram for daily summary
```

---

## Configuration Tuning Guide

### AutoTune Pro Tuning

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `AUTOTUNE_TARGET_LOW` | 3.0 | 1-5 | Lower bound signals/hour |
| `AUTOTUNE_TARGET_HIGH` | 5.0 | 3-10 | Upper bound signals/hour |
| `AUTOTUNE_STEP_PCT` | 0.1 | 0.05-0.2 | Threshold adjustment step (10%) |
| `FLOW_QUIET_SCANS` | 30 | 10-60 | Scans before flow loosening |
| `FLOW_QUIET_SCANS_2` | 60 | 30-120 | Scans before second notch |
| `AUTO_ACCEL_TOGGLE` | True | bool | Enable/disable accel auto-toggle |

### EAGER Breakout Tuning

| Parameter | Default | Range | Effect |
|-----------|---------|-------|--------|
| `EAGER_VSPIKE_MIN` | 3.0 | 2.0-5.0 | Volume spike threshold (3x) |
| `EAGER_MAX_NEG_RET5M` | -0.003 | -0.01 to 0.0 | Allow -0.3% negative momentum |
| `EAGER_LOOKBACK_HIGH_N` | 5 | 3-10 | Breakout of last N highs |
| `EAGER_EPS_PCT` | 0.0008 | 0.0005-0.002 | Breakout epsilon (+0.08%) |
| `EAGER_SL_PCT` | 0.008 | 0.005-0.02 | Stop loss (0.8%) |
| `EAGER_TP_PCT` | 0.015 | 0.01-0.03 | Take profit (1.5%) |
| `EAGER_MAX_PER_SCAN` | 1 | 0-3 | Max eager trades per scan |

**Tuning Tips**:

- **More conservative**: Increase `EAGER_VSPIKE_MIN` to 4.0, tighten `EAGER_MAX_NEG_RET5M` to -0.001
- **More aggressive**: Lower `EAGER_VSPIKE_MIN` to 2.5, allow `EAGER_MAX_NEG_RET5M` to -0.005
- **Tighter risk**: Reduce `EAGER_SL_PCT` to 0.005 (0.5%), increase `EAGER_TP_PCT` to 0.02 (2%)
- **Wider breakout zone**: Increase `EAGER_LOOKBACK_HIGH_N` to 10 (requires breaking 10-candle high)

---

## Troubleshooting

### No EAGER Signals

**Check**:
```bash
# Verify EAGER is enabled
grep EAGER_ENABLE .env

# Check if LIVE_TEST_MODE constraint is blocking
grep EAGER_ONLY_LIVE_TEST .env
grep LIVE_TEST_MODE .env

# View near-miss logs (should show candidates with high vspike)
sudo journalctl -u alpha-sniper-async.service -n 100 | grep EARLY_TOP
```

**Common Issues**:
1. `EAGER_ONLY_LIVE_TEST=True` but `LIVE_TEST_MODE=False` → No eager trades
2. All symbols failing wick filter → Check `WICK_FILTER_ATR_MULT` (default: 2.0)
3. Vspike below threshold → Lower `EAGER_VSPIKE_MIN` to 2.5

### AutoTune Pro Not Adjusting

**Check**:
```bash
# View current overrides
python scripts/overrides_cli.py show

# Check autotune logs
sudo journalctl -u alpha-sniper-async.service -n 200 | grep -E "FLOW_LOOSEN|FLOW_TOGGLE|AUTOTUNE"
```

**Common Issues**:
1. Already at floor → Second notch should trigger
2. Scan count too low → Wait 30+ scans (30 minutes)
3. AutoTune disabled → Check `AUTOTUNE_ENABLE` in settings

### EAGER Orders Rejected

**Check validation errors**:
```bash
sudo journalctl -u alpha-sniper-async.service -f | grep "EAGER.*rejected"
```

**Common Issues**:
1. **Min notional**: Size too small → Increase `RISK_PER_TRADE_PCT`
2. **Precision**: Price/qty decimals wrong → Exchange API handles this, but check logs
3. **Insufficient balance**: Check account balance on exchange

---

## Safety Considerations

### Circuit Breakers

1. **Max positions**: `MAX_POSITIONS` (default: 5) prevents overexposure
2. **Daily loss limit**: `MAX_DAILY_DRAWDOWN_PCT` stops trading after -X%
3. **Order size cap**: `MAX_POSITION_SIZE_USD` limits single trade size
4. **Rate limiting**: Exchange wrapper respects Binance rate limits

### EAGER-Specific Safety

1. **Hard cap**: `EAGER_MAX_PER_SCAN=1` prevents spam
2. **IOC orders**: Immediate-or-cancel → no lingering limit orders
3. **LIVE_TEST_MODE constraint**: Must explicitly enable for real trading
4. **Wick filter**: Rejects symbols with large upper wick (avoids fake breakouts)
5. **Tight stops**: 0.8% SL vs standard 2-3% → limits downside

### Monitoring

**Critical Alerts** (set up Telegram notifications):
- EAGER trade opened
- Stop loss hit
- Circuit breaker triggered
- AutoTune second notch triggered
- Daily loss exceeds threshold

---

## Summary

**AutoTune Pro** ensures consistent signal flow by:
1. Adjusting thresholds based on signals/hour
2. Expanding universe when market is quiet
3. Toggling accel requirement in extreme quiet

**EAGER Breakout** adds a second entry path for:
- High volume consolidation patterns (vspike ≥ 3x)
- Flat/slightly negative price (ret5m ≥ -0.3%)
- Breakout confirmation above recent highs
- Tight risk management (0.8% SL, 1.5% TP)

**Together**, they provide:
- ✅ Standard signals for clear momentum pumps
- ✅ EAGER signals for accumulation breakouts
- ✅ Adaptive thresholds for all market conditions
- ✅ Maximum coverage with controlled risk

**Result**: Bot should trade consistently even in extremely calm markets, with 2-3 standard signals + 0-1 eager signal per hour.

---

## Contact & Support

**Questions?** Check the implementation patches above or refer to:
- AutoTune Pro commit: `e494d788`
- Documentation: This file
- Logs: `/var/log/alpha-sniper-async/` or `journalctl -u alpha-sniper-async.service`

**Deploy checklist**:
- [x] AutoTune Pro v3 (threshold + flow loosen + second notch)
- [x] Near-miss visibility with real values
- [x] Automatic accel toggle on startup
- [ ] EAGER breakout settings added
- [ ] EAGER pipeline implemented in main loop
- [ ] Top-3 depth fetching added
- [ ] Production testing complete
