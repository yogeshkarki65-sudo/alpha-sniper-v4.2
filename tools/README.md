# Alpha Sniper Tools

## auto_env_optimizer.py

Automatic ENV optimizer that learns from PUMP_DEBUG logs and SQLite database to tune signal generation parameters.

### Features

- **Pre-trade learning**: Analyzes rejection patterns in logs to detect bottlenecks
- **Post-trade learning**: Uses win rate from database to adjust quality filters (when ≥10 trades)
- **Regime-aware**: Different bounds and targets for BULL/SIDEWAYS/BEAR
- **Safety mechanisms**:
  - Cooldown (24h between changes)
  - Hysteresis (20% margin)
  - EMA smoothing (alpha=0.3)
  - Rollback on drawdown >3%
  - Dry-run by default

### Usage

**1. Dry run (safe, no changes):**
```bash
python tools/auto_env_optimizer.py \
  --log /opt/alpha-sniper/logs/bot.log \
  --env /etc/alpha-sniper/alpha-sniper-live.env \
  --dry-run
```

**2. Apply changes and restart bot:**
```bash
python tools/auto_env_optimizer.py \
  --log /opt/alpha-sniper/logs/bot.log \
  --env /etc/alpha-sniper/alpha-sniper-live.env \
  --db /var/lib/alpha-sniper/alpha_sniper.db \
  --apply \
  --restart-cmd "sudo systemctl restart alpha-sniper-live"
```

**3. Custom window and cadence:**
```bash
python tools/auto_env_optimizer.py \
  --log logs/bot.log \
  --env alpha-sniper/.env \
  --window-hours 48 \
  --cadence-hours 12 \
  --dry-run
```

### Parameters

- `--log`: Path to bot.log file (required)
- `--env`: Path to .env file (required)
- `--db`: Path to SQLite database (optional, for post-trade learning)
- `--window-hours`: Analysis window in hours (default: 24)
- `--cadence-hours`: Minimum hours between runs (default: 6)
- `--dry-run`: Dry run mode - no changes (default: true)
- `--apply`: Apply changes to env file
- `--restart-cmd`: Command to restart bot after apply
- `--history`: Path to tune history file (default: /opt/alpha-sniper/tune_history.json)

### What It Tunes

**Tunable Parameters (pump-only):**
- MIN_SCORE
- MIN_RVOL
- MIN_PUMP_VOLUME_24H_USD
- MIN_MOMENTUM
- MIN_RETURN / MAX_RETURN
- SPREAD_MAX
- LIQUIDITY_GUARD_FACTOR
- UNIVERSE_LIMIT
- NEW_LISTING_MIN_RVOL

**NOT Modified (safety):**
- RISK_PERCENT_PER_TRADE
- STOP_LOSS_PCT_*
- MAX_POSITION_SIZE_USD
- Daily loss limits

### Signal Targets (per regime)

- **SIDEWAYS**: 2-8 signals per scan
- **BULL**: 4-12 signals per scan
- **BEAR**: 1-4 signals per scan

### Automation

Run via cron every 6 hours:

```bash
# Add to crontab
0 */6 * * * /opt/alpha-sniper/venv/bin/python /opt/alpha-sniper/tools/auto_env_optimizer.py --log /opt/alpha-sniper/logs/bot.log --env /etc/alpha-sniper/alpha-sniper-live.env --db /var/lib/alpha-sniper/alpha_sniper.db --apply --restart-cmd "sudo systemctl restart alpha-sniper-live" >> /var/log/alpha-sniper-optimizer.log 2>&1
```

### Output

Produces:
1. Human-readable summary with metrics, bottleneck, proposed changes
2. JSON output for automation
3. History file (tune_history.json) tracking all changes and metrics
