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

## License

MIT

## Disclaimer

**Educational purposes only. Trading crypto carries significant risk. Use at your own risk.**
