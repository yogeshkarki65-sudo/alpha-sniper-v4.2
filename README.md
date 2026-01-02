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

## Development & Diagnostics

Install development dependencies for running diagnostic scripts:

```bash
pip install -r requirements-dev.txt
```

### Diagnostic Scripts

**Health Check:**
```bash
python scripts/diagnostics.py | tee /tmp/alpha_diag.json
```

**Settings Dump:**
```bash
python scripts/print_settings.py | tee /tmp/alpha_settings.json
```

**Why No Trade Analysis:**
```bash
python scripts/why_no_trade.py | tee /tmp/alpha_why_no_trade.json
```

### Recommended ENV for Pump Catching (Safe Defaults)

```env
# React faster
ALPHA_SCAN_INTERVAL_SECONDS=60

# Avoid dead/pegged pairs and thin books
ALPHA_UNIVERSE_MIN_QUOTE_VOLUME=100000
ALPHA_UNIVERSE_EXCLUDE_BASES=USDC,FDUSD,DAI,TUSD,USDD,EUR,PAXG,WBTC,BTCB
ALPHA_UNIVERSE_EXCLUDE_SYMBOL_PATTERNS=^USDC/USDT$,^PAXG/USDT$

# Early detector (start moderate; tune after audit)
ALPHA_EARLY_RET_5M_MIN=0.015
ALPHA_EARLY_VOL_SPIKE_MIN=1.5
ALPHA_EARLY_ACCEL_REQUIRED=true

# Anti-wick
ALPHA_WICK_FILTER_ENABLE=true
ALPHA_WICK_FILTER_ATR_MULT=1.5

# Liquidity floor (raise as order cap grows)
ALPHA_MIN_DEPTH_USD_ABSOLUTE=15000
```

### Monitoring Commands

After editing `.env`, restart and tail important lines:

```bash
sudo systemctl restart alpha-sniper-async.service
journalctl -u alpha-sniper-async.service -n 120 --no-pager | grep -E "EARLY signal|Opened|Closed|AUDIT|IOC|slip"
```

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

## License

MIT

## Disclaimer

**Educational purposes only. Trading crypto carries significant risk. Use at your own risk.**
