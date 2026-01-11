# Migration Notes - Alpha Sniper Hardening

## 🚨 **IMPORTANT: Read Before Applying**

**Current Status:** Bot is WORKING and trading successfully.
**Recommendation:** DO NOT apply these patches while bot is actively trading.
**When to apply:** During a scheduled maintenance window after collecting 50+ trades of data.

## New Settings (Optional)

If you choose to apply the hardening patches, these new settings will be available:

### In `.env.async` or `overrides.json`:

```bash
# Reserve cushion for fees/slippage (default: 3.0)
ALPHA_RESERVE_USDT=3.0

# Adaptive price padding for EAGER entries (default: 0.0025 = 0.25%)
ALPHA_EAGER_EPS_PCT=0.0025

# Timeout for IOC emulation if exchange doesn't support IOC (default: 300ms)
ALPHA_IOC_EMULATION_TIMEOUT_MS=300

# Enable retry with 95% balance on insufficient funds error (default: true)
ALPHA_ORDER_RETRY_ON_BALANCE_ERROR=true
```

### Setting Overrides (Recommended if applying patches):

```bash
cd /opt/alpha-sniper/alpha-sniper
source ../venv/bin/activate

# Set new parameters
python ../scripts/overrides_cli.py set --key RESERVE_USDT --value 3.0
python ../scripts/overrides_cli.py set --key EAGER_EPS_PCT --value 0.0025
python ../scripts/overrides_cli.py set --key IOC_EMULATION_TIMEOUT_MS --value 300
python ../scripts/overrides_cli.py set --key ORDER_RETRY_ON_BALANCE_ERROR --value true

# Verify
python ../scripts/overrides_cli.py show
```

## What Changes

### 1. Sizing Pipeline Enhancement
**Before:**
- Risk calc → Auto-bump → LIVE_TEST cap → Validate → Order

**After:**
- Risk calc → Auto-bump (with reserve) → LIVE_TEST cap → Balance clamp → Precision round → Depth check → Order
- More detailed logging at each step

### 2. IOC Fallback
**Before:**
- Always uses `timeInForce='IOC'`
- If exchange rejects, order fails

**After:**
- Tries IOC first
- If "invalid type" error, auto-detects and falls back to GTC + immediate cancel
- Logs TIF strategy used

### 3. Precision Handling
**Before:**
- CCXT precision rounding (working)
- Silent if rounds to zero

**After:**
- Same CCXT rounding
- Logs `[PRECISION]` messages
- Attempts to bump to minimum if rounds to zero

### 4. print_settings.py
**Before:**
- Outputs JSON with possible warnings

**After:**
- `--json` flag suppresses all warnings for clean piping

## Database Changes

**None.** These patches do not modify the database schema.

## Compatibility

- **Python:** 3.12+ (no change)
- **CCXT:** 4.5.x (no change)
- **Dependencies:** No new dependencies
- **Backward Compatible:** Yes - all new settings have defaults

## Testing Plan (If Applying Patches)

1. **Stop bot during low-activity period:**
   ```bash
   sudo systemctl stop alpha-sniper-async.service
   ```

2. **Apply patches** (see PATCHES.diff)

3. **Test in dry-run mode first** (optional):
   ```bash
   # Temporarily set to SIM mode
   python scripts/overrides_cli.py set --key MODE --value SIM
   sudo systemctl start alpha-sniper-async.service

   # Watch for 5 minutes
   sudo journalctl -u alpha-sniper-async.service -f

   # If looks good, switch back to LIVE
   python scripts/overrides_cli.py set --key MODE --value LIVE
   sudo systemctl restart alpha-sniper-async.service
   ```

4. **Monitor logs for new patterns:**
   ```bash
   bash verification_script.sh
   ```

## Expected Log Changes

### New Log Lines You'll See:

```
[AUTO_BUMP] WLD/USDT $0.50 → $7.50 (action=bumped, min_cost=$5.00)
[CLAMP] BTC/USDT $175.00 → $169.00 (free=$172.00, reserve=$3.00)
[PRECISION] Rounded amount 0.123456789 → 0.12345678 (8 decimals)
[ORDER_TIF] IOC supported on mexc
[EAGER] SYM/USDT skipped: depth $2500 < floor $5000
[EAGER] SYM/USDT skipped: unaffordable (need≥$5.00, cap=$2.50)
[EAGER] SYM/USDT skipped: rounded_to_zero (amount_raw=0.00000001)
```

### Logs You Won't See Anymore:

```
[EAGER] ... rejected: insufficient_quote_balance {'notional': 350, 'free': 172}
```
*(Should already be gone with current LIVE_TEST fix)*

## Performance Impact

**Negligible:**
- One additional Decimal conversion per order (~microseconds)
- One IOC detection attempt on first order only
- Slightly more logging (minimal overhead)

## Rollback Plan

See ROLLBACK.md for detailed instructions.

## Questions?

If you see new error patterns after applying patches, check logs:
```bash
sudo journalctl -u alpha-sniper-async.service --since "10 minutes ago" | grep ERROR
```

Report issues with full context (last 100 log lines before error).
