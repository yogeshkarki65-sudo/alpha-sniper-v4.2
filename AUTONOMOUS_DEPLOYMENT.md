# Alpha Sniper v4.2 - Autonomous Trading System Deployment

## 🎯 System Overview

This deployment makes Alpha Sniper **fully autonomous** with:
- ✅ **Zero manual intervention** - system self-optimizes every 6 hours
- ✅ **Complete telemetry** - every scan, filter, and trade decision is logged
- ✅ **Unified vspike** - single source of truth prevents drift
- ✅ **Safe bounds** - all adjustments within proven ranges
- ✅ **Quality-first** - all 7 entry filters enabled and enforced

---

## 📦 What's Included

### 1. Enhanced Telemetry (`app_async.py`)
- `effective_vspike_min(settings)` - single source of truth for vspike
- `[EAGER_THRESHOLDS]` - per-scan configuration banner
- `[EAGER_FILTER_SUMMARY]` - per-scan rejection counts
- `[EAGER_PLACE/FILLED/CANCEL]` - IOC order lifecycle tracking
- `[EAGER] SKIP_AFTER_PASS` - post-filter skip reasons

### 2. Auto-Sync CLI (`scripts/overrides_cli.py`)
- Setting either `EARLY_VOL_SPIKE_MIN` or `EAGER_VSPIKE_MIN` auto-syncs both

### 3. 6-Hour Auto-Tuner (`scripts/alpha_autotune.sh`)
- Queries SQLite for last 6h performance
- Adjusts parameters based on winrate and trade count
- Ensures critical filters always enabled
- Safe bounds prevent runaway adjustments

### 4. Quick Diagnostics (`scripts/diag_last_10m.sh`)
- Fast 10-minute activity snapshot

---

## 🚀 Deployment Steps

### Step 1: Deploy to Production Server

```bash
# SSH to your production server
ssh ubuntu@your-server-ip

# Navigate to repo
cd /opt/alpha-sniper/alpha-sniper

# Fetch latest changes
git fetch origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
git reset --hard origin/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Verify scripts are executable
chmod +x scripts/alpha_autotune.sh scripts/diag_last_10m.sh

# Restart service to apply telemetry improvements
sudo systemctl restart alpha-sniper-async.service
```

### Step 2: Install Auto-Tuner Cron Job

```bash
# Add cron job to run every 6 hours
(crontab -l 2>/dev/null; echo "0 */6 * * * /opt/alpha-sniper/scripts/alpha_autotune.sh >> /opt/alpha-sniper/logs/autotune.log 2>&1") | crontab -

# Verify cron is installed
crontab -l | grep alpha_autotune
```

**Expected output:**
```
0 */6 * * * /opt/alpha-sniper/scripts/alpha_autotune.sh >> /opt/alpha-sniper/logs/autotune.log 2>&1
```

### Step 3: Run Initial Auto-Tune (Optional)

```bash
# Run auto-tuner manually to ensure critical filters are enabled
/opt/alpha-sniper/scripts/alpha_autotune.sh

# Expected output:
# alpha_autotune: n=15 wr=18.5 avg_pnl=0.020 ret=0.020 vsp=1.90 risk=0.0020 action=TUNE:TIGHTEN
```

### Step 4: Configure Telegram Notifications (Optional)

**Setup Telegram Bot:**

1. **Create bot via @BotFather:**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Save your **bot token** (e.g., `110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw`)

2. **Get your chat ID:**
   - Send `/start` to your new bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Look for `"chat":{"id":123456789}` and save the **chat ID**

3. **Add credentials to environment:**
   ```bash
   # Edit .env file
   nano /opt/alpha-sniper/.env

   # Add these lines:
   TELEGRAM_BOT_TOKEN="your_bot_token_here"
   TELEGRAM_CHAT_ID="your_chat_id_here"
   ```

4. **Test notifications:**
   ```bash
   cd /opt/alpha-sniper && source venv/bin/activate
   python scripts/telegram_notify.py --severity success "✅ Bot configured and ready!"
   deactivate
   ```

**What gets notified:**
- ⚙️ Auto-tune parameter adjustments (every 6 hours)
- ✅ Optimal performance status
- 🔴 Low winrate warnings (tightening filters)
- 🟢 High winrate celebrations (loosening filters)
- 🚨 Critical alerts (parameters at bounds, low trade volume)

**Silence notifications:**
Simply remove or comment out the `TELEGRAM_BOT_TOKEN` from `.env` - notifications will fail silently without breaking automation.

**Example notifications:**

```
⚙️ Alpha Sniper

🟢 AUTO-TUNE: Loosening filters
📊 Performance (6h): 28 trades, 35.7% WR, P&L $0.0023
⚙️ New settings: ret5m=0.018 vsp=1.80 risk=0.0020
📈 Action: TUNE:LOOSEN_GENTLE

2026-01-17 14:32:15
```

```
⚙️ Alpha Sniper

✅ AUTO-TUNE: System performing optimally
📊 Performance (6h): 42 trades, 38.5% WR, P&L $0.0031
⚙️ Current settings: ret5m=0.018 vsp=1.80 risk=0.0020
🎯 Status: No changes needed

2026-01-17 20:05:42
```

```
⚙️ Alpha Sniper

🚨 AUTO-TUNE: Low trade volume (vspike at minimum)
📊 Performance (6h): 3 trades, 33.3% WR, P&L $0.0005
⚠️ Current settings: ret5m=0.019 vsp=1.60 (MIN) risk=0.0020
🔍 Status: Check market conditions or filter rejections

2026-01-17 02:18:33
```

---

## 🔍 Verification Tests

### Test 1: Thresholds Banner (Every Scan)
```bash
sudo journalctl -u alpha-sniper-async.service -f -o cat | grep EAGER_THRESHOLDS
```

**Expected:**
```
[EAGER_THRESHOLDS] ret5m≥0.0190 vsp≥1.80 score≥6 depth≥$8000 eps=0.0012
```

### Test 2: Filter Summary (Every Scan)
```bash
sudo journalctl -u alpha-sniper-async.service -f -o cat | grep EAGER_FILTER_SUMMARY
```

**Expected:**
```
[EAGER_FILTER_SUMMARY] ACCEL=2 DEPTH=1 EMA_TREND=8 RET5M=3 VSPIKE=5
```

### Test 3: Placement Telemetry
```bash
sudo journalctl -u alpha-sniper-async.service --since "10 min ago" -o cat \
| grep -E "EAGER_PLACE|EAGER_FILLED|EAGER_CANCEL"
```

**Expected when trade occurs:**
```
[EAGER_PLACE] XYZ/USDT notional=$15.23 qty=12.5 eps=0.0012 price=1.2345 min_cost=$5.00 free=$28.45
[EAGER_FILLED] XYZ/USDT qty=12.5 avg=1.2346
```

### Test 4: Vspike Sync
```bash
cd /opt/alpha-sniper && source venv/bin/activate

# Set one vspike key
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 1.87

# Verify both keys synced
python scripts/overrides_cli.py get --key EAGER_VSPIKE_MIN
python scripts/overrides_cli.py get --key EARLY_VOL_SPIKE_MIN

deactivate
```

**Expected:**
```
SYNC: Set both EARLY_VOL_SPIKE_MIN and EAGER_VSPIKE_MIN to 1.87 for consistency.
{"EAGER_VSPIKE_MIN": 1.87}
{"EARLY_VOL_SPIKE_MIN": 1.87}
```

### Test 5: Quick Diagnostics
```bash
/opt/alpha-sniper/scripts/diag_last_10m.sh
```

**Expected:**
```
Last thresholds: [EAGER_THRESHOLDS] ret5m≥0.0190 vsp≥1.80 score≥6 depth≥$8000 eps=0.0012
Last filter summary: [EAGER_FILTER_SUMMARY] ACCEL=2 DEPTH=1 EMA_TREND=8 RET5M=3 VSPIKE=5

Summaries:
[EAGER_SUMMARY] candidates=15 attempted=1 opened=1 free_usdt=28.45

Actions:
[EAGER_PLACE] XYZ/USDT notional=$15.23 qty=12.5 eps=0.0012 price=1.2345 min_cost=$5.00 free=$28.45
[EAGER_FILLED] XYZ/USDT qty=12.5 avg=1.2346
```

---

## ⚙️ Auto-Tuner Behavior

### Enhanced Decision Logic

The auto-tuner runs every 6 hours and makes intelligent decisions based on trade count, winrate, and profitability:

#### Trade Volume Thresholds
| Trades | Winrate | Avg P&L | Action | Changes |
|--------|---------|---------|--------|---------|
| < 10 | Any | Any | Seed flow | Lower vspike by 0.10 (min 1.60) |
| 10-19 | < 20% | Any | Tighten + seed | +0.001 ret5m |
| 10-19 | ≥ 20% | Any | Seed flow | Lower vspike by 0.10 |

#### Quality Optimization (≥20 trades)
| Winrate | Avg P&L | Trade Count | Action | Changes |
|---------|---------|-------------|--------|---------|
| < 25% | Any | ≥ 20 | Tighten aggressively | +0.001 ret5m, +0.10 vspike |
| 25-30% | Positive | ≥ 40 | Loosen gently | -0.001 ret5m |
| 25-30% | Positive | 20-39 | Hold | Monitor profitability |
| 25-30% | Negative | ≥ 20 | Tighten gently | +0.001 ret5m |
| 30-35% | Positive | ≥ 20 | Loosen gently | -0.001 ret5m |
| 30-35% | Negative | ≥ 20 | Hold | Check R-ratio |
| 35-40% | Positive | ≥ 20 | Hold (optimal) | No changes |
| 35-40% | Negative | ≥ 20 | Tighten gently | +0.001 ret5m (R-ratio fix) |
| ≥ 40% | Any | ≥ 20 | Loosen | -0.001 ret5m |

#### Risk Sizing (if SIZING_AUTOPILOT_ENABLE=true)
| Trades | Winrate | Action | Changes |
|--------|---------|--------|---------|
| ≥ 10 | ≥ 35% | Scale risk up | +0.0002 risk (max 0.30%) |
| ≥ 10 | ≤ 20% | Scale risk down | -0.0002 risk (min 0.10%) |

#### Bounded Parameter Recovery
- When ret5m hits max (3.5%) and WR still < 25%, reduces risk instead of further tightening
- When vspike hits min (1.60) and trades < 10, holds (cannot loosen further)
- Automatic service restart when parameters change (requires systemd)

### Safe Bounds

All adjustments stay within proven ranges:

| Parameter | Min | Max | Current Default |
|-----------|-----|-----|-----------------|
| EARLY_RET_5M_MIN | 1.4% | 3.5% | 1.9% |
| EARLY_VOL_SPIKE_MIN | 1.6x | 4.0x | 1.8x |
| RISK_PER_TRADE | 0.10% | 0.30% | 0.20% |

### Critical Filters (Always Enabled)

The auto-tuner ensures these filters are ALWAYS enabled:
- ✅ ENTRY_TREND_EMA_CHECK_ENABLE
- ✅ ENTRY_ACCEL_ENABLE
- ✅ ENTRY_WICK_FILTER_ENABLE
- ✅ BTC_GUARD_ENABLE

### AutoTune Settings (Always Set)

- AUTOTUNE_MIN_DWELL_MIN = 60 (prevent oscillation)
- AUTOTUNE_FLOW_ENABLE = false (disable flow-based loosening)
- WINRATE_ADJUST_ENABLE = true (enable quality-based tightening)

---

## 📊 Monitoring Commands

### Live Tail (All EAGER Events)
```bash
sudo journalctl -u alpha-sniper-async.service -f -o cat | grep EAGER
```

### Last Hour Summary
```bash
sudo journalctl -u alpha-sniper-async.service --since "1 hour ago" -o cat \
| awk '
/EAGER_SUMMARY/{
  for(i=1;i<=NF;i++){
    if($i~/candidates=/){split($i,a,"=");c+=a[2]}
    if($i~/attempted=/){split($i,a,"=");at+=a[2]}
    if($i~/opened=/){split($i,a,"=");o+=a[2]}
  }
}
END{
  printf "1h: candidates=%d attempted=%d opened=%d | hit=%.1f%%\n",
    c+0, at+0, o+0, (at?100*o/at:0)
}'
```

### Auto-Tuner Log
```bash
tail -f /opt/alpha-sniper/logs/autotune.log
```

**Enhanced log format includes avg P&L:**
```
alpha_autotune: n=25 wr=32.5 avg_pnl=0.0018 ret=0.019 vsp=1.80 risk=0.0020 action=TUNE:LOOSEN_GENTLE
alpha_autotune: n=15 wr=28.0 avg_pnl=-0.0005 ret=0.020 vsp=1.80 risk=0.0020 action=TUNE:TIGHTEN_GENTLE
alpha_autotune: n=42 wr=38.5 avg_pnl=0.0025 ret=0.018 vsp=1.80 risk=0.0020 action=HOLD:WR_35-40_OPTIMAL
```

**Action codes:**
- `TUNE:TIGHTEN` - Aggressive tightening (WR < 25%)
- `TUNE:TIGHTEN_GENTLE` - Slight tightening (WR 25-40%, not profitable)
- `TUNE:LOOSEN` - Standard loosening (WR ≥ 40%)
- `TUNE:LOOSEN_GENTLE` - Slight loosening (WR 25-35%, profitable)
- `TUNE:SEED_FLOW` - Lowering vspike to increase trade volume
- `HOLD:*` - No parameter changes, monitoring specific scenario
- `[SERVICE_RESTARTED]` - Bot restarted to apply new parameters

### Filter Breakdown (Last 10 Minutes)
```bash
sudo journalctl -u alpha-sniper-async.service --since "10 min ago" -o cat \
| grep EAGER_FILTERS | awk -F'REJECT=' '{print $2}' | awk '{print $1}' \
| sort | uniq -c | sort -rn
```

---

## 🎯 Expected Behavior

### First 48 Hours (Learning Phase)
- **Trade Frequency:** 5-15 per day (quality over quantity)
- **Win Rate Target:** 25-35% (up from historical 14%)
- **Auto-Tuner:** Will tighten if WR < 25%, seed flow if < 20 trades/6h

### Week 1-2 (Stabilization)
- **Trade Frequency:** 10-20 per day
- **Win Rate Target:** 30-40%
- **Auto-Tuner:** Should mostly HOLD or make small adjustments

### Month 1+ (Optimization)
- **Trade Frequency:** 15-30 per day
- **Win Rate Target:** 40-55%
- **Auto-Tuner:** Fine-tuning within stable ranges

---

## 🚨 Troubleshooting

### No Trades for 1+ Hours

**Check 1: Thresholds too strict?**
```bash
sudo journalctl -u alpha-sniper-async.service --since "10 min ago" -o cat \
| grep EAGER_THRESHOLDS | tail -1
```
If `ret5m≥0.025` or `vsp≥3.0`, manually loosen:
```bash
cd /opt/alpha-sniper && source venv/bin/activate
python scripts/overrides_cli.py set --key EARLY_RET_5M_MIN --value 0.018
python scripts/overrides_cli.py set --key EARLY_VOL_SPIKE_MIN --value 1.8
deactivate
sudo systemctl restart alpha-sniper-async.service
```

**Check 2: Which filter is blocking most?**
```bash
sudo journalctl -u alpha-sniper-async.service --since "30 min ago" -o cat \
| grep EAGER_FILTER_SUMMARY | tail -5
```

**Check 3: Candidates passing but not attempting?**
```bash
sudo journalctl -u alpha-sniper-async.service --since "10 min ago" -o cat \
| grep -E "SKIP_AFTER_PASS|eager_candidates="
```

### Auto-Tuner Not Running

**Check cron:**
```bash
crontab -l | grep alpha_autotune
```

**Check last run:**
```bash
cat /opt/alpha-sniper/logs/autotune.log | tail -20
```

**Manually trigger:**
```bash
/opt/alpha-sniper/scripts/alpha_autotune.sh
```

### Filter Summary Shows "none"

This is normal if no candidates reached the filter stage (pre-filtered by vspike/ret5m/score).

---

## 🔒 Safety Features

1. **Bounded Adjustments:** All parameters stay within safe ranges
2. **Dwell Time:** Minimum 60 minutes between autotune adjustments
3. **Filter Enforcement:** Critical quality filters always enabled
4. **Wallet Reserve:** $5 reserve buffer prevents over-sizing
5. **Gradual Changes:** Small steps (0.001 ret, 0.10 vsp, 0.0002 risk)
6. **Vspike Sync:** Single source of truth prevents drift
7. **Trade Count Gates:** Requires minimum data before making decisions

---

## 📈 Success Metrics

Monitor these metrics weekly:

| Metric | Baseline (Pre-Fix) | Week 1 Target | Week 4 Target |
|--------|-------------------|---------------|---------------|
| Win Rate | 14% | 25-30% | 35-45% |
| Trades/Day | 40-60 | 10-20 | 15-30 |
| Avg Winner | $0.02 | $0.03 | $0.04 |
| Avg Loser | $0.027 | $0.025 | $0.025 |
| R-Multiple | 0.74 | 1.2 | 1.6 |
| Net P&L | -$44 (2,168 trades) | Breakeven | Profitable |

---

## 🎓 Understanding the Logs

### EAGER_THRESHOLDS
```
[EAGER_THRESHOLDS] ret5m≥0.0190 vsp≥1.80 score≥6 depth≥$8000 eps=0.0012
```
- `ret5m≥0.0190`: Minimum 5-minute return (1.9%)
- `vsp≥1.80`: Minimum volume spike (1.8x average)
- `score≥6`: Minimum quality score
- `depth≥$8000`: Minimum orderbook depth
- `eps=0.0012`: Entry epsilon above breakout (0.12%)

### EAGER_FILTER_SUMMARY
```
[EAGER_FILTER_SUMMARY] ACCEL=2 DEPTH=1 EMA_TREND=8 RET5M=3 VSPIKE=5
```
- Each number = how many symbols rejected by that filter this scan
- High counts normal - filters doing their job
- If one filter dominates (>80% rejections), may need adjustment

### EAGER_PLACE/FILLED/CANCEL
```
[EAGER_PLACE] XYZ/USDT notional=$15.23 qty=12.5 eps=0.0012 price=1.2345 min_cost=$5.00 free=$28.45
[EAGER_FILLED] XYZ/USDT qty=12.5 avg=1.2346
```
- `PLACE`: IOC order sent to exchange
- `FILLED`: Order executed (qty may differ from requested)
- `CANCEL`: Order rejected or not filled (IOC timeout)

---

## 🤝 Support

If issues persist after 72 hours:
1. Collect diagnostics: `./scripts/diag_last_10m.sh > diag.txt`
2. Share autotune log: `cat /opt/alpha-sniper/logs/autotune.log | tail -50`
3. Share recent performance: `sqlite3 /opt/alpha-sniper/data/alpha_async.db "SELECT COUNT(*), ROUND(100.0*SUM(pnl_usd>0)/COUNT(*),1) as wr FROM trades WHERE closed_at > strftime('%s','now','-24 hours')"`

---

**System is now fully autonomous. No manual intervention required.**
