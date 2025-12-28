# Alpha Sniper V4.2 - Deployment Guide
## Regime-Based Thresholds + Telegram Fixes

### What Changed

**Commit e6613ae - Regime-Based Pump Thresholds:**
- Pump engine now adapts filter strictness based on market regime
- All thresholds configurable via env (no more hard-coded values)
- Supports per-regime overrides: `PUMP_STRONG_BULL_MIN_SCORE`, `PUMP_SIDEWAYS_MIN_RVOL`, etc.
- New listing bypass properly implemented with relaxed thresholds
- Fixed "after_core=0" issue - signals will now generate

**Commit 207d5ff - Telegram Error Logging:**
- Robust error logging with HTTP status codes
- Test message sent on startup to verify Telegram config
- All failures logged with ❌ emoji and full error details
- No more silent failures

### Deployment Steps

#### 1. SSH to AWS Server
```bash
ssh alpha-sniper@your-aws-server-ip
```

#### 2. Backup Current Config
```bash
sudo cp /etc/alpha-sniper/alpha-sniper-live.env /etc/alpha-sniper/alpha-sniper-live.env.backup.$(date +%Y%m%d_%H%M%S)
```

#### 3. Replace Env File
Replace `/etc/alpha-sniper/alpha-sniper-live.env` with the new file provided below.

**IMPORTANT:** Make sure to preserve your actual API keys and Telegram token!

#### 4. Pull Latest Code
```bash
cd /opt/alpha-sniper
sudo git fetch origin
sudo git checkout claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
sudo git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
```

#### 5. Verify Changes
```bash
# Check that regime threshold code is present
sudo grep -n "get_pump_thresholds" /opt/alpha-sniper/alpha-sniper/config.py

# Check Telegram test message code
sudo grep -n "send_test_message" /opt/alpha-sniper/alpha-sniper/utils/telegram.py
```

#### 6. Set Permissions
```bash
sudo chown -R alpha-sniper:alpha-sniper /opt/alpha-sniper
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
```

#### 7. Restart Service
```bash
sudo systemctl restart alpha-sniper-live.service
```

#### 8. Monitor Logs
```bash
# Watch for test message and threshold logging
sudo journalctl -u alpha-sniper-live.service -f --since "1 minute ago"
```

### What to Look For in Logs

**Immediate (within 10 seconds):**
```
[TELEGRAM] Test message sent successfully - Telegram is working!
```
→ You should receive "🧪 Telegram Test" message on Telegram

**First Scan (within 60 seconds):**
```
[PUMP_DEBUG] Active thresholds (regime=SIDEWAYS): min_vol=150000, min_score=30, min_rvol=2.0, min_return=0.05%, max_return=15.00%, min_momentum=3.0, new_listing_min_rvol=0.8, new_listing_min_score=8, new_listing_min_momentum=0.5
```

**Signal Generation:**
```
[PUMP_DEBUG] Scan Summary: raw=1247, after_data=982, after_volume=156, after_spread=142, after_score=47, after_core=12, final_signals=3
```
→ **after_core > 0** means signals are being generated!

**Telegram Alert Success:**
```
[TELEGRAM] ✅ Startup sent successfully
[TELEGRAM] ✅ Regime Change (SIDEWAYS→STRONG_BULL) sent successfully
[TELEGRAM] ✅ Trade Open (BTC/USDT LONG) sent successfully
```

**Telegram Alert Failures (if any):**
```
[TELEGRAM] ❌ Daily Summary failed: HTTP 429 - Too Many Requests
[TELEGRAM] ❌ Trade Close failed: Request timeout (>5s)
```

### Troubleshooting

**No Telegram Test Message:**
- Check logs for `[TELEGRAM] ❌ Test message failed`
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in env file
- Test manually: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`

**Still No Signals (after_core=0):**
- Check `[PUMP_DEBUG] Active thresholds` - should show your env values
- Look at rejection reasons: `[PUMP_DEBUG] Sample rejections`
- Current market might not meet even loose thresholds
- Try lowering `PUMP_MIN_SCORE` to 20 or `PUMP_MIN_RVOL` to 1.5

**Scan Loop Stalling:**
- Should be fixed by commit 317689d (no funding rate calls on spot)
- If still occurs, check for other timeout sources in logs

### Expected Behavior

**SIDEWAYS Market (most common):**
- Uses moderate thresholds: min_vol=150k, min_score=30, min_rvol=2.0
- Should generate 2-5 signals per hour during active periods
- New listings with RVOL >= 5.0 use relaxed thresholds (min_score=8)

**STRONG_BULL Market:**
- Uses loose thresholds: min_vol=100k, min_score=20, min_rvol=1.5
- Should generate 5-10 signals per hour
- More aggressive entries, higher signal volume

**MILD_BEAR / FULL_BEAR Markets:**
- Uses strict thresholds to avoid chop
- May generate 0-2 signals per hour
- Only highest quality setups pass

### Rollback (if needed)

```bash
cd /opt/alpha-sniper
sudo git checkout main  # or previous working commit
sudo systemctl restart alpha-sniper-live.service

# Restore old env
sudo cp /etc/alpha-sniper/alpha-sniper-live.env.backup.XXXXXXXX /etc/alpha-sniper/alpha-sniper-live.env
sudo systemctl restart alpha-sniper-live.service
```

### Support

If issues persist after deployment:
1. Capture full logs: `sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" > debug.log`
2. Check threshold values in logs
3. Look for error patterns in Telegram alerts
4. Verify env file is being read correctly
