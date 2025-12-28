# Alpha Sniper V4.2 - Production Setup Guide

## 🎯 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install runtime dependencies
pip install -r requirements.txt

# Optional: Install development tools
pip install -r requirements-dev.txt
```

### 2. Configure Environment

```bash
# Copy example config
cp alpha-sniper/.env.example alpha-sniper/.env

# Edit configuration
nano alpha-sniper/.env
```

**Minimum required settings:**
```bash
# Trading mode
SIM_MODE=true                    # Set to false for LIVE trading

# MEXC API (only needed for LIVE mode)
MEXC_API_KEY=your_key_here
MEXC_SECRET_KEY=your_secret_here

# Bot configuration
STARTING_EQUITY=1000.0
MIN_SCORE=30
PUMP_ONLY_MODE=true
```

### 3. Run the Bot

```bash
# Test in SIM mode (safe, no real trading)
python alpha-sniper/run.py --mode sim

# Single cycle test
python alpha-sniper/run.py --mode sim --once

# LIVE trading (REAL MONEY!)
python alpha-sniper/run.py --mode live
```

---

## 📁 Production Directory Structure

```
alpha-sniper-v4.2/
├── alpha-sniper/              # Main package
│   ├── __init__.py
│   ├── run.py                 # 🚀 ENTRYPOINT
│   ├── main.py                # Bot orchestration
│   ├── config.py              # Configuration loader
│   ├── exchange.py            # MEXC API wrapper
│   ├── risk_engine.py         # Position/risk management
│   ├── signals/               # Signal generation engines
│   │   ├── scanner.py         # Multi-engine scanner
│   │   ├── pump_engine.py     # PUMP signals (primary)
│   │   ├── long_engine.py     # CORE mean reversion
│   │   ├── bear_micro_long.py # BEAR_MICRO scalping
│   │   └── short_engine.py    # SHORT (disabled)
│   ├── utils/                 # Utilities
│   │   ├── logger.py
│   │   ├── helpers.py
│   │   ├── telegram.py
│   │   └── ...
│   ├── alpha_sniper/          # Health check subpackage
│   │   ├── health.py
│   │   └── healthcheck.py
│   └── deployment/            # Production deployment
│       ├── systemd/           # Service files
│       └── install.sh
├── pyproject.toml             # Package configuration
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── .env                       # Runtime configuration
├── logs/                      # Bot logs (created at runtime)
└── /var/lib/alpha-sniper/    # Persistent data (created at runtime)
    ├── positions.json         # Open positions
    └── alpha_sniper.db        # Trade history (SQLite)
```

---

## 🔧 Systemd Service (Production)

### Install as Service

```bash
# Run installer
sudo bash alpha-sniper/deployment/install.sh

# Or manually:
sudo cp alpha-sniper/deployment/systemd/alpha-sniper-live.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable alpha-sniper-live.service
```

### Service Commands

```bash
# Start bot
sudo systemctl start alpha-sniper-live.service

# Stop bot
sudo systemctl stop alpha-sniper-live.service

# Restart bot
sudo systemctl restart alpha-sniper-live.service

# Check status
sudo systemctl status alpha-sniper-live.service

# View logs
sudo journalctl -u alpha-sniper-live.service -f
```

---

## 🧪 Testing

### Verify Installation

```bash
# 1. Package import
python -c "import alpha_sniper; print(f'Version: {alpha_sniper.__version__}')"

# 2. Module imports
cd alpha-sniper
python -c "from main import AlphaSniperBot; print('OK')"
cd ..

# 3. Entrypoint
python alpha-sniper/run.py --help

# 4. Code quality
ruff check alpha-sniper/
```

### Test Trading Cycle

```bash
# Single cycle in SIM mode (no real trading)
SIM_MODE=true python alpha-sniper/run.py --mode sim --once
```

---

## 📊 Monitoring

### Log Files

```bash
# Real-time logs
tail -f logs/bot.log

# Watch for signals
tail -f logs/bot.log | grep -E "Signal.*score|Position opened"

# Check errors
grep ERROR logs/bot.log | tail -20
```

### Health Check Endpoint

The bot exposes a health check endpoint on port 8080:

```bash
curl http://localhost:8080/health
```

---

## 🔐 Security Best Practices

1. **Never commit .env files** - Contains API keys
2. **Use SIM_MODE first** - Test before LIVE trading
3. **Start with small equity** - Test with $100-500 first
4. **Monitor actively** - Watch first 24 hours closely
5. **Set position limits** - Use MAX_POSITION_SIZE_USD
6. **Enable Telegram** - Get real-time trade notifications

---

## 🚨 Troubleshooting

### Import Errors

```bash
# Reinstall package
pip install -e . --force-reinstall
```

### Configuration Issues

```bash
# Check config is loaded
cd alpha-sniper
python -c "from config import get_config; cfg = get_config(); print(f'SIM_MODE: {cfg.sim_mode}')"
```

### Bot Not Trading

```bash
# Check logs for MIN_SCORE rejections
tail -100 logs/bot.log | grep -E "MIN_SCORE|rejected"

# Verify signals are being generated
tail -100 logs/bot.log | grep "Signal.*score"
```

---

## 📈 Performance Monitoring

### Database Queries

```bash
# View all trades
sqlite3 /var/lib/alpha-sniper/alpha_sniper.db "SELECT * FROM trades ORDER BY timestamp_close DESC LIMIT 10;"

# Calculate total PnL
sqlite3 /var/lib/alpha-sniper/alpha_sniper.db "SELECT SUM(pnl_usd) as total_pnl FROM trades;"

# Win rate
sqlite3 /var/lib/alpha-sniper/alpha_sniper.db "SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(100.0 * SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) / COUNT(*), 2) as win_rate_pct
FROM trades;"
```

---

## 🔄 Updates & Maintenance

### Pull Latest Changes

```bash
cd /opt/alpha-sniper
sudo systemctl stop alpha-sniper-live.service

git pull origin main

pip install -r requirements.txt --upgrade

sudo systemctl start alpha-sniper-live.service
```

### Backup Important Data

```bash
# Backup database
cp /var/lib/alpha-sniper/alpha_sniper.db ~/backup_$(date +%Y%m%d).db

# Backup config
cp alpha-sniper/.env ~/backup_env_$(date +%Y%m%d)
```

---

## 📞 Support

- **Issues**: https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2/issues
- **Documentation**: See README.md
- **Logs**: Check `logs/bot.log` for detailed information
