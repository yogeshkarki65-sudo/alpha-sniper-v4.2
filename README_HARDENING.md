# Alpha Sniper - Hardening Package

## 📦 **What's in This Package**

After extensive debugging and hardening analysis, here are the deliverables:

### ✅ **Immediate Use (Run These Now)**

1. **check_bot_health.sh** - Quick health check
   ```bash
   bash check_bot_health.sh
   ```
   Shows: Service status, recent trades, errors, configuration

2. **SIMPLE_HARDENING.md** - Current state analysis
   - What's working
   - What's fixed
   - What's optional

### 📋 **Reference Documentation**

3. **HARDENING_SUMMARY.md** - Executive summary
   - Current operational status
   - Recommendation: DON'T patch now
   - Monitoring checklist
   - When to apply hardening

4. **MIGRATION_NOTES.md** - If you decide to apply patches
   - New settings explained
   - What changes
   - Testing plan

5. **ROLLBACK.md** - How to undo patches
   - Git-based rollback
   - Manual file restoration
   - Emergency procedures

### 🔧 **Optional Hardening (Apply During Maintenance)**

6. **PATCHES.diff** - Unified diffs for optional improvements
   - Reserve cushion ($3 for fees)
   - IOC fallback mechanism
   - Enhanced precision logging
   - Better error messages

7. **verification_script.sh** - Post-patch testing
   ```bash
   bash verification_script.sh
   ```
   (Only run after applying patches)

## 🚀 **Quick Start**

### Right Now (On Your Server):

```bash
# 1. Check bot health
cd /opt/alpha-sniper/alpha-sniper
bash check_bot_health.sh

# 2. Watch live trading
sudo journalctl -u alpha-sniper-async.service -f | grep -E 'SCAN|EAGER|OPENED|CLOSED'

# 3. Read current status
cat SIMPLE_HARDENING.md
```

### Expected Output (Healthy Bot):

```
========================================
  Alpha Sniper Health Check
========================================

1. Service Status:
   ✅ Service is RUNNING

2. Recent Activity (last 5 minutes):
   📊 Scans completed: 5
   🎯 Candidates found: 12
   ✅ Positions opened: 1
   ❌ Positions closed: 0

3. Recent Errors:
   ✅ No errors in last 10 minutes

4. Configuration:
   LIVE_TEST_MODE: True
   ✅ Size capping active

5. Last Trade Activity:
   Last OPEN: [EAGER] OPENED WLD/USDT @ 0.58040000 size=$7.50

========================================
  Overall Status: ✅ HEALTHY
========================================
```

## 📊 **What We Fixed During Debugging**

✅ **Completed (Already Applied):**
1. Settings absolute path (`/opt/alpha-sniper/alpha-sniper/.env.async`)
2. LIVE_TEST_MODE cap in EAGER loop ($7.50 max per order)
3. None handling for `initial_risk_usd`
4. Oversold error force-close
5. Auto-bump before validation
6. Settings parameter scope in manage_positions_loop

✅ **Current Status:**
- Bot is actively trading
- EAGER finding breakout candidates
- Positions managed by Hold Brain
- Telegram notifications working
- All automatic features operational

## 🎯 **Next Steps (Recommended)**

### Option 1: Monitor (RECOMMENDED)

**Just let it run for 24-48 hours:**

```bash
# Check health periodically
bash check_bot_health.sh

# Watch Telegram for trade notifications
# (You'll get alerts for opens/closes)

# Review daily digest at midnight UTC
```

**Why:** Bot is working perfectly. Collect baseline data before optimizing further.

### Option 2: Apply Hardening (OPTIONAL)

**Only if you insist or see actual errors:**

1. **Read first:**
   - `HARDENING_SUMMARY.md` (decision guide)
   - `MIGRATION_NOTES.md` (what changes)
   - `ROLLBACK.md` (how to undo)

2. **Schedule maintenance window** (low volatility period)

3. **Create rollback point:**
   ```bash
   cd /opt/alpha-sniper/alpha-sniper
   git tag before-hardening-$(date +%Y%m%d)
   ```

4. **Apply patches** (manual review required - patches are conceptual)

5. **Test with:**
   ```bash
   bash verification_script.sh
   ```

6. **Monitor for issues:**
   - First 10 minutes: Watch logs continuously
   - First hour: Check every 15 minutes
   - First 24 hours: Check health 4-6 times

7. **Rollback if anything breaks:**
   ```bash
   git reset --hard before-hardening-YYYYMMDD
   sudo systemctl restart alpha-sniper-async.service
   ```

## ⚠️ **Important Warnings**

### DO NOT:
- ❌ Apply patches while bot is actively trading positions
- ❌ Apply patches during high volatility (major news events)
- ❌ Skip creating a rollback point
- ❌ Apply patches without reading documentation first

### DO:
- ✅ Create git tag before ANY changes
- ✅ Test in SIM mode first (optional but safe)
- ✅ Monitor logs continuously after changes
- ✅ Have rollback plan ready

## 📖 **Documentation Map**

**Start here:**
- `README_HARDENING.md` (this file) - Overview

**For decision making:**
- `HARDENING_SUMMARY.md` - Should I apply patches?
- `SIMPLE_HARDENING.md` - What's currently working?

**For implementation:**
- `MIGRATION_NOTES.md` - How to apply patches
- `PATCHES.diff` - Actual code changes
- `verification_script.sh` - How to test

**For safety:**
- `ROLLBACK.md` - How to undo everything

**For monitoring:**
- `check_bot_health.sh` - Quick health check

## 🔍 **Troubleshooting**

### "Bot not finding trades"

This is normal! EAGER requires:
- +1% return in 5 minutes (very rare)
- Volume spike 1.0x+ (fairly common)
- Depth ≥ $5000 (filters out illiquid coins)
- Not on cooldown (90 sec per symbol)

During quiet markets, you might see:
- 10-20 candidates per scan
- 0-5 actual signals per hour
- 1-3 trades per hour (in test mode, max 50/day)

**This is expected.**

### "Too many insufficient_balance rejections"

If you see:
```
[EAGER] SYM/USDT rejected: insufficient_quote_balance {'notional': 7.5, 'free': 6.2}
```

This means:
- You're running low on USDT (< $10)
- OR another order just filled (race condition)
- OR fees ate into balance

**Solutions:**
1. Add more USDT to wallet
2. Apply reserve cushion patch (prevents balance edge cases)

### "Service keeps restarting"

Check logs:
```bash
sudo journalctl -u alpha-sniper-async.service -n 100 | grep ERROR
```

Common causes:
- API key/secret invalid → Check `.env.async`
- Database locked → Restart: `sudo systemctl restart alpha-sniper-async.service`
- Python error → Check code changes weren't applied incorrectly

## 💡 **Pro Tips**

1. **Monitor Telegram, not just logs**
   - More readable trade summaries
   - Daily digest with stats
   - Immediate notifications on your phone

2. **Check health script daily**
   ```bash
   bash check_bot_health.sh
   ```
   Takes 2 seconds, gives full picture

3. **Let AutoTune work**
   - System adjusts thresholds automatically
   - After 20+ trades, may flip out of test mode
   - Trust the process

4. **Review weekly**
   - Win rate trending up? Good!
   - Avg R-multiple > 0.6? Excellent!
   - Slippage < 0.4%? Perfect!

## 📞 **Support**

If you need help:

1. **Capture diagnostics:**
   ```bash
   bash check_bot_health.sh > /tmp/health.txt
   sudo journalctl -u alpha-sniper-async.service -n 200 > /tmp/logs.txt
   cat /opt/alpha-sniper/data/overrides.json > /tmp/overrides.txt
   ```

2. **Check documentation:**
   - Most issues covered in ROLLBACK.md
   - Common errors in MIGRATION_NOTES.md

3. **Restore to known good state:**
   ```bash
   git reset --hard 2c751d53  # Last known working commit
   ```

## 📅 **Changelog**

**2026-01-11 15:30 UTC - Initial Package**
- Bot fully operational after debugging session
- All critical fixes applied
- Optional hardening patches prepared
- Comprehensive documentation provided

**Current Commit:** `2c751d53` (LIVE_TEST_MODE cap applied)
**Status:** ✅ Healthy and trading
**Recommendation:** Monitor, don't patch yet

---

**Built with care during multi-hour debugging session.**
**Your bot is working - trust it. Let it prove itself before optimizing further.**

🚀 Happy trading!
