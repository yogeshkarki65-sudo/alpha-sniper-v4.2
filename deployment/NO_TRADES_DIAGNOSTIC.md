# No Trades Diagnostic & Fixes

**Problem:** Bot running in LIVE mode, generating signals, but NOT placing any orders.

**Investigation Date:** 2025-12-24
**Session ID:** `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`

---

## 🔍 ROOT CAUSE ANALYSIS

### 1. **CRITICAL: Silent Signal Rejections** ❌

**Location:** `alpha-sniper/main.py:1133, 1167-1171, 1177-1181`

**Problem:**
- Signals WERE being generated (confirmed by Telegram summaries)
- BUT rejections were logged at **DEBUG level only**
- In production logs (INFO level), rejections were invisible
- No explicit "PLACING ORDER" log before `exchange.create_order()`

**Evidence:**
```python
# BEFORE (line 1133):
self.logger.debug(f"❌ Cannot open {signal['symbol']} {signal['engine']}: {reason}")  # DEBUG only!

# AFTER:
self.logger.info(f"[SIGNAL_REJECTED] {signal['symbol']} {signal['engine']} | reason={reason}")  # INFO level
```

**Impact:** User couldn't see WHY signals weren't becoming orders.

---

### 2. **Position Sizing Too Strict for Small Accounts** 💰

**Location:** `alpha-sniper/main.py:1175-1181`

**Problem:**
- **Account size:** $58
- **Risk per trade:** 0.0015 (0.15%)
- **Position size:** $58 × 0.0015 = **$0.087 per trade**
- **Minimum position size check:** max($1.00, equity × 0.01) = **$1.00**
- **Result:** ALL signals rejected as "position too small"

**Evidence:**
```python
# BEFORE:
min_position_size = max(1.0, self.config.starting_equity * 0.01)  # $1.00 minimum
if size_usd < min_position_size:  # $0.087 < $1.00 → REJECTED!
    self.logger.debug(...)  # Silent failure
    continue
```

**Fix:**
- Lowered minimum to **$0.10** or 0.5% of equity (whichever is higher)
- Changed logging from DEBUG to INFO
- For $58 account: min = max($0.10, $58 × 0.005) = **$0.29**

**Note:** This still might be too small for MEXC minimums. See Fix #4 below.

---

### 3. **MEXC Exchange Minimum Notional** ⚖️

**Location:** `alpha-sniper/core/order_executor.py:186-194`

**Problem:**
- MEXC requires minimum $5 notional (amount × price) for most pairs
- With $0.29 position size, even with 4R target, notional ≈ **$1.16**
- **Still below MEXC $5 minimum!**

**Evidence:**
```python
# Order validation in OrderExecutor:
if notional < limits['min_notional']:  # $1.16 < $5.00 → REJECTED!
    self.logger.error(
        f"[ORDER_VALIDATE] REJECTED: {symbol} notional=${notional:.2f} < min=${limits['min_notional']:.2f}"
    )
    return False
```

**Reality Check for $58 Account:**
- To meet $5 minimum notional, need **AT LEAST** 8.6% position size
- With 0.15% risk, impossible to meet exchange minimums
- **Account is too small for LIVE trading on MEXC**

**Options:**
1. **Increase account size** to at least $200-$300
2. **Increase risk per trade** to 1-2% (dangerous, not recommended)
3. **Use SIM mode** until account grows
4. **Find exchange with lower minimums** (e.g., $1 notional)

---

### 4. **BadSymbol Spam (PEN/USDT)** 🔴

**Location:** `alpha-sniper/signals/scanner.py:153-232`, `alpha-sniper/exchange.py:454-507`

**Problem:**
- Universe built from `exchange.get_markets()` includes ALL symbols
- Some symbols (e.g., PEN/USDT) are listed but not tradeable
- Every scan cycle: `fetch_ticker` → BadSymbol error → ERROR log spam
- No blacklist to prevent retries

**Evidence from user logs:**
```
Error on attempt 1/2: fetch_ticker PEN/USDT - BadSymbol: MEXC does not have market symbol PEN/USDT
```

**Fix Implemented:**
1. **Created:** `alpha-sniper/core/symbol_blacklist.py`
   - Runtime blacklist with persistence
   - Auto-expires after 7 days (configurable)
   - Stored at `/var/lib/alpha-sniper/symbol_blacklist.json`

2. **Updated:** `alpha-sniper/exchange.py:_with_retries`
   - Detects BadSymbol errors automatically
   - Adds to blacklist on first occurrence
   - Returns None immediately (no retries)

3. **Updated:** `alpha-sniper/signals/scanner.py:_build_universe`
   - Checks runtime blacklist before including symbols
   - Prevents BadSymbol errors from recurring

**Expected Result:**
- First scan: PEN/USDT triggers BadSymbol → added to blacklist → WARNING log
- All future scans: PEN/USDT skipped silently
- **No more error spam!**

---

### 5. **Permission Denied on /var/run** 🔒

**Location:** `alpha-sniper/risk_engine.py:879`

**Problem:**
- Code tried to write `/var/run/alpha-sniper/trades_today.json`
- `/var/run` owned by root, ubuntu user can't create directories
- Every position close: permission denied warning

**Evidence from user logs:**
```
Failed to save daily trades to /var/run/alpha-sniper/trades_today.json: [Errno 13] Permission denied
```

**Fix:**
- Changed path from `/var/run/alpha-sniper/` to `/var/lib/alpha-sniper/`
- `/var/lib/alpha-sniper` already created and owned by ubuntu user via systemd
- **No more permission errors**

---

## 🛠️ **FIXES APPLIED**

### Fix #1: Explicit Order Placement Logging

**File:** `alpha-sniper/main.py`

**Changes:**
1. Line 1133: Changed DEBUG → INFO for risk rejection logging
2. Line 1167-1171: Changed DEBUG → INFO for score rejection logging
3. Line 1177-1181: Changed DEBUG → INFO for position size rejection logging
4. Line 1276-1284: **Added explicit [PLACING_ORDER] log** before `create_order()`

**New Logs:**
```
[SIGNAL_REJECTED] BTC/USDT pump | reason=Max concurrent positions reached (2)
[SIGNAL_REJECTED] ETH/USDT long | reason=score_too_low | score=75.00 < min=80.00
[SIGNAL_REJECTED] SOL/USDT pump | reason=position_too_small | size_usd=$0.09 < min=$0.29

[PLACING_ORDER] BTC/USDT | side=buy | engine=pump | amount=0.00000123 | price=50000.00 | notional=$0.06 | size_usd=$0.29
```

**Benefit:** User can now see EXACTLY why each signal is rejected or if orders are attempted.

---

### Fix #2: Lowered Minimum Position Size

**File:** `alpha-sniper/main.py:1175`

**Before:**
```python
min_position_size = max(1.0, self.config.starting_equity * 0.01)  # $1.00 or 1% of equity
```

**After:**
```python
min_position_size = max(0.10, self.config.starting_equity * 0.005)  # $0.10 or 0.5% of equity
```

**For $58 account:**
- Before: min = $1.00
- After: min = $0.29

**WARNING:** This still won't help if MEXC requires $5 minimum notional. See Reality Check section.

---

### Fix #3: BadSymbol Blacklist

**Files Created:**
- `alpha-sniper/core/symbol_blacklist.py` (new)

**Files Modified:**
- `alpha-sniper/exchange.py` (lines 424-452, 489-507)
- `alpha-sniper/signals/scanner.py` (lines 211-215)

**How It Works:**
1. Exchange catches BadSymbol errors in `_with_retries()`
2. Extracts symbol from error label
3. Adds to persistent blacklist at `/var/lib/alpha-sniper/symbol_blacklist.json`
4. Scanner checks blacklist before fetching market data
5. **No more retry spam!**

**Logs:**
```
[BLACKLIST_ADD] PEN/USDT | reason=BadSymbol | error=MEXC does not have market symbol PEN/USDT | will skip in future scans
[BLACKLIST] Skipping PEN/USDT (in runtime blacklist)
```

---

### Fix #4: Fixed /var/run Permissions

**File:** `alpha-sniper/risk_engine.py:871-889`

**Before:**
```python
filepath = '/var/run/alpha-sniper/trades_today.json'  # Can't write here!
```

**After:**
```python
dirpath = '/var/lib/alpha-sniper'  # Ubuntu user owns this
filepath = os.path.join(dirpath, 'trades_today.json')
```

**Benefit:** No more permission denied warnings.

---

## ✅ **VERIFICATION CHECKLIST**

### Pre-Deployment Verification

```bash
# 1. Verify changes are committed
cd /opt/alpha-sniper
git log --oneline -5

# 2. Check critical files exist
ls -la alpha-sniper/core/symbol_blacklist.py
ls -la deployment/NO_TRADES_DIAGNOSTIC.md

# 3. Verify /var/lib/alpha-sniper directory
ls -la /var/lib/alpha-sniper/
sudo chown -R ubuntu:ubuntu /var/lib/alpha-sniper
```

---

### Post-Deployment Verification

```bash
# 1. Pull latest code
cd /opt/alpha-sniper
git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# 2. Restart service
sudo systemctl restart alpha-sniper-live.service

# 3. Monitor logs for new logging
sudo journalctl -u alpha-sniper-live.service -f --since "1 minute ago" | grep -E "SIGNAL_REJECTED|PLACING_ORDER|BLACKLIST"

# 4. Expected logs (examples):
# [SIGNAL_REJECTED] BTC/USDT pump | reason=Portfolio heat limit (...)
# [SIGNAL_REJECTED] ETH/USDT long | reason=position_too_small | size_usd=$0.09 < min=$0.29
# [BLACKLIST_ADD] PEN/USDT | reason=BadSymbol | will skip in future scans
# [PLACING_ORDER] SOL/USDT | side=buy | amount=... | notional=$...
```

---

### Check Blacklist Status

```bash
# View blacklist file (if it exists)
cat /var/lib/alpha-sniper/symbol_blacklist.json

# Expected format:
# {
#   "blacklist": {
#     "PEN/USDT": 1734998400.0
#   },
#   "updated_at": 1734998400.0
# }
```

---

### Check Position File Permissions

```bash
# Verify trades_today.json is being created
ls -la /var/lib/alpha-sniper/trades_today.json

# Should show:
# -rw-rw-r-- 1 ubuntu ubuntu ... /var/lib/alpha-sniper/trades_today.json
```

---

## 🚨 **CRITICAL REALITY CHECK**

### Your $58 Account is TOO SMALL for MEXC Live Trading

**Math:**
- Account: $58
- Risk per trade: 0.15% → $0.087 per trade
- Minimum position size (post-fix): $0.29
- **MEXC minimum notional: $5.00**
- **Gap: $5.00 - $0.29 = $4.71 SHORT**

**To meet MEXC $5 minimum:**
- Need position size ≈ $5-$10 (depending on price)
- Requires 8.6% - 17% position sizing
- **With 0.15% risk, mathematically impossible!**

**Options:**

1. **RECOMMENDED: Increase Account Size**
   - Minimum: $200-$300 for conservative trading
   - Comfortable: $500-$1000
   - At $300: 0.15% risk = $0.45, with 10x leverage could meet minimums
   - At $1000: 0.15% risk = $1.50, much more comfortable

2. **INCREASE RISK (NOT RECOMMENDED)**
   - To meet $5 minimum from $58 account
   - Would need 8.6% position sizing
   - Risk per trade would be ~2-3% (extremely aggressive!)
   - **One bad trade = -20% account**

3. **STAY IN SIM MODE**
   - Use SIM mode to refine strategy
   - Paper trade until account grows to $200+
   - Test signals without real money risk

4. **FIND LOWER MINIMUM EXCHANGE**
   - Some exchanges have $1 minimum notional
   - But liquidity and fees may be worse

---

## 🧪 **TEST MODE (OPTIONAL)**

Want to test the order path without risking real money?

### Option 1: Dry Run with SIM Mode

```bash
# Edit /etc/alpha-sniper/alpha-sniper-live.env
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Temporarily set:
SIM_MODE=true

# Restart
sudo systemctl restart alpha-sniper-live.service

# Monitor logs - should see [SIM-OPEN] instead of [LIVE]
sudo journalctl -u alpha-sniper-live.service -f | grep -E "SIM-OPEN|PLACING_ORDER"
```

### Option 2: Single Trade Test (LIVE but Controlled)

```bash
# Edit config to allow only 1 position
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Set:
MAX_CONCURRENT_POSITIONS=1
PUMP_MAX_CONCURRENT=1

# Restart and monitor closely
sudo systemctl restart alpha-sniper-live.service
sudo journalctl -u alpha-sniper-live.service -f
```

---

## 📊 **EXPECTED BEHAVIOR AFTER FIXES**

### Scenario 1: Signal Generated, Risk Check Passes, Order Attempted

**Logs:**
```
[SCANNER] Found signal: BTC/USDT pump score=85
[PLACING_ORDER] BTC/USDT | side=buy | amount=0.00001234 | price=50000.00 | notional=$0.62
[ORDER_VALIDATE] REJECTED: BTC/USDT notional=$0.62 < min=$5.00
[ORDER_FAILED] BTC/USDT | reason=invalid_order_size | retries_exhausted=2
```

**Explanation:** Order was attempted but rejected due to MEXC $5 minimum.

---

### Scenario 2: Signal Generated, Rejected by Risk Check

**Logs:**
```
[SCANNER] Found signal: ETH/USDT long score=88
[SIGNAL_REJECTED] ETH/USDT long | reason=Max concurrent positions reached (2)
```

**Explanation:** Risk engine blocked the trade (clear reason provided).

---

### Scenario 3: Signal Generated, Position Size Too Small

**Logs:**
```
[SCANNER] Found signal: SOL/USDT pump score=92
[SIGNAL_REJECTED] SOL/USDT pump | reason=position_too_small | size_usd=$0.09 < min=$0.29
```

**Explanation:** Position size calculation resulted in tiny size (0.15% of $58).

---

### Scenario 4: BadSymbol Error (First Time)

**Logs:**
```
[SCANNER] Building universe: 850 symbols
Error on attempt 1/2: fetch_ticker PEN/USDT - BadSymbol: invalid symbol
[BLACKLIST_ADD] PEN/USDT | reason=BadSymbol | will skip in future scans
```

**Next Scan:**
```
[SCANNER] Building universe: 849 symbols
[BLACKLIST] Skipping PEN/USDT (in runtime blacklist)
```

---

## 📝 **SUMMARY**

**What Was Fixed:**
✅ Silent signal rejections → Now logged at INFO level
✅ No order placement logs → Added explicit [PLACING_ORDER] logs
✅ Position sizing too strict → Lowered minimum for small accounts
✅ BadSymbol spam → Implemented automatic blacklist
✅ Permission denied errors → Moved to /var/lib/alpha-sniper

**What Still Needs Attention:**
⚠️ **Account too small for MEXC** ($58 < $200 minimum recommended)
⚠️ **MEXC $5 minimum notional** prevents tiny orders
⚠️ **Risk/position sizing math** needs adjustment for small accounts

**Recommended Next Steps:**
1. Deploy fixes and verify improved logging
2. Confirm signal rejection reasons in logs
3. **Decide:** Stay in SIM mode OR increase account size to $200+
4. Adjust risk parameters if increasing account size
5. Test with single position limit before full deployment

---

**Files Modified:**
- `alpha-sniper/main.py` (logging improvements)
- `alpha-sniper/core/symbol_blacklist.py` (new file)
- `alpha-sniper/exchange.py` (blacklist integration)
- `alpha-sniper/signals/scanner.py` (blacklist check)
- `alpha-sniper/risk_engine.py` (path fix)

**Commit:** `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
