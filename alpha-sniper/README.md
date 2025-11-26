# Alpha Sniper V4.2 - Full Dynamic Safe Bull

A professional crypto trading bot with regime-based risk management, multiple signal engines, and comprehensive safety features.

## Features

- **SIM and LIVE Modes**: Test strategies safely before going live
- **Regime Detection**: Adapts to market conditions (BULL, SIDEWAYS, MILD_BEAR, DEEP_BEAR)
- **Multiple Signal Engines**:
  - Standard Long Engine (trend-following longs)
  - Standard Short Engine (breakdown shorts with funding checks)
  - Pump Engine (new token pump catcher)
  - Bear Micro-Long Engine (selective longs in bear markets)
- **Risk Management**:
  - Portfolio heat tracking
  - Daily loss limits
  - Regime-based position sizing
  - R-based risk calculation
- **Safety Features**:
  - Exchange outage detection
  - Spread filters
  - Volume filters
  - Graceful error handling
- **Telegram Alerts**: Get notified of regime changes, trades, and daily summaries

## Installation

### Prerequisites

- Python 3.12+ recommended (3.10+ supported)
- Ubuntu 22.04 or similar Linux distribution
- MEXC account (for LIVE mode)

### Quick Start

1. **Clone the repository** (if not already done):
   ```bash
   git clone https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2.git
   cd alpha-sniper-v4.2/alpha-sniper
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   nano .env  # Edit with your settings
   ```

5. **Run in SIM mode** (no API keys required):
   ```bash
   python main.py
   ```

## Configuration

Edit `.env` to configure the bot. Key settings:

### Mode Selection

```
SIM_MODE=true              # Set to false for LIVE trading
STARTING_EQUITY=1000       # Starting capital (USD)
```

### API Keys (Required for LIVE mode)

```
MEXC_API_KEY=your_key_here
MEXC_SECRET_KEY=your_secret_here
```

### Telegram Alerts (Optional)

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Risk Parameters

```
MAX_PORTFOLIO_HEAT=0.012        # Max 1.2% total portfolio risk
MAX_CONCURRENT_POSITIONS=5      # Max open positions
ENABLE_DAILY_LOSS_LIMIT=true    # Enable daily loss limit
MAX_DAILY_LOSS_PCT=0.03         # Max 3% daily loss
```

### Regime-Based Risk Per Trade

```
RISK_PER_TRADE_BULL=0.0025          # 0.25% per trade in BULL
RISK_PER_TRADE_SIDEWAYS=0.0025      # 0.25% per trade in SIDEWAYS
RISK_PER_TRADE_MILD_BEAR=0.0018     # 0.18% per trade in MILD_BEAR
RISK_PER_TRADE_DEEP_BEAR=0.0015     # 0.15% per trade in DEEP_BEAR
```

### Signal Filters

```
MIN_SCORE=80                    # Minimum signal score (0-100)
MIN_24H_QUOTE_VOLUME=50000      # Minimum 24h volume (USD)
MAX_SPREAD_PCT=0.9              # Maximum spread %
SCAN_INTERVAL_SECONDS=300       # Scan every 5 minutes
```

## Usage

### Running the Bot

**SIM Mode** (Recommended for testing):
```bash
python main.py
```

**LIVE Mode**:
1. Set `SIM_MODE=false` in `.env`
2. Add your MEXC API keys
3. Run: `python main.py`

### Stopping the Bot

Press `Ctrl+C` to gracefully shut down the bot.

### Logs

Logs are saved to:
- `logs/bot.log` - INFO level logs
- `logs/bot_debug.log` - DEBUG level logs (detailed)

### Positions

Open positions are saved to `positions.json` and automatically restored on restart.

## Running as a Service (Systemd)

Create `/etc/systemd/system/alpha-sniper.service`:

```ini
[Unit]
Description=Alpha Sniper V4.2 Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/alpha-sniper-v4.2/alpha-sniper
Environment="PATH=/path/to/alpha-sniper-v4.2/alpha-sniper/venv/bin"
ExecStart=/path/to/alpha-sniper-v4.2/alpha-sniper/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable alpha-sniper
sudo systemctl start alpha-sniper
sudo systemctl status alpha-sniper
```

View logs:
```bash
sudo journalctl -u alpha-sniper -f
```

## Architecture

```
alpha-sniper/
├── main.py                 # Main entry point
├── config.py               # Configuration loader
├── exchange.py             # MEXC exchange wrapper
├── risk_engine.py          # Risk management + regime detection
├── signals/                # Signal generation engines
│   ├── long_engine.py      # Standard longs
│   ├── short_engine.py     # Standard shorts
│   ├── pump_engine.py      # Pump catcher
│   ├── bear_micro_long.py  # Bear market longs
│   └── scanner.py          # Master orchestrator
├── utils/                  # Utilities
│   ├── logger.py           # Logging setup
│   ├── telegram.py         # Telegram alerts
│   └── helpers.py          # Helper functions
├── positions.json          # Open positions (created at runtime)
├── logs/                   # Log files (created at runtime)
├── requirements.txt        # Python dependencies
└── .env                    # Configuration (create from .env.example)
```

## Regime Detection

The bot automatically detects market regimes based on BTC/USDT daily data:

- **BULL**: Price > 200 EMA, RSI > 55, 30d return > +10%
- **SIDEWAYS**: Neutral conditions, abs(30d return) <= 10%
- **MILD_BEAR**: Price < 200 EMA, 30d return between -20% and -10%
- **DEEP_BEAR**: Price < 200 EMA, 30d return <= -20%, RSI < 40

Position sizing and signal filtering automatically adjust based on regime.

## Safety Features

1. **SIM Mode**: Test without risking real capital
2. **Daily Loss Limit**: Stops trading if daily loss exceeds threshold
3. **Portfolio Heat Limit**: Prevents over-leveraging
4. **Spread Filters**: Avoids illiquid markets
5. **Volume Filters**: Ensures sufficient liquidity
6. **Max Hold Times**: Automatically closes stale positions
7. **Partial TPs**: Takes profits at 2R and moves SL to breakeven
8. **Graceful Shutdown**: Saves state on exit

## Troubleshooting

### Bot won't start

- Check Python version: `python --version` (needs 3.10+)
- Verify virtual environment is activated
- Install dependencies: `pip install -r requirements.txt`

### No signals generated

- Check logs for errors
- Verify market conditions meet filters (volume, spread, score)
- Try lowering `MIN_SCORE` or `MIN_24H_QUOTE_VOLUME`

### API Errors in LIVE mode

- Verify API keys are correct
- Check MEXC API key permissions (need trading enabled)
- Ensure IP whitelist is configured on MEXC

## License

MIT

## Disclaimer

**This bot is for educational purposes only. Crypto trading carries significant risk. Never trade with money you can't afford to lose. Past performance does not guarantee future results. Use at your own risk.**
