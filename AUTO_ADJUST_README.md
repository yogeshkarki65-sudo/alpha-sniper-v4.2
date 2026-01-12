# Auto-Adjustment Features

## Overview

Two new automatic adjustment features have been added to improve bot performance and adaptability:

### 1. **Win Rate Auto-Tightening**
If your bot's win rate stays below 40% after 100+ trades, the system automatically tightens signal requirements to become more selective.

### 2. **Quiet Market Auto-Loosening**
If no trades are opened for 6+ hours (quiet market), the system automatically loosens requirements to increase trade opportunities.

---

## How It Works

### Win Rate Auto-Tightening

**Trigger Conditions:**
- Total trades ≥ 100
- Win rate < 40%
- At least 1 hour since last adjustment

**Actions Taken:**
- Increase `EARLY_RET_5M_MIN` by 0.002 (0.2%)
- Increase `EARLY_VOL_SPIKE_MIN` by 0.2

**Purpose:**
Filters out poor quality signals when the strategy is underperforming. Higher thresholds mean only stronger breakouts are traded.

**Log Message:**
```
[WINRATE_ADJUST] Low winrate=35.2% (35/100) -> Tightening: RET5M=0.0120, VSP=1.50
```

---

### Quiet Market Auto-Loosening

**Trigger Conditions:**
- No trades opened for 6+ hours
- At least 2 hours since last adjustment

**Actions Taken:**
- Decrease `EARLY_RET_5M_MIN` by 0.001 (0.1%)
- Decrease `EAGER_MIN_DEPTH_USD` by $1000 (min $3000)

**Purpose:**
Adapts to quiet market conditions by accepting slightly weaker signals when opportunities are scarce.

**Log Message:**
```
[QUIET_MARKET] No trades for 8.3h -> Loosening: RET5M=0.0070, MIN_DEPTH=$4000
```

---

## Deployment

### One-Shot Deployment (Recommended)

```bash
cd /opt/alpha-sniper/alpha-sniper
bash deploy_auto_adjust.sh
```

This script:
1. Stops the service
2. Pulls latest changes from GitHub
3. Verifies database connectivity
4. Restarts the service
5. Confirms successful startup

### Manual Deployment

```bash
cd /opt/alpha-sniper/alpha-sniper

# Stop service
sudo systemctl stop alpha-sniper-async.service

# Pull changes
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Start service
sudo systemctl start alpha-sniper-async.service
```

---

## Monitoring

### Watch for Adjustments

```bash
# Monitor all AutoTune adjustments
sudo journalctl -u alpha-sniper-async.service -f | grep -E 'AUTOTUNE|WINRATE|QUIET_MARKET'
```

### Check Current Settings

```bash
cat /opt/alpha-sniper/data/overrides.json | jq '.EARLY_RET_5M_MIN, .EARLY_VOL_SPIKE_MIN, .EAGER_MIN_DEPTH_USD'
```

### Review Performance

```bash
cd /opt/alpha-sniper/alpha-sniper
bash check_performance.sh
```

This shows:
- Total trades
- Win rate
- Average R-multiple
- Recent trade history

---

## Understanding the Adjustments

### When Win Rate is Low (< 40%)

**Current State:**
```
Total Trades: 150
Win Rate: 35.3% (53 wins / 97 losses)
EARLY_RET_5M_MIN: 0.008 (0.8%)
```

**After Auto-Tightening:**
```
[WINRATE_ADJUST] Low winrate=35.3% -> Tightening: RET5M=0.0100, VSP=1.50
```

**Effect:**
- Only breakouts with ≥1.0% momentum in 5min are considered (was 0.8%)
- Volume spike must be ≥1.5x average (was 1.3x)
- Fewer but higher quality signals

**Expected Outcome:**
- Trade frequency decreases
- Win rate improves over next 50-100 trades
- Better R-multiples on winning trades

---

### When Market is Quiet (No Trades 6+ Hours)

**Current State:**
```
Last Trade: 8 hours ago
EARLY_RET_5M_MIN: 0.008 (0.8%)
EAGER_MIN_DEPTH_USD: $5000
```

**After Auto-Loosening:**
```
[QUIET_MARKET] No trades for 8.0h -> Loosening: RET5M=0.0070, MIN_DEPTH=$4000
```

**Effect:**
- Accept breakouts with ≥0.7% momentum (was 0.8%)
- Accept coins with ≥$4000 depth (was $5000)
- More opportunities in low-volatility periods

**Expected Outcome:**
- Trade frequency increases
- May find opportunities in smaller/quieter coins
- Risk is similar (still capped by LIVE_TEST_MODE)

---

## Interaction with Existing AutoTune

These new features **complement** the existing AutoTune Pro features:

| Feature | Trigger | Adjustment | Purpose |
|---------|---------|------------|---------|
| **Signal Flow Tuning** | Signals/hr too high/low | RET5M, VSP, MIN_SCORE | Match target signal rate |
| **Universe Loosening** | Signals/hr < 0.5 at floor | UNIVERSE_SIZE, MIN_QUOTE_VOLUME | Expand opportunity set |
| **Sizing Autopilot** | Recent R-multiples | RISK_PER_TRADE | Scale position sizing |
| **Live Test Flip** | Guardrails met | LIVE_TEST_MODE → False | Graduate from test mode |
| **Win Rate Tightening** ⭐ | Win rate < 40% after 100+ | RET5M, VSP | Filter poor signals |
| **Quiet Market Loosening** ⭐ | No trades for 6h | RET5M, MIN_DEPTH | Adapt to quiet markets |

All features work together to optimize bot performance automatically.

---

## Safety Features

### Cooldowns
- **Win rate check:** Every 50 scans (~50 minutes)
- **Win rate adjustment:** Minimum 1 hour between adjustments
- **Quiet market check:** Every scan
- **Quiet market adjustment:** Minimum 2 hours between adjustments

### Boundaries
All adjustments respect the bounds defined in settings:
- `AUTOTUNE_RET5M_BOUNDS` (default: 0.004 to 0.030)
- `AUTOTUNE_VSPIKE_BOUNDS` (default: 0.8 to 3.0)
- `EAGER_MIN_DEPTH_USD` (minimum: $3000)

### Database Safety
- Read-only queries (no writes from AutoTune)
- Error handling with fallback (continues on DB error)
- Thread-safe connection (`check_same_thread=False`)

---

## Server Cleanup

Remove unnecessary files and old databases:

```bash
cd /opt/alpha-sniper/alpha-sniper
bash cleanup_server.sh
```

This interactive script:
- Archives old `alpha.db` (no longer used)
- Removes hardening docs (already applied)
- Removes duplicate scripts
- Creates backup before deletion
- Confirms each action

**Safe to run:** All files are archived, not deleted.

---

## Troubleshooting

### "Database locked" Error

```bash
# Check for other processes using DB
lsof /opt/alpha-sniper/data/alpha_async.db

# Restart service
sudo systemctl restart alpha-sniper-async.service
```

### Adjustments Not Triggering

**Win Rate Adjustment:**
```bash
# Check trade count
sqlite3 /opt/alpha-sniper/data/alpha_async.db "SELECT COUNT(*) FROM trades;"

# Must be ≥ 100 trades
```

**Quiet Market Adjustment:**
```bash
# Check recent logs for OPENED
sudo journalctl -u alpha-sniper-async.service --since "6 hours ago" | grep "OPENED"

# If no OPENED messages, adjustment should trigger after 6h
```

### Verify Feature is Active

```bash
# Check if AutoTune is receiving database connection
sudo journalctl -u alpha-sniper-async.service -n 100 | grep "AutoTune Pro initialized"

# Should see: AutoTune Pro initialized (enabled: True)
```

---

## Example Scenarios

### Scenario 1: Poor Early Performance

**Day 1:**
```
Trades: 120
Win Rate: 28%
Avg R: -0.15R
```

**System Response:**
```
[WINRATE_ADJUST] Low winrate=28.0% -> Tightening: RET5M=0.0100, VSP=1.50
```

**Day 2-3:**
```
Trades: 145 (+25)
Win Rate: 36%
Avg R: -0.05R
```

**System Response:**
```
[WINRATE_ADJUST] Low winrate=36.0% -> Tightening: RET5M=0.0120, VSP=1.70
```

**Day 4-7:**
```
Trades: 180 (+35)
Win Rate: 42%
Avg R: +0.08R
```

**Result:** System stabilized above 40% threshold, no further tightening needed.

---

### Scenario 2: Quiet Market Period

**Normal Market:**
```
08:00 - Trade opened: BTC/USDT
09:00 - Trade opened: ETH/USDT
10:00 - Trade opened: SOL/USDT
```

**Quiet Period Begins:**
```
11:00 - No signals
12:00 - No signals
13:00 - Candidates found but no fills
14:00 - Candidates found but no fills
15:00 - No signals
16:00 - No signals
17:00 - 6 hours since last trade
```

**System Response:**
```
[QUIET_MARKET] No trades for 6.0h -> Loosening: RET5M=0.0070, MIN_DEPTH=$4000
```

**Result:**
```
17:30 - Trade opened: MATIC/USDT (benefited from looser requirements)
```

---

## Configuration Reference

### Relevant Settings

From `/opt/alpha-sniper/alpha-sniper/.env.async`:

```env
# AutoTune Bounds (respected by all adjustments)
ALPHA_AUTOTUNE_RET5M_BOUNDS=0.004,0.030
ALPHA_AUTOTUNE_VSPIKE_BOUNDS=0.8,3.0

# EAGER Settings (adjusted by auto-features)
ALPHA_EARLY_RET_5M_MIN=0.008
ALPHA_EARLY_VOL_SPIKE_MIN=1.1
ALPHA_EAGER_MIN_DEPTH_USD=5000
```

### Current Overrides

Check active values:
```bash
cat /opt/alpha-sniper/data/overrides.json
```

### Resetting to Defaults

If needed, clear specific overrides:
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python scripts/overrides_cli.py delete --key EARLY_RET_5M_MIN
python scripts/overrides_cli.py delete --key EARLY_VOL_SPIKE_MIN
sudo systemctl restart alpha-sniper-async.service
```

---

## FAQ

**Q: Will this change my position sizing?**
A: No, these features only adjust signal requirements (when to enter). Position sizing is controlled by `RISK_PER_TRADE` and `LIVE_TEST_MODE`.

**Q: Can I disable these features?**
A: They're part of AutoTune Pro. To disable, set `ALPHA_AUTOTUNE_ENABLE=False` in `.env.async`.

**Q: What if win rate drops below 40% after tightening?**
A: The system will tighten further (every hour max) until hitting the upper bound or win rate improves.

**Q: Will loosening for quiet markets hurt my win rate?**
A: Slightly looser requirements may reduce win rate by 1-3%, but this is acceptable to maintain trade flow. The system will tighten again if performance degrades.

**Q: How do I know if adjustments are working?**
A: Monitor logs and check performance after 50+ trades following each adjustment. Win rate should trend toward 40%+ over time.

---

## Support

For issues or questions:

1. **Check logs:**
   ```bash
   sudo journalctl -u alpha-sniper-async.service -n 200
   ```

2. **Check bot health:**
   ```bash
   bash check_bot_health.sh
   ```

3. **Check performance:**
   ```bash
   bash check_performance.sh
   ```

4. **Review recent adjustments:**
   ```bash
   sudo journalctl -u alpha-sniper-async.service | grep -E 'AUTOTUNE|WINRATE|QUIET_MARKET' | tail -20
   ```

---

## Changelog

**2026-01-12 - v4.2.5**
- Added win rate auto-tightening (< 40% after 100+ trades)
- Added quiet market auto-loosening (no trades for 6+ hours)
- Added database connection to AutoTune Pro
- Added on_trade_opened() tracking hook
- Integrated with existing AutoTune Pro flow
- Created deployment and cleanup scripts

---

**Status:** ✅ Ready for production deployment

**Recommendation:** Deploy during low-volatility period, monitor for first 24 hours to confirm adjustments trigger as expected.
