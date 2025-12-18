# Alpha Sniper V4.2

Professional crypto trading bot with regime-based risk management and multiple signal engines.

## Quick Start

```bash
cd alpha-sniper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Configure your settings
python main.py
```

See `alpha-sniper/README.md` for detailed documentation.

## Features

- ✅ SIM and LIVE modes
- ✅ Regime-based position sizing (BULL, SIDEWAYS, MILD_BEAR, DEEP_BEAR)
- ✅ Multiple signal engines (long, short, pump, bear_micro)
- ✅ Comprehensive risk management
- ✅ Telegram alerts
- ✅ Safe error handling

## Git Commands

### Initial Setup (if needed)

```bash
git init
git remote add origin https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2.git
git add .
git commit -m "Initial Alpha Sniper V4.2 bot implementation"
git branch -M main
git push -u origin main
```

### Subsequent Updates

```bash
git add .
git commit -m "Update Alpha Sniper V4.2 logic / fixes"
git push
```

## Repository Structure

```
alpha-sniper-v4.2/
├── README.md              # This file
└── alpha-sniper/          # Main bot code
    ├── main.py            # Entry point
    ├── config.py          # Configuration
    ├── risk_engine.py     # Risk management
    ├── signals/           # Trading engines
    ├── utils/             # Utilities
    ├── README.md          # Detailed documentation
    └── requirements.txt   # Dependencies
```

## Configuration Guide

### Core Protection Settings

**Pump Max Loss (Virtual Stop)**
```bash
# Default max loss for all pump trades
PUMP_MAX_LOSS_PCT=0.02                      # 2% guaranteed max loss

# Per-regime overrides (optional)
PUMP_MAX_LOSS_PCT_SIDEWAYS=0.03             # 3% for sideways markets
PUMP_MAX_LOSS_PCT_STRONG_BULL=0.015         # 1.5% for strong bull
PUMP_MAX_LOSS_PCT_MILD_BEAR=0.025           # 2.5% for mild bear
PUMP_MAX_LOSS_PCT_FULL_BEAR=0.04            # 4% for full bear

# Watchdog check interval
PUMP_MAX_LOSS_WATCHDOG_INTERVAL=1.0         # Check every 1 second
```

**Pump-Only Mode**
```bash
PUMP_ONLY=true                               # Use ONLY pump engine
# OR
PUMP_ONLY_MODE=true                          # Alternative name
```

### Telegram Alerts (Full Story)

```bash
# Enable/disable alert types
TELEGRAM_TRADE_ALERTS=true                   # Entry/exit notifications
TELEGRAM_SCAN_SUMMARY=true                   # Scan cycle summaries
TELEGRAM_WHY_NO_TRADE=true                   # Why no trade explanations
TELEGRAM_MAX_MSG_LEN=3500                    # Max message length (truncate)
```

**What You'll Receive:**
- 📊 Scan cycle start (regime, engines, universe size, top signals)
- 🟢 Position entry (symbol, engine, score, triggers, liquidity scaling, stops)
- 📉 Position exit (PnL, hold time, reason, trigger details)
- ❓ Why no trade (reasons when no positions opened)

### VPS Performance Optimization

For low-memory VPS deployments:

```bash
# Limit scan universe size
SCAN_UNIVERSE_MAX=800                        # Max symbols to scan

# Add pacing between scans (reduces CPU spikes)
SCAN_SLEEP_SECS=0                            # Optional sleep (0 = disabled)

# Exchange info caching
EXCHANGE_INFO_CACHE_SECONDS=300              # Cache for 5 minutes

# API rate limiting
MAX_CONCURRENT_API_CALLS=10                  # Limit concurrent requests
```

### Complete Example Configuration

`/etc/alpha-sniper/alpha-sniper-live.env`:
```bash
# === CORE SETTINGS ===
SIM_MODE=false
MEXC_API_KEY=your_key_here
MEXC_SECRET_KEY=your_secret_here
STARTING_EQUITY=1000

# === PUMP MAX LOSS PROTECTION ===
PUMP_MAX_LOSS_PCT=0.02
PUMP_MAX_LOSS_WATCHDOG_INTERVAL=1.0
PUMP_ONLY=true

# === TELEGRAM FULL STORY ===
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_TRADE_ALERTS=true
TELEGRAM_SCAN_SUMMARY=true
TELEGRAM_WHY_NO_TRADE=true

# === VPS PERFORMANCE ===
SCAN_UNIVERSE_MAX=800
EXCHANGE_INFO_CACHE_SECONDS=300
```

## How to Fetch CodeRabbit Report on Server

CodeRabbit PR reviews can be downloaded and saved on the server for offline analysis.

### Prerequisites

**Option 1: Using `gh` CLI (Recommended)**
```bash
# Install gh CLI if not already installed
# Ubuntu/Debian:
sudo apt install gh

# Authenticate
gh auth login
```

**Option 2: Using GitHub API**
```bash
# Set your GitHub personal access token
export GITHUB_TOKEN="ghp_your_token_here"
```

### Fetch Report

```bash
# Navigate to repository
cd /opt/alpha-sniper

# Run the fetch script
./scripts/fetch_coderabbit_report.sh OWNER REPO PR_NUMBER

# Example:
./scripts/fetch_coderabbit_report.sh yogeshkarki65-sudo alpha-sniper-v4.2 123
```

### Output

Reports are saved to `/opt/alpha-sniper/reports/coderabbit_pr_<PR>.md`

```bash
# View the report
cat /opt/alpha-sniper/reports/coderabbit_pr_123.md

# Search for CodeRabbit comments
grep -i 'coderabbit' /opt/alpha-sniper/reports/coderabbit_pr_123.md

# View with pagination
less /opt/alpha-sniper/reports/coderabbit_pr_123.md
```

### Troubleshooting

**Error: "gh: command not found"**
- Install gh CLI or use GitHub API method with GITHUB_TOKEN

**Error: "GITHUB_TOKEN environment variable not set"**
- Create a personal access token at https://github.com/settings/tokens
- Export it: `export GITHUB_TOKEN="ghp_..."`

**No CodeRabbit comments found**
- Verify CodeRabbit bot reviewed the PR
- Check PR number is correct
- Review raw report for any comments

## License

MIT

## Disclaimer

**Educational purposes only. Trading crypto carries significant risk. Use at your own risk.**
