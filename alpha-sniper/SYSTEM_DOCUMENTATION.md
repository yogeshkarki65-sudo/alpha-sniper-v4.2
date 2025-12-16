# Alpha Sniper V4.2 - Complete System Documentation

**Last Updated:** 2025-12-04
**Version:** 4.2 (Pump-Only Mode)
**Deployment:** Production LIVE Trading on Ubuntu Server

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Trading Strategy](#trading-strategy)
4. [Configuration Reference](#configuration-reference)
5. [Deployment Infrastructure](#deployment-infrastructure)
6. [File Structure](#file-structure)
7. [Key Features](#key-features)
8. [Monitoring & Alerting](#monitoring--alerting)
9. [Common Operations](#common-operations)
10. [Troubleshooting](#troubleshooting)

---

## System Overview

### What is Alpha Sniper V4.2?

Alpha Sniper V4.2 is a fully automated cryptocurrency trading bot designed for MEXC futures trading. It runs in **PUMP-ONLY MODE**, which means it exclusively trades using the Pump Engine strategy to capture momentum moves on high-volatility altcoin pumps.

### Current Deployment

- **Environment:** Production LIVE Trading (Real Money)
- **Exchange:** MEXC Futures
- **Mode:** PUMP-ONLY (Long-Only)
- **Server:** Ubuntu 20.04/22.04
- **Service Manager:** systemd
- **Deployment Path:** `/opt/alpha-sniper`
- **Config Path:** `/etc/alpha-sniper/alpha-sniper-live.env`
- **User/Group:** `alpha-sniper:alpha-sniper`

### Key Characteristics

- **LONG-ONLY:** Only takes long positions, never shorts
- **PUMP-ONLY:** Uses only the Pump Engine, core strategy is disabled
- **ATR-BASED TRAILING STOPS:** Dynamic stops based on Average True Range
- **TELEGRAM ALERTS:** Real-time notifications for trades and system events
- **MEXC EQUITY SYNC:** Automatically syncs account balance from MEXC
- **SYSTEMD MANAGED:** Auto-restart, crash notifications, log management

---

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────┐
│                   Alpha Sniper V4.2                      │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Scanner    │→ │ Pump Engine  │→ │  Execution   │  │
│  │  (Market     │  │ (Strategy    │  │  (Order      │  │
│  │   Data)      │  │  Logic)      │  │  Management) │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         ↓                  ↓                  ↓          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Risk Engine  │  │ Telegram Bot │  │ MEXC Exchange│  │
│  │ (Portfolio   │  │ (Alerts)     │  │ (Live Data + │  │
│  │  Mgmt)       │  │              │  │  Trading)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         ↓                  ↓                  ↓
   [logs/bot.log]   [Telegram App]    [MEXC API]
```

### Core Modules

1. **config.py** - Configuration loader with inline comment stripping
2. **main.py** - Main orchestrator, startup logic, equity syncing
3. **signals/scanner.py** - Market data collection, pump detection
4. **signals/pump_engine.py** - Pump strategy logic and scoring
5. **execution/executor.py** - Order placement and management
6. **execution/position_manager.py** - Position tracking and stops
7. **risk/risk_engine.py** - Portfolio heat, position sizing, risk limits
8. **exchange/mexc_client.py** - MEXC API wrapper
9. **utils/telegram_notifier.py** - Telegram notification dispatcher
10. **scripts/telegram_notify.py** - Standalone Telegram helper
11. **scripts/crash_notify.py** - Systemd crash alerting

---

## Trading Strategy

### Pump-Only Mode Strategy

The bot operates exclusively in **PUMP-ONLY MODE**, which means:

#### What It Does
- Scans all MEXC futures pairs every 3 minutes (180 seconds)
- Looks for coins experiencing momentum pumps (high volume + price appreciation)
- Filters by strict criteria (minimum score, volume, momentum thresholds)
- Takes long positions on qualifying pumps
- Uses ATR-based trailing stops to lock in profits
- Exits after 3 hours maximum hold time

#### What It Does NOT Do
- Does NOT use the core V4.2 strategy (regime-based, coil detection, etc.)
- Does NOT take short positions
- Does NOT trade on funding rate overlays
- Does NOT use sideways coil boost logic

### Pump Detection Criteria

A coin must meet ALL of these filters to be traded:

1. **24h Return:** Between 80% - 300% gain
2. **Relative Volume (RVOL):** >= 3.0x average volume
3. **1h Momentum Score:** >= 45 (0-100 scale)
4. **24h Quote Volume:** >= $1,000,000
5. **Pump Score:** >= 90 (0-100 scale)
6. **Max Spread:** <= 0.5% (liquidity check)
7. **Max Hold Time:** 3 hours

### Entry Logic

1. Coin passes all pump filters
2. Risk engine approves position size
3. Portfolio heat check passes (< 0.8%)
4. Max concurrent positions not exceeded (3 max)
5. Entry executed at market price with limit order

### Exit Logic (ATR-Based Trailing Stop)

- **Initial Stop:** 2.5x ATR below entry price
- **Trailing Activation:** After 30 minutes in position
- **Trailing Stop:** 1.5x ATR below highest price achieved
- **Time Stop:** Force exit after 3 hours
- **Manual Stop:** If spread exceeds safety limits

### Position Sizing

```
Position Size = (Account Equity × Risk Per Trade) / Stop Distance

Where:
- Risk Per Trade = 0.08% (PUMP_RISK_PER_TRADE)
- Stop Distance = Entry Price - Initial Stop Price
- Leverage = Dynamically calculated (typically 3-8x)
```

### Portfolio Management

- **Max Portfolio Heat:** 0.8% (total risk across all positions)
- **Max Concurrent Positions:** 3
- **Daily Loss Limit:** 2% (circuit breaker)
- **Position Check Interval:** 15 seconds

---

## Configuration Reference

### File Location
`/etc/alpha-sniper/alpha-sniper-live.env`

### Critical Settings

#### Mode Configuration
```bash
SIM_MODE=false                    # LIVE trading enabled
SIM_DATA_SOURCE=LIVE_DATA         # Not used in live mode
STARTING_EQUITY=1000              # Risk baseline (not actual balance)
```

**Important:** `STARTING_EQUITY` is the risk calculation baseline. Actual equity is synced from MEXC on startup.

#### Pump-Only Mode
```bash
PUMP_ONLY_MODE=true               # CRITICAL: Enables pump-only mode
PUMP_ENGINE_ENABLED=true          # Pump engine active
PUMP_MAX_CONCURRENT=1             # Max pump positions
PUMP_RISK_PER_TRADE=0.0008        # 0.08% risk per pump trade
```

#### Pump Filters
```bash
PUMP_MIN_24H_RETURN=0.80          # 80% minimum 24h gain
PUMP_MAX_24H_RETURN=3.00          # 300% maximum 24h gain
PUMP_MIN_RVOL=3.0                 # 3x volume vs average
PUMP_MIN_MOMENTUM_1H=45           # Momentum score 45+
PUMP_MIN_24H_QUOTE_VOLUME=1000000 # $1M minimum volume
PUMP_MIN_SCORE=90                 # Pump score 90+
PUMP_MAX_HOLD_HOURS=3             # 3 hour max hold
```

#### ATR Trailing Stops
```bash
PUMP_TRAIL_INITIAL_ATR_MULT=2.5   # Initial stop: 2.5x ATR
PUMP_TRAIL_ATR_MULT=1.5           # Trailing stop: 1.5x ATR
PUMP_TRAIL_START_MINUTES=30       # Trail after 30 minutes
```

#### Risk Management
```bash
MAX_PORTFOLIO_HEAT=0.008          # 0.8% total portfolio risk
MAX_CONCURRENT_POSITIONS=3        # 3 position limit
MAX_SPREAD_PCT=0.5                # 0.5% max spread
ENABLE_DAILY_LOSS_LIMIT=true     # Daily loss protection
MAX_DAILY_LOSS_PCT=0.02           # 2% daily loss limit
```

#### Disabled Features (Pump-Only Mode)
```bash
SHORT_FUNDING_OVERLAY_ENABLED=false  # Disabled in pump-only
SIDEWAYS_COIL_ENABLED=true           # Ignored in pump-only
DFE_ENABLED=false                    # Dynamic filters off
ENTRY_DETE_ENABLED=true              # Smart entry timing enabled
```

#### Telegram Alerts
```bash
TELEGRAM_BOT_TOKEN=8541042711:AAH1kVhxBj8R_8S6kINWg2f3HhjK3aAF-3s
TELEGRAM_CHAT_ID=5809355125
```

#### MEXC API
```bash
MEXC_API_KEY=mx0vglqqwmHW4LxJ1m
MEXC_SECRET_KEY=b35680c2853049ce9050511418d65074
```

#### Timing
```bash
SCAN_INTERVAL_SECONDS=180         # Scan market every 3 minutes
POSITION_CHECK_INTERVAL_SECONDS=15 # Check stops every 15 seconds
```

### Configuration Parsing

The bot uses a custom `get_env()` helper that:
- Strips inline comments (e.g., `SETTING=value # comment` works correctly)
- Strips whitespace from all values
- Handles boolean parsing (`true`, `false`, `1`, `0`, `yes`, `no`)

---

## Deployment Infrastructure

### Systemd Services

#### Primary Service: `alpha-sniper-live.service`

**Location:** `/etc/systemd/system/alpha-sniper-live.service`

**Key Features:**
- Runs as `alpha-sniper` user
- Working directory: `/opt/alpha-sniper`
- Environment file: `/etc/alpha-sniper/alpha-sniper-live.env`
- Auto-restart on failure
- 60-second graceful shutdown timeout
- Triggers crash notification on failure

**Commands:**
```bash
# Start the bot
sudo systemctl start alpha-sniper-live.service

# Stop the bot
sudo systemctl stop alpha-sniper-live.service

# Restart the bot
sudo systemctl restart alpha-sniper-live.service

# Check status
sudo systemctl status alpha-sniper-live.service

# View logs
sudo journalctl -u alpha-sniper-live.service -f

# Enable auto-start on boot
sudo systemctl enable alpha-sniper-live.service
```

#### Crash Notification Service: `alpha-sniper-live-crash-notify.service`

**Location:** `/etc/systemd/system/alpha-sniper-live-crash-notify.service`

**Purpose:** Sends Telegram alert when main service crashes or fails to start

**Trigger:** Automatically called via `OnFailure=` in main service

**Message Format:**
```
❌ Alpha Sniper LIVE crashed or failed to start
Host: ip-172-26-1-170
Service: alpha-sniper-live.service
Check logs: journalctl -u alpha-sniper-live.service -n 50
```

### Directory Structure

```
/opt/alpha-sniper/              # Production deployment
├── venv/                        # Python virtual environment
├── run.py                       # Entry point
├── config.py                    # Configuration loader
├── main.py                      # Main orchestrator
├── signals/                     # Strategy modules
│   ├── scanner.py              # Market scanner
│   ├── pump_engine.py          # Pump strategy
│   └── scoring.py              # Scoring logic
├── execution/                   # Execution modules
│   ├── executor.py             # Order execution
│   └── position_manager.py     # Position tracking
├── risk/                        # Risk modules
│   └── risk_engine.py          # Risk management
├── exchange/                    # Exchange modules
│   └── mexc_client.py          # MEXC API client
├── utils/                       # Utility modules
│   ├── telegram_notifier.py    # Telegram dispatcher
│   └── logger.py               # Logging setup
├── scripts/                     # Standalone scripts
│   ├── telegram_notify.py      # Telegram helper
│   ├── trade_notify.py         # Trade notifications
│   └── crash_notify.py         # Crash alerting
└── logs/                        # Log files
    └── bot.log                  # Main log file

/etc/alpha-sniper/              # Configuration directory
└── alpha-sniper-live.env       # Environment variables

~/alpha-sniper-v4.2/            # Git repository (development)
└── alpha-sniper/               # Source code
    └── .env.live.clean         # Clean config template
```

### Deployment Workflow

1. **Development:** Make changes in git repo (`~/alpha-sniper-v4.2/`)
2. **Commit & Push:** Push to branch `claude/fix-issues-018PzVLhR8jpyJBusPvozqDS`
3. **Deploy to Production:**
   ```bash
   cd /opt/alpha-sniper
   git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS
   sudo systemctl restart alpha-sniper-live.service
   ```

---

## File Structure

### Key Python Files

#### `config.py`
- Loads environment variables from `.env` or system environment
- Strips inline comments using regex: `re.sub(r'\s*#.*$', '', value)`
- Parses booleans safely
- Validates MEXC API keys for live mode
- Returns `Config` object with all settings as attributes

#### `main.py`
- Main entry point via `run.py`
- Initializes all modules (scanner, pump engine, executor, risk engine, telegram)
- Sends startup Telegram notification with mode indicator
- Syncs equity from MEXC in live mode
- Sends equity sync notification comparing config vs MEXC balance
- Runs main loop: scan → evaluate → execute → check positions
- Handles graceful shutdown on SIGTERM/SIGINT

#### `signals/scanner.py`
- Fetches market data from MEXC every scan interval
- Enforces PUMP-ONLY mode (lines 65-72):
  ```python
  if self.config.pump_only_mode:
      self.logger.info("[PUMP-ONLY MODE] Using ONLY pump engine, core strategy disabled")
      # Only run pump engine
  ```
- Collects ticker data, funding rates, orderbook depth
- Passes data to pump engine for evaluation

#### `signals/pump_engine.py`
- Evaluates coins against pump criteria
- Calculates pump score (0-100) based on:
  - 24h return
  - Relative volume (RVOL)
  - 1h momentum
  - Volume quality
- Filters by min/max thresholds
- Returns ranked list of pump candidates

#### `execution/executor.py`
- Executes market orders via MEXC API
- Calculates position size based on risk engine
- Determines leverage dynamically
- Places stop-loss orders
- Sends trade notifications to Telegram

#### `execution/position_manager.py`
- Tracks open positions
- Updates trailing stops every 15 seconds
- Checks time-based exits (3 hour max)
- Monitors spread and liquidity
- Closes positions when stop triggered

#### `risk/risk_engine.py`
- Manages portfolio-level risk
- Calculates current portfolio heat
- Enforces daily loss limits
- Determines position size per trade
- Updates equity from MEXC

### Helper Scripts

#### `scripts/telegram_notify.py`
Standalone Telegram notification sender.

**Features:**
- Loads credentials from env file (`/etc/alpha-sniper/alpha-sniper-live.env`)
- Strips inline comments from env file
- Sends message via Telegram Bot API
- Returns exit code 0 on success, 1 on failure

**Usage:**
```bash
python scripts/telegram_notify.py "Test message"
```

#### `scripts/trade_notify.py`
Formats and sends trade event notifications.

**Usage:**
```bash
python scripts/trade_notify.py \
  --event opened \
  --context PUMP \
  --symbol BTCUSDT \
  --side LONG \
  --entry_price 45000 \
  --size 0.1 \
  --leverage 5
```

**Output Example:**
```
🟢 [PUMP] TRADE OPENED
Symbol: BTCUSDT
Side: LONG ×5
Entry: $45,000.00
Size: 0.1 BTC
Notional: $4,500.00
```

#### `scripts/crash_notify.py`
Sends crash alert when systemd service fails.

**Triggered by:** `OnFailure=` directive in systemd service file

**Message:**
```
❌ Alpha Sniper LIVE crashed or failed to start
Host: <hostname>
Service: alpha-sniper-live.service
Check logs: journalctl -u alpha-sniper-live.service -n 50
```

---

## Key Features

### 1. Pump-Only Mode Enforcement

**Purpose:** Simplify strategy to focus exclusively on momentum pumps

**Implementation:**
- Config setting: `PUMP_ONLY_MODE=true`
- Scanner checks this setting and disables core strategy
- Only pump engine evaluates signals
- All other V4.2 overlays are ignored

**Benefits:**
- Simpler logic, easier to debug
- Focused on high-conviction setups
- Avoids regime detection complexity

### 2. ATR-Based Trailing Stops

**Purpose:** Dynamically adjust stops based on volatility

**How It Works:**
1. **Initial Stop:** 2.5x ATR below entry
   - ATR = Average True Range (14-period)
   - Protects against immediate reversals
2. **Trailing Activation:** After 30 minutes
   - Allows pump to develop before trailing
3. **Trailing Stop:** 1.5x ATR below highest price
   - Locks in profits as price rises
   - Adapts to changing volatility

**Example:**
```
Entry: $1.00
ATR: $0.04
Initial Stop: $1.00 - (2.5 × $0.04) = $0.90

After 30 min, price reaches $1.50:
Trailing Stop: $1.50 - (1.5 × $0.04) = $1.44

Price falls to $1.44 → Position closed
```

### 3. MEXC Equity Syncing

**Purpose:** Use actual account balance for risk calculations, not config value

**Implementation:**
1. On startup, bot reads `STARTING_EQUITY` from config (baseline)
2. Calls MEXC API: `get_total_usdt_balance()`
3. Updates risk engine with live equity
4. Sends Telegram notification comparing config vs actual

**Notification Example:**
```
💰 Equity synced from MEXC
Config: $1,000.00
MEXC Balance: $1,234.56
```

**Why Important:**
- Config equity is just a baseline for risk calculations
- Actual equity changes after P&L
- Bot must use real balance to calculate position sizes correctly

### 4. Telegram Real-Time Alerts

**Startup Notification:**
```
🚀 Alpha Sniper V4.2 started
Mode: LIVE (PUMP-ONLY)
Data: LIVE
Config Equity: $1,000.00 (risk baseline)
Regime: BULL
Note: Equity will sync from MEXC balance shortly
```

**Trade Notifications:**
- Trade opened
- Trade closed
- Stop-loss hit
- Take-profit hit
- Time-based exit

**System Alerts:**
- Crash notifications
- Daily loss limit reached
- Exchange outage detected

### 5. Crash Recovery & Notifications

**OnFailure Integration:**
- Systemd detects service crash
- Automatically triggers crash notification service
- Telegram alert sent immediately
- Service auto-restarts after 15 seconds

**Graceful Shutdown:**
- 60-second timeout allows position cleanup
- Closes open positions safely
- Flushes logs before exit

### 6. Daily Loss Limit Protection

**Purpose:** Circuit breaker to prevent runaway losses

**Settings:**
```bash
ENABLE_DAILY_LOSS_LIMIT=true
MAX_DAILY_LOSS_PCT=0.02  # 2% max daily loss
```

**Behavior:**
- Tracks daily P&L from UTC 00:00
- If daily loss exceeds 2%, bot stops taking new positions
- Existing positions remain open but can still exit
- Resets at UTC midnight

### 7. Smart Entry Timing (Entry-DETE)

**Purpose:** Wait for slight dip before entering to get better price

**Settings:**
```bash
ENTRY_DETE_ENABLED=true
ENTRY_DETE_MAX_WAIT_SECONDS=120    # Wait up to 2 minutes
ENTRY_DETE_MIN_TRIGGERS=2          # Need 2 favorable ticks
ENTRY_DETE_MIN_DIP_PCT=0.005       # 0.5% minimum dip
ENTRY_DETE_MAX_DIP_PCT=0.015       # 1.5% maximum dip
```

**How It Works:**
1. Signal triggers
2. Bot waits for price to dip 0.5-1.5%
3. Enters on favorable tick (volume spike + dip)
4. If no dip within 2 minutes, enters at market

---

## Monitoring & Alerting

### Log Files

**Location:** `/opt/alpha-sniper/logs/bot.log`

**Content:**
- Timestamped events
- Scan results
- Trade executions
- Position updates
- Errors and warnings

**Rotation:** Automatically rotated by Python logging (typically daily or by size)

### Systemd Journal

**View Live Logs:**
```bash
sudo journalctl -u alpha-sniper-live.service -f
```

**View Last 50 Lines:**
```bash
sudo journalctl -u alpha-sniper-live.service -n 50
```

**View Errors Only:**
```bash
sudo journalctl -u alpha-sniper-live.service -p err
```

**View Logs Since Time:**
```bash
sudo journalctl -u alpha-sniper-live.service --since "1 hour ago"
```

### Telegram Monitoring

All critical events are sent to Telegram:
- ✅ Service started
- 💰 Equity synced
- 🟢 Trade opened
- 🔴 Trade closed
- 🛑 Stop-loss hit
- ⏰ Time-based exit
- ❌ Service crashed
- 🚨 Daily loss limit reached

### Health Checks

**Service Status:**
```bash
sudo systemctl is-active alpha-sniper-live.service
# Output: active
```

**Process Check:**
```bash
ps aux | grep "python.*run.py"
```

**Recent Activity:**
```bash
sudo journalctl -u alpha-sniper-live.service --since "10 minutes ago" | tail -n 20
```

---

## Common Operations

### Restart the Bot

```bash
sudo systemctl restart alpha-sniper-live.service
```

### Update Configuration

```bash
# Edit config
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Restart to apply
sudo systemctl restart alpha-sniper-live.service
```

### Deploy Code Changes

```bash
# Stop service
sudo systemctl stop alpha-sniper-live.service

# Pull latest code
cd /opt/alpha-sniper
sudo -u alpha-sniper git pull origin claude/fix-issues-018PzVLhR8jpyJBusPvozqDS

# Restart service
sudo systemctl start alpha-sniper-live.service
```

### Update Telegram Credentials

```bash
# Edit config
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Find and update:
TELEGRAM_BOT_TOKEN=new_token_here
TELEGRAM_CHAT_ID=new_chat_id_here

# Restart
sudo systemctl restart alpha-sniper-live.service
```

### Change Risk Parameters

```bash
# Edit config
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# Example: Reduce risk per trade
PUMP_RISK_PER_TRADE=0.0005  # Changed from 0.0008 to 0.0005

# Example: Increase max positions
MAX_CONCURRENT_POSITIONS=5   # Changed from 3 to 5

# Restart
sudo systemctl restart alpha-sniper-live.service
```

### View Position Status

```bash
# Check recent logs for position updates
sudo journalctl -u alpha-sniper-live.service -n 100 | grep -i "position\|trade"
```

### Emergency Stop

```bash
# Stop bot immediately (60s graceful shutdown)
sudo systemctl stop alpha-sniper-live.service

# Force kill if needed (not recommended)
sudo systemctl kill -s SIGKILL alpha-sniper-live.service
```

### Backup Configuration

```bash
# Backup current config
sudo cp /etc/alpha-sniper/alpha-sniper-live.env \
       /etc/alpha-sniper/alpha-sniper-live.env.backup.$(date +%Y%m%d)

# List backups
ls -lah /etc/alpha-sniper/*.backup*
```

---

## Troubleshooting

### Service Won't Start

**Symptom:** `sudo systemctl start alpha-sniper-live.service` fails

**Diagnosis:**
```bash
# Check service status
sudo systemctl status alpha-sniper-live.service

# View detailed logs
sudo journalctl -u alpha-sniper-live.service -n 50
```

**Common Causes:**
1. **Missing MEXC API keys**
   - Check: `sudo grep "MEXC_API_KEY\|MEXC_SECRET_KEY" /etc/alpha-sniper/alpha-sniper-live.env`
   - Fix: Add valid keys to config

2. **Invalid config syntax**
   - Check: `sudo cat /etc/alpha-sniper/alpha-sniper-live.env | grep -v "^#" | grep "="`
   - Fix: Ensure all values are properly formatted

3. **Permission issues**
   - Check: `ls -la /etc/alpha-sniper/alpha-sniper-live.env`
   - Fix: `sudo chown alpha-sniper:alpha-sniper /etc/alpha-sniper/alpha-sniper-live.env`

4. **Python dependencies missing**
   - Check: `sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/pip list`
   - Fix: `sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/pip install -r requirements.txt`

### No Telegram Notifications

**Symptom:** Bot runs but no Telegram messages

**Diagnosis:**
```bash
# Test telegram_notify.py directly
sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/python \
  /opt/alpha-sniper/scripts/telegram_notify.py "Test message"
```

**Common Causes:**
1. **Invalid bot token**
   - Verify token with Telegram BotFather
   - Check: `sudo grep "TELEGRAM_BOT_TOKEN" /etc/alpha-sniper/alpha-sniper-live.env`

2. **Wrong chat ID**
   - Get your chat ID from @userinfobot on Telegram
   - Check: `sudo grep "TELEGRAM_CHAT_ID" /etc/alpha-sniper/alpha-sniper-live.env`

3. **Network issues**
   - Test: `curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe`

### No Trades Being Taken

**Symptom:** Bot scans but never opens positions

**Diagnosis:**
```bash
# Check recent scans
sudo journalctl -u alpha-sniper-live.service -n 100 | grep -i "scan\|pump\|candidate"
```

**Common Causes:**
1. **Pump filters too strict**
   - Check: Logs show "No pump candidates found"
   - Fix: Lower `PUMP_MIN_SCORE`, `PUMP_MIN_RVOL`, or `PUMP_MIN_MOMENTUM_1H`

2. **Portfolio heat exceeded**
   - Check: Logs show "Portfolio heat limit exceeded"
   - Fix: Close existing positions or increase `MAX_PORTFOLIO_HEAT`

3. **Daily loss limit reached**
   - Check: Logs show "Daily loss limit reached"
   - Fix: Wait for UTC reset or disable `ENABLE_DAILY_LOSS_LIMIT`

4. **Max positions reached**
   - Check: Logs show "Max concurrent positions reached"
   - Fix: Wait for positions to close or increase `MAX_CONCURRENT_POSITIONS`

### Positions Not Closing

**Symptom:** Positions remain open past expected time

**Diagnosis:**
```bash
# Check position manager logs
sudo journalctl -u alpha-sniper-live.service -n 200 | grep -i "position\|stop\|close"
```

**Common Causes:**
1. **Trailing stop too wide**
   - Check: `PUMP_TRAIL_ATR_MULT` setting
   - Fix: Reduce from 1.5 to 1.2 for tighter stops

2. **Time-based exit not triggering**
   - Check: Logs for "Max hold time reached"
   - Verify: `PUMP_MAX_HOLD_HOURS` is set correctly

3. **Position manager error**
   - Check: Logs for Python exceptions in position_manager.py
   - Fix: Review error and restart service

### Crash Loop

**Symptom:** Service keeps restarting every 15 seconds

**Diagnosis:**
```bash
# View crash logs
sudo journalctl -u alpha-sniper-live.service --since "5 minutes ago"
```

**Common Causes:**
1. **Python exception on startup**
   - Look for: Traceback in logs
   - Fix: Address the specific error

2. **MEXC API connection failure**
   - Test: Manually call MEXC API
   - Fix: Check network, verify API keys

3. **Config parsing error**
   - Look for: "Config error" in logs
   - Fix: Validate config syntax

**Temporary Stop Crash Loop:**
```bash
sudo systemctl stop alpha-sniper-live.service
sudo systemctl disable alpha-sniper-live.service
# Fix issue, then:
sudo systemctl enable alpha-sniper-live.service
sudo systemctl start alpha-sniper-live.service
```

### High Memory/CPU Usage

**Symptom:** Server resources maxed out

**Diagnosis:**
```bash
# Check resource usage
top -p $(pgrep -f "run.py")
```

**Common Causes:**
1. **Too many concurrent positions**
   - Reduce: `MAX_CONCURRENT_POSITIONS`

2. **Scan interval too frequent**
   - Increase: `SCAN_INTERVAL_SECONDS` from 180 to 300

3. **Log file too large**
   - Rotate: `sudo logrotate /etc/logrotate.d/alpha-sniper`

### Equity Not Syncing

**Symptom:** Startup shows config equity but no MEXC sync

**Diagnosis:**
```bash
# Check for equity sync notification
sudo journalctl -u alpha-sniper-live.service -n 100 | grep -i "equity"
```

**Common Causes:**
1. **MEXC API error**
   - Look for: API errors in logs
   - Test: Call `get_total_usdt_balance()` manually

2. **Sync already completed**
   - Note: Notification only sent once on startup

3. **Balance matches config**
   - If MEXC balance == config equity, notification may not fire

---

## Appendix A: Configuration Quick Reference

### Most Important Settings

| Setting | Value | Purpose |
|---------|-------|---------|
| `SIM_MODE` | `false` | Enable LIVE trading |
| `PUMP_ONLY_MODE` | `true` | Use only pump engine |
| `PUMP_RISK_PER_TRADE` | `0.0008` | Risk 0.08% per trade |
| `MAX_PORTFOLIO_HEAT` | `0.008` | Total risk 0.8% |
| `MAX_CONCURRENT_POSITIONS` | `3` | Max 3 open positions |
| `PUMP_MIN_SCORE` | `90` | Minimum pump score |
| `PUMP_MIN_RVOL` | `3.0` | 3x volume requirement |
| `PUMP_MAX_HOLD_HOURS` | `3` | Max 3 hour hold |
| `PUMP_TRAIL_ATR_MULT` | `1.5` | Trailing stop width |

### Emergency Shutoff

```bash
# Stop trading immediately
sudo systemctl stop alpha-sniper-live.service

# Disable auto-restart
sudo systemctl disable alpha-sniper-live.service

# Close all positions manually via MEXC website
```

---

## Appendix B: Contact & Support

### Logs to Provide for Support

When asking for help, always provide:

1. **Service status:**
   ```bash
   sudo systemctl status alpha-sniper-live.service
   ```

2. **Recent logs:**
   ```bash
   sudo journalctl -u alpha-sniper-live.service -n 100 --no-pager
   ```

3. **Configuration (without secrets):**
   ```bash
   sudo grep -v "API_KEY\|SECRET\|TOKEN" /etc/alpha-sniper/alpha-sniper-live.env
   ```

4. **Error messages:**
   ```bash
   sudo journalctl -u alpha-sniper-live.service -p err -n 50
   ```

### Quick Health Check Script

Save as `/opt/alpha-sniper/scripts/health_check.sh`:

```bash
#!/bin/bash
echo "=== Alpha Sniper V4.2 Health Check ==="
echo ""
echo "Service Status:"
sudo systemctl is-active alpha-sniper-live.service
echo ""
echo "Configuration:"
sudo grep -E "^(SIM_MODE|PUMP_ONLY_MODE|MAX_CONCURRENT_POSITIONS)=" /etc/alpha-sniper/alpha-sniper-live.env
echo ""
echo "Last 10 Log Lines:"
sudo journalctl -u alpha-sniper-live.service -n 10 --no-pager
echo ""
echo "Process Info:"
ps aux | grep "[r]un.py"
```

Run with: `bash /opt/alpha-sniper/scripts/health_check.sh`

---

## End of Documentation

**Version:** 4.2 (Pump-Only)
**Last Updated:** 2025-12-04
**Status:** Production LIVE Trading Active
