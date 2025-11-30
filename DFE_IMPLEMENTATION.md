# Dynamic Filter Engine (DFE) Implementation

## Overview

The Dynamic Filter Engine (DFE) makes Alpha Sniper V4.2 **self-adapting** by automatically adjusting key filters based on recent trading performance. No more manual `.env` editing - the bot learns and optimizes itself!

## What It Does

DFE runs **once per day at 00:05 UTC** and:

1. **Analyzes recent performance** from `logs/v4_trade_scores.csv`
2. **Calculates metrics:**
   - Trades per day (last 14 days)
   - Win rate (last 30 trades)
   - Average R-multiple (last 30 trades)
3. **Adjusts 4 key filters** within safe ranges
4. **Updates `.env` file** in-place (preserves all other settings)

---

## Managed Filters

DFE auto-tunes these 4 filters:

| Filter | Purpose | Safe Range |
|--------|---------|------------|
| `MIN_SCORE` | Signal quality threshold | 68 - 82 |
| `MIN_24H_QUOTE_VOLUME` | Minimum liquidity (USDT) | 8,000 - 60,000 |
| `MAX_SPREAD_PCT` | Maximum spread tolerance | 0.7% - 2.4% |
| `PUMP_MAX_AGE_HOURS` | Pump signal staleness limit | 24 - 168 hours |

All adjustments are **clamped** to these ranges - DFE will never make unsafe changes.

---

## Decision Logic

### 1. Trade Frequency Rules

**Too Few Trades (<3/day for last 14 days)**
- **Action:** Loosen all filters by ~10%
- **Reason:** Bot is too picky, missing opportunities
- **Example:**
  ```
  MIN_SCORE: 80 → 72
  MIN_24H_QUOTE_VOLUME: 50000 → 45000
  MAX_SPREAD_PCT: 0.9 → 0.99
  PUMP_MAX_AGE_HOURS: 72 → 79
  ```

**Too Many Trades (>12/day for last 14 days)**
- **Action:** Tighten all filters by ~8%
- **Reason:** Over-trading, need better selectivity
- **Example:**
  ```
  MIN_SCORE: 75 → 81
  MIN_24H_QUOTE_VOLUME: 30000 → 32400
  MAX_SPREAD_PCT: 1.5 → 1.38
  PUMP_MAX_AGE_HOURS: 96 → 88
  ```

**Goldilocks Zone (3-12 trades/day)**
- **Action:** No frequency-based adjustment
- **Reason:** Trade volume is healthy

### 2. Win Rate Rule

**Low Win Rate (<56% for last 30 trades)**
- **Action:** Tighten quality filters by ~5%
- **Reason:** Not winning enough, need better signals
- **Affects:**
  ```
  MIN_SCORE: +5%
  MIN_24H_QUOTE_VOLUME: +7%
  MAX_SPREAD_PCT: -5%
  ```

### 3. Average R-Multiple Rule

**Low Avg R (<0.6R for last 30 trades)**
- **Action:** Tighten volume and spread by ~12%
- **Reason:** R-multiples too low, need better liquidity
- **Affects:**
  ```
  MIN_24H_QUOTE_VOLUME: +12%
  MAX_SPREAD_PCT: -12%
  ```

**Note:** Adjustments are **cumulative** - multiple rules can apply simultaneously.

---

## Example Scenarios

### Scenario 1: Undertrading with Poor Win Rate

**Current Performance:**
- Trades/day: 1.8 (too few)
- Win rate: 52% (below 56%)
- Avg R: 0.8R (good)

**DFE Actions:**
1. Loosen filters ~10% (frequency rule)
2. Tighten quality ~5% (win rate rule)
3. **Net effect:** Slight loosening on volume/spread, minimal change to score

**Result:** More trades, but better quality

### Scenario 2: Overtrading with Low R-Multiples

**Current Performance:**
- Trades/day: 15.2 (too many)
- Win rate: 61% (good)
- Avg R: 0.4R (low)

**DFE Actions:**
1. Tighten filters ~8% (frequency rule)
2. Tighten volume/spread ~12% (R-multiple rule)
3. **Net effect:** Significant tightening, especially on liquidity

**Result:** Fewer trades, but higher quality (better R)

### Scenario 3: Healthy Performance

**Current Performance:**
- Trades/day: 6.5 (good)
- Win rate: 58% (good)
- Avg R: 0.85R (good)

**DFE Actions:**
- No adjustments needed!

**Result:** Filters stay the same

---

## Activation Requirements

DFE only runs if **ALL** conditions are met:

1. ✅ `DFE_ENABLED=true` in `.env`
2. ✅ `logs/v4_trade_scores.csv` exists
3. ✅ At least **10 closed trades** in the log

If any condition fails, DFE logs a message and skips adjustment (bot continues normally).

---

## Configuration

### Enable DFE

Add to `.env`:

```bash
# Dynamic Filter Engine
DFE_ENABLED=true

# Initial filter values (DFE will adjust these)
MIN_SCORE=75
MIN_24H_QUOTE_VOLUME=30000
MAX_SPREAD_PCT=1.5
PUMP_MAX_AGE_HOURS=72
```

### Disable DFE (Manual Mode)

```bash
DFE_ENABLED=false
# Filters stay as you set them
```

---

## Log Output Examples

### Successful Adjustment

```
======================================================================
🔧 Dynamic Filter Engine | Starting daily adjustment
======================================================================
DFE | Performance metrics:
  Trades/day (14d): 4.21
  Win rate (last 30): 54.2%
  Avg R (last 30): 0.523R
DFE | Current filters:
  MIN_SCORE = 75
  MIN_24H_QUOTE_VOLUME = 30000.0
  MAX_SPREAD_PCT = 1.5
  PUMP_MAX_AGE_HOURS = 72
DFE | Applying adjustment rules:
  → Trade frequency OK (4.2/day) - no frequency adjustment
  ↑ Low win rate (54.2%) - tightening quality ~5%
  ↑ Low avg R (0.523R) - tightening volume/spread ~12%
DFE | New filters:
  MIN_SCORE = 79 ↑ (+4.0)
  MIN_24H_QUOTE_VOLUME = 35880.0 ↑ (+5880.0)
  MAX_SPREAD_PCT = 1.24 ↓ (-0.26)
  PUMP_MAX_AGE_HOURS = 72 → (+0.0)
DFE | ✅ Filters updated successfully
```

### Skipped (Not Enough Data)

```
DFE | Not enough trades for adjustment (n_trades=7) - skipping
```

### Skipped (Disabled)

```
🔧 DFE disabled - filters will not auto-adjust
```

---

## Safety Features

### 1. Soft Failures
- Missing CSV → Skip, log info, continue trading
- Parse errors → Skip, log warning, continue trading
- File write errors → Log error, raise exception (admin must fix)

### 2. Clamped Ranges
- All filters clamped to safe min/max
- DFE will **never** set `MIN_SCORE=100` or `MAX_SPREAD_PCT=10%`

### 3. No Trading Logic Changes
- DFE only modifies `.env` values
- No changes to risk calculations, position sizing, or signal generation
- Existing behavior 100% preserved if `DFE_ENABLED=false`

### 4. Preserves Other Settings
- `.env` edit is surgical: only touches 4 managed lines
- Comments, ordering, and all other variables stay intact

---

## Testing DFE

### Dry Run Test

```bash
cd ~/alpha-sniper-v4.2/alpha-sniper
python test_dfe.py
```

**What it does:**
- Loads trade data
- Calculates metrics
- Shows proposed adjustments
- **Does NOT modify .env** (safe to run anytime)

**Example output:**
```
======================================================================
Testing Dynamic Filter Engine (DFE)
======================================================================

1. Checking for trade log...
   ✅ Found 45 closed trades

2. Calculating performance metrics...
   Trades/day (14d): 3.21
   Win rate (last 30): 56.7%
   Avg R (last 30): 0.721R

3. Current filter values:
   MIN_SCORE = 75
   MIN_24H_QUOTE_VOLUME = 30000.0
   MAX_SPREAD_PCT = 1.5
   PUMP_MAX_AGE_HOURS = 72

4. Proposed new filter values:
   MIN_SCORE = 75 → (+0.0)
   MIN_24H_QUOTE_VOLUME = 30000.0 → (+0.0)
   MAX_SPREAD_PCT = 1.5 → (+0.0)
   PUMP_MAX_AGE_HOURS = 72 → (+0.0)

✅ DFE logic test complete!
Note: No .env file was modified. This was just a dry run.
```

### Live Test (Development)

1. Set `DFE_ENABLED=true` in `.env`
2. Manually trigger at any time:
   ```python
   from utils.dynamic_filters import update_dynamic_filters
   from config import get_config
   from utils.logger import setup_logger

   cfg = get_config()
   logger = setup_logger()
   update_dynamic_filters(cfg, logger)
   ```

3. Check `.env` to see changes
4. Verify filters are within safe ranges

---

## Monitoring DFE

### What to Watch

**In logs (grep for `DFE`):**
```bash
tail -f logs/bot.log | grep DFE
```

**Key log markers:**
- `DFE | Performance metrics:` - Calculated values
- `DFE | Applying adjustment rules:` - Which rules triggered
- `DFE | New filters:` - Final values with deltas
- `DFE | ✅ Filters updated` - Success
- `DFE | Not enough trades` - Skipped (need more data)

### Inspect .env Changes

```bash
# See when filters were last modified
ls -l .env

# View current values
grep -E "MIN_SCORE|MIN_24H_QUOTE_VOLUME|MAX_SPREAD_PCT|PUMP_MAX_AGE_HOURS" .env
```

---

## Troubleshooting

### Issue: DFE never runs

**Check:**
1. `DFE_ENABLED=true` in `.env`?
2. Bot logs show "DFE enabled" at startup?
3. At least 10 closed trades in `logs/v4_trade_scores.csv`?

**Solution:**
- Enable DFE in `.env`
- Run more trades (manual or wait for signals)
- Check logs for DFE errors

### Issue: Filters not changing

**Possible reasons:**
1. Performance is in "Goldilocks zone" (3-12 trades/day, >56% win rate, >0.6R)
2. Filters already at min/max bounds (clamped)
3. Adjustments too small (rounded away)

**Solution:**
- This might be intentional! Check DFE logs to see if rules triggered
- If performance is good, no changes are ideal

### Issue: DFE adjustments seem wrong

**Example:** Win rate is high but filters tightened

**Explanation:**
- Multiple rules can apply
- If trades/day >12, frequency rule tightens regardless of win rate
- Rules are cumulative

**Solution:**
- Check all three metrics (trades/day, win rate, avg R)
- Review DFE log output to see which rules applied

### Issue: .env corruption

**Symptom:** .env has garbled data or missing lines

**Cause:** Rare file write error

**Solution:**
1. Restore from backup (if you have one)
2. Recreate from `.env.example`
3. Report as bug (DFE should preserve all lines)

---

## Advanced: Tuning DFE Itself

If you want to modify DFE's behavior, edit `utils/dynamic_filters.py`:

**Change adjustment percentages:**
```python
# Line ~165: Frequency adjustment
new['MIN_SCORE'] *= 0.90  # Change 0.90 to 0.85 for more aggressive loosening
```

**Change thresholds:**
```python
# Line ~161: Trade frequency threshold
if trades_per_day < 3:  # Change 3 to 5 to loosen earlier
```

**Change safe ranges:**
```python
# Line ~31: Filter ranges
FILTER_RANGES = {
    'MIN_SCORE': (68, 82),  # Expand to (65, 85) for wider range
    ...
}
```

**⚠️ Warning:** Modifying DFE logic can lead to unexpected behavior. Test thoroughly!

---

## FAQ

**Q: Can I disable DFE temporarily without editing .env?**

A: Yes, just comment out the line:
```bash
# DFE_ENABLED=true
```

**Q: Will DFE reset my custom filter values?**

A: On first run, DFE uses whatever values are in `.env`. After that, it adjusts them. If you want to reset, manually set values in `.env` and DFE will adjust from there.

**Q: How often does DFE run?**

A: Once per day at 00:05 UTC (scheduled via `schedule` library)

**Q: Can I trigger DFE manually?**

A: Yes! Use `test_dfe.py` for dry-run, or call `update_dynamic_filters()` directly for live adjustment.

**Q: What if I'm running 24/7 but DFE seems slow to adapt?**

A: DFE only runs daily. If you need faster adaptation, you could modify the schedule in `main.py` (e.g., every 12 hours). But daily is recommended to avoid over-fitting.

**Q: Does DFE work in both SIM and LIVE modes?**

A: Yes! DFE reads from `v4_trade_scores.csv` which logs trades from both modes. However, keep in mind that SIM and LIVE trades are mixed in the analysis.

**Q: Can I see what DFE would do without enabling it?**

A: Yes! Run `python test_dfe.py` for a dry-run simulation.

---

## Summary

✅ **DFE is fully implemented and production-ready**

**Key Points:**
- Fully optional (default: disabled)
- Runs daily at 00:05 UTC
- Adjusts 4 filters within safe ranges
- Based on 3 performance metrics
- Soft failures (never crashes bot)
- Preserves all other `.env` settings
- Comprehensive logging
- Test script included

**To Enable:**
1. Add `DFE_ENABLED=true` to `.env`
2. Run bot normally
3. DFE auto-tunes filters daily

**Your bot is now self-improving! 🚀**
