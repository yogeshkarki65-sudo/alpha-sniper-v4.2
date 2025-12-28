# Alpha Sniper v4.2.3 - Production Runbook

**Complete guide for deploying and operating the trading bot in production**

---

## Table of Contents

1. [Quick Start - Deployment](#quick-start---deployment)
2. [Smoke Tests](#smoke-tests)
3. [Deployment Process Details](#deployment-process-details)
4. [Observability & Debugging](#observability--debugging)
5. [Rollback Procedures](#rollback-procedures)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start - Deployment

### Prerequisites

1. **Server access** with sudo privileges
2. **Git repository** cloned to production server
3. **Python venv** created and activated
4. **Systemd service** configured (alpha-sniper-live.service)
5. **.env file** configured with API keys

### Deploy Latest Code

```bash
# 1. Navigate to repository
cd /opt/alpha-sniper

# 2. Run deployment script
scripts/deploy.sh claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# 3. Monitor logs
tail -f logs/bot.log
```

**That's it!** The script handles:
- ✅ Git pull
- ✅ Dependency installation
- ✅ Syntax checks
- ✅ Smoke tests
- ✅ Service restart
- ✅ Health verification
- ✅ Auto-rollback on failure

---

## Smoke Tests

### Test 1: Market Data (Safe - No Orders)

Tests REAL exchange connectivity WITHOUT placing orders:

```bash
# Run market data smoke test
python scripts/smoke_market_data.py
```

**What it tests:**
- ✅ Ticker fetching
- ✅ Orderbook depth
- ✅ OHLCV data
- ✅ Spread calculations
- ✅ Exchange limits (minQty, minNotional, precision)
- ✅ Viability gates (spread, depth, size)
- ✅ Order validation logic

**Exit codes:**
- `0` = All tests PASSED ✅
- `1` = Some tests FAILED ❌
- `2` = Configuration error ⚙️

**Example output:**
```
================================================================================
TEST 1: Market Data Fetching (BTC/USDT)
================================================================================
[1.1] Fetching ticker...
✓ PASS: Ticker | last=50123.45 | bid=50123.00 | ask=50124.00
[1.2] Fetching orderbook...
✓ PASS: Orderbook | bids=50 levels | asks=50 levels
[1.3] Fetching OHLCV (1h, 200 candles)...
✓ PASS: OHLCV | 200 candles retrieved

================================================================================
TEST 2: Liquidity Metrics (BTC/USDT)
================================================================================
✓ PASS: Spread within limits (0.01% ≤ 0.30%)
✓ PASS: Depth sufficient ($1,234,567 ≥ $2,000)

================================================================================
SMOKE TEST SUMMARY
================================================================================
✓ ALL TESTS PASSED - Market data system is HEALTHY
```

---

### Test 2: Order Lifecycle (GATED - Real Orders!)

⚠️ **WARNING: This test places REAL ORDERS with REAL MONEY!**

Tests REAL order placement (disabled by default):

```bash
# Dry-run mode (default - shows what would happen):
python scripts/smoke_order_lifecycle.py

# LIVE mode (ACTUALLY PLACES ORDERS):
SMOKE_TEST_ALLOW_ORDERS=true python scripts/smoke_order_lifecycle.py
```

**Safety measures:**
1. **Disabled by default** - Requires explicit `SMOKE_TEST_ALLOW_ORDERS=true`
2. **Confirms before execution** - 5 second countdown
3. **Small size** - Uses `SMOKE_TEST_USD` (default $10)
4. **Abortable** - Press Ctrl+C to cancel

**What it tests:**
- ✅ ORDER_VALIDATING lifecycle log
- ✅ ORDER_PLACED lifecycle log
- ✅ ORDER_FILLED lifecycle log
- ✅ Real exchange integration

---

## Deployment Process Details

### Step-by-Step Breakdown

#### 1. Pre-flight Checks
```bash
✓ Git repository OK
✓ Network connectivity OK
✓ Service found: alpha-sniper-live.service
✓ Python environment OK: /opt/alpha-sniper/venv/bin/python
```

**What it checks:**
- Git repository exists
- Network can reach GitHub
- Systemd service is configured
- Python virtual environment exists

#### 2. Rollback Point Creation
```bash
Current commit: a7d79f86
Current branch: claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
✓ Rollback point saved
```

**What it saves:**
- Current git commit hash
- Current branch name

#### 3. Stop Service
```bash
Stopping service: alpha-sniper-live.service
✓ Service stopped
```

#### 4. Pull Latest Code
```bash
Checking out: claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
Pulling latest changes...
✓ Code updated to: 509b2ca7

Changes deployed:
509b2ca7 feat: Add v4.2.2 deployment script
d881eb61 feat: Add v4.2.2 enhancements
```

#### 5. Install Dependencies
```bash
Installing Python dependencies...
✓ Dependencies installed
```

#### 6. Syntax Checks
```bash
Compiling Python files...
✓ Syntax checks passed
```

#### 7. Smoke Tests
```bash
Running smoke tests (market data only, no orders)...
✓ Smoke tests PASSED
```

#### 8. Restart Service
```bash
Starting service: alpha-sniper-live.service
✓ Service started
```

#### 9. Health Check
```bash
Verifying service is active...
✓ Service is active

Verifying bot health (waiting max 60s for successful scan)...
✓ Bot health check PASSED (scan activity detected)
```

---

## Observability & Debugging

### v4.2.3 Observability Enhancements

#### Reason-Coded Skip Logging

**Every skipped signal now has a standardized reason code:**

```python
# Example log output:
📊 No new positions opened | skip_reasons: SKIP_TOO_SMALL_AFTER_LIQUIDITY=3 | SKIP_MIN_NOTIONAL=2 | SKIP_SPREAD_TOO_HIGH=1
```

**Reason codes:**
- `SKIP_TOO_SMALL_AFTER_LIQUIDITY` - LiquidityGuard rejected (size=0)
- `SKIP_SPREAD_TOO_HIGH` - Spread > MAX_SPREAD_PCT_ORDER
- `SKIP_DEPTH_TOO_LOW` - Orderbook depth insufficient
- `SKIP_MIN_QTY` - Below exchange minimum quantity
- `SKIP_MIN_NOTIONAL` - Below exchange minimum notional value
- `SKIP_PRECISION_ROUNDING` - Too much precision loss (>5%)
- `SKIP_TOO_SMALL_AFTER_VALIDATION` - Final size check failed
- `EXCHANGE_REJECTED` - Exchange returned no order ID
- `ORDER_EXCEPTION` - Exception during order creation
- `CORE_*` - CORE filter rejection (cooldown, heat, etc.)

---

#### Viability Check Logging

**Before each order, viability gates are logged:**

```python
[VIABILITY_CHECK] PASS BTC/USDT | size=$25.00 | spread=0.02% | depth=$1,234,567
[VIABILITY_CHECK] REJECT ETH/USDT | reason=SPREAD_TOO_HIGH | spread=0.45% > max=0.30%
[VIABILITY_CHECK] REJECT SOL/USDT | reason=DEPTH_TOO_LOW | depth=$5,000 < required=$10,000 (size=$50 * 200x)
```

---

#### Order Lifecycle Logging

**Full visibility into order execution:**

```python
[ORDER_VALIDATING] BTC/USDT | side=long | size=$25.00 | amount=0.000499 | price=50123.45
[ORDER_VALIDATION] PASS BTC/USDT | {'symbol': 'BTC/USDT', 'qty_rounded': 0.000499, 'notional': 25.01, ...}
[ORDER_PLACED] BTC/USDT | id=12345678 | side=long | amount=0.000499 | status=closed
[ORDER_FILLED] BTC/USDT | id=12345678 | filled_qty=0.000499 | avg_price=50124.30
```

**On failure:**

```python
[ORDER_REJECTED] BTC/USDT | reason=EXCHANGE_REJECTED | order_response=None
[ORDER_EXCEPTION] ETH/USDT | error=InsufficientFunds | error_type=InsufficientFunds
```

---

#### CORE Rejection Observability

**All CORE filter rejections are logged with structured data (from v4.2.2):**

```python
[CORE_REJECT] symbol=BTC/USDT | reason=COOLDOWN | side=long | remaining_hours=2.3
[CORE_REJECT] symbol=ETH/USDT | reason=PORTFOLIO_HEAT | current_heat=1.15% | engine_risk=0.25% | total=1.40% | max=1.20%
[CORE_REJECT] symbol=SOL/USDT | reason=MAX_POSITIONS | current_positions=5 | max=5
```

---

### Log Monitoring Commands

```bash
# Monitor all logs
tail -f /opt/alpha-sniper/logs/bot.log

# Filter for skip reasons
tail -f logs/bot.log | grep "skip_reasons"

# Filter for order lifecycle
tail -f logs/bot.log | grep -E "(ORDER_VALIDATING|ORDER_PLACED|ORDER_FILLED|ORDER_REJECTED)"

# Filter for CORE rejections
tail -f logs/bot.log | grep "CORE_REJECT"

# Filter for viability checks
tail -f logs/bot.log | grep "VIABILITY_CHECK"

# Filter for liquidity guard
tail -f logs/bot.log | grep "LiquidityGuard"
```

---

## Rollback Procedures

### Automatic Rollback (Built-in)

The deployment script automatically rolls back if:
- Smoke tests fail
- Service fails to start
- Health check fails

**Rollback actions:**
1. Restores previous git commit
2. Reinstalls previous dependencies
3. Restarts service
4. Verifies service is active

---

### Manual Rollback

If you need to manually rollback:

```bash
# 1. Stop service
sudo systemctl stop alpha-sniper-live.service

# 2. Checkout previous commit
cd /opt/alpha-sniper
git log --oneline -10  # Find commit to rollback to
git checkout <previous-commit-hash>

# 3. Reinstall dependencies
source venv/bin/activate
pip install -r requirements.txt

# 4. Restart service
sudo systemctl start alpha-sniper-live.service

# 5. Verify
sudo systemctl status alpha-sniper-live.service
tail -f logs/bot.log
```

---

## Troubleshooting

### Issue: "No new positions opened" but no skip reasons

**Cause:** No signals were generated (not a rejection issue)

**Check:**
```bash
# Look for signal generation in logs
grep "Processing.*signals" logs/bot.log | tail -20

# Check PUMP_DEBUG logs
grep "PUMP_DEBUG" logs/bot.log | tail -50
```

**Fix:**
- If seeing `Processing 0 signal(s)`, check signal generation parameters
- Use auto-optimizer to tune parameters
- Check market regime and filters

---

### Issue: All signals rejected with `SKIP_SPREAD_TOO_HIGH`

**Cause:** Spread too high for current config

**Check:**
```bash
# See what spreads are being measured
grep "VIABILITY_CHECK" logs/bot.log | tail -20
```

**Fix:**
```bash
# Increase spread tolerance in .env
MAX_SPREAD_PCT_ORDER=0.50  # Was 0.30
```

---

### Issue: All signals rejected with `SKIP_MIN_NOTIONAL`

**Cause:** Trade size too small for exchange minimums

**Check validation details:**
```bash
grep "ORDER_VALIDATION.*REJECT" logs/bot.log | tail -20
```

**Fix:**
```bash
# Increase minimum viable trade size
MIN_VIABLE_TRADE_USD=15.0  # Was 10.0
```

---

### Issue: Deployment fails at smoke tests

**Cause:** Network issue or exchange limits changed

**Debug:**
```bash
# Run smoke test manually to see detailed errors
python scripts/smoke_market_data.py
```

**Fix:**
- Check network connectivity
- Check exchange API status
- Update SMOKE_TEST_SYMBOL if current symbol has issues

---

### Issue: Service starts but no scan activity

**Cause:** Bot initialization error or configuration issue

**Check:**
```bash
# Look for initialization errors
sudo journalctl -u alpha-sniper-live.service -n 100

# Check recent logs
tail -100 logs/bot.log
```

**Fix:**
- Check .env configuration
- Verify API keys are valid
- Check Python dependencies

---

## Configuration Reference

### v4.2.3 New ENV Variables

```bash
# === ORDER VIABILITY & EXCHANGE VALIDATION ===
MIN_VIABLE_TRADE_USD=10.0              # Minimum trade size after all scaling
MAX_SPREAD_PCT_ORDER=0.30              # Reject if spread > this %
MIN_DEPTH_MULTIPLE=200                 # depth_usd must be >= adjusted_usd * this
ORDERBOOK_DEPTH_LEVELS=10              # Number of orderbook levels to analyze
VALIDATION_FEE_BUFFER_PCT=0.20         # Extra buffer for fees/slippage (20%)
EXCHANGE_TAKER_FEE_FALLBACK=0.001      # 0.1% fallback fee if not available

# === PRODUCTION SMOKE TESTS ===
REAL_MARKET_SMOKE_TEST=false           # Enable smoke tests
SMOKE_TEST_ALLOW_ORDERS=false          # Allow real orders in smoke test (DANGEROUS)
SMOKE_TEST_SYMBOL=BTC/USDT             # Symbol for smoke tests
SMOKE_TEST_USD=10.0                    # USD size for smoke test orders
```

---

## Deployment Checklist

Before deploying to production:

- [ ] **Smoke tests pass** on staging/dev environment
- [ ] **Config reviewed** - all new ENV vars set appropriately
- [ ] **Backup created** - current .env and database backed up
- [ ] **Notification ready** - Telegram configured to receive alerts
- [ ] **Monitoring ready** - Know how to access logs
- [ ] **Rollback plan** - Know how to rollback manually if needed
- [ ] **Off-hours deployment** - Deploy during low-volume periods
- [ ] **Monitor first hour** - Watch logs closely after deployment

---

## Support & References

- **GitHub Issues**: https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2/issues
- **Deployment Script**: `scripts/deploy.sh`
- **Smoke Tests**: `scripts/smoke_market_data.py`, `scripts/smoke_order_lifecycle.py`
- **Logs**: `/opt/alpha-sniper/logs/bot.log`
- **Service**: `sudo systemctl status alpha-sniper-live.service`

---

**Last Updated:** 2025-12-28 (v4.2.3)
