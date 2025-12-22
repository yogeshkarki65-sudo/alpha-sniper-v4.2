# Environment Configuration Setup Guide

## Quick Setup Instructions

### Step 1: Copy the template to production location

```bash
# On your production server
sudo cp /opt/alpha-sniper/deployment/alpha-sniper-live.env.template /etc/alpha-sniper/alpha-sniper-live.env
```

### Step 2: Edit the file and add your credentials

```bash
sudo nano /etc/alpha-sniper/alpha-sniper-live.env
```

### Step 3: Fill in these CRITICAL values

**⚠️ YOU MUST CHANGE THESE - THE BOT WILL NOT WORK WITHOUT THEM:**

```bash
# 1. Set mode to LIVE
SIM_MODE=false

# 2. Add your MEXC API credentials
MEXC_API_KEY=your_actual_mexc_api_key
MEXC_SECRET_KEY=your_actual_mexc_secret_key

# 3. Add your Telegram credentials
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### Step 4: Optionally adjust trading parameters

**Recommended starting values for small accounts ($50-$100):**

```bash
# Reduce risk for small accounts
STARTING_EQUITY=58  # Your actual MEXC balance (used as baseline only)
MAX_CONCURRENT_POSITIONS=2  # Reduce from 5 to 2
RISK_PER_TRADE_BULL=0.0015  # Reduce from 0.0025 to 0.0015
RISK_PER_TRADE_SIDEWAYS=0.0015
PUMP_RISK_PER_TRADE=0.0008  # Reduce from 0.0010 to 0.0008
```

### Step 5: Secure the file

```bash
# Restrict permissions (only root can read the API keys)
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
sudo chown root:root /etc/alpha-sniper/alpha-sniper-live.env
```

### Step 6: Verify the configuration

```bash
# Check that all critical values are set
sudo cat /etc/alpha-sniper/alpha-sniper-live.env | grep -E "SIM_MODE|MEXC_API_KEY|TELEGRAM_BOT_TOKEN"
```

You should see:
```
SIM_MODE=false
MEXC_API_KEY=mx0vglxxxxxxxx  # Your actual key
MEXC_SECRET_KEY=xxxxxxxx  # Your actual secret
TELEGRAM_BOT_TOKEN=1234567890:ABCxxxxxx  # Your actual token
TELEGRAM_CHAT_ID=123456789  # Your actual chat ID
```

### Step 7: Restart the service

```bash
sudo systemctl restart alpha-sniper-live.service
sudo journalctl -u alpha-sniper-live.service -f
```

### Step 8: Verify LIVE mode is active

**Expected log output:**

```
🔧 Mode: LIVE
📱 Telegram notifications enabled
💰 Starting Equity: $58.00
[EQUITY_SYNC] FIRST RUN DETECTED: Using MEXC balance as baseline
```

**⚠️ If you see "Mode: SIM", the .env file is not loaded correctly!**

---

## How to Get Your Credentials

### MEXC API Keys

1. Log into MEXC: https://www.mexc.com
2. Go to: Account → API Management
3. Click "Create API"
4. Save your API Key and Secret Key
5. **IMPORTANT:** Enable "Spot Trading" permission
6. **SECURITY:** Set IP whitelist to your VPS IP address

### Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the prompts to name your bot
4. Copy the bot token (format: `1234567890:ABCdefGHI...`)

### Telegram Chat ID

1. Open Telegram and search for `@userinfobot`
2. Send `/start` command
3. Copy your chat ID (format: `123456789`)

Alternatively:

1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}` in the response

---

## Troubleshooting

### Problem: Bot still running in SIM mode

**Solution:**

```bash
# 1. Verify .env file exists
ls -la /etc/alpha-sniper/alpha-sniper-live.env

# 2. Check SIM_MODE value
sudo cat /etc/alpha-sniper/alpha-sniper-live.env | grep SIM_MODE

# 3. Ensure it says exactly: SIM_MODE=false (no quotes, no spaces)

# 4. Reload systemd and restart
sudo systemctl daemon-reload
sudo systemctl restart alpha-sniper-live.service
```

### Problem: No Telegram messages

**Solution:**

```bash
# 1. Verify credentials
sudo cat /etc/alpha-sniper/alpha-sniper-live.env | grep TELEGRAM

# 2. Test Telegram bot manually
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d "chat_id=<YOUR_CHAT_ID>" \
  -d "text=Test message"

# 3. Check if you started the bot in Telegram
# Open your bot in Telegram and send /start
```

### Problem: API key errors from MEXC

**Solution:**

```bash
# 1. Verify API key permissions
# - Log into MEXC → API Management
# - Ensure "Spot Trading" is enabled
# - Check IP whitelist includes your VPS IP

# 2. Verify keys are correct in .env
sudo cat /etc/alpha-sniper/alpha-sniper-live.env | grep MEXC_API_KEY

# 3. Test connection
# Check logs for "MEXC connection successful"
sudo journalctl -u alpha-sniper-live.service -n 50 | grep -i mexc
```

---

## Default Values Explanation

### Risk Management

- `MAX_PORTFOLIO_HEAT=0.012` → Max 1.2% of equity at risk across all positions
- `MAX_CONCURRENT_POSITIONS=5` → Max 5 open trades at once
- `RISK_PER_TRADE_BULL=0.0025` → Risk 0.25% per trade in bull markets
- `PUMP_RISK_PER_TRADE=0.0010` → Risk 0.10% per pump trade (more aggressive)

### Scan Settings

- `SCAN_INTERVAL_SECONDS=300` → Scan for new signals every 5 minutes
- `POSITION_CHECK_INTERVAL_SECONDS=15` → Check SL/TP every 15 seconds

### Safety Features

- `ENABLE_DAILY_LOSS_LIMIT=true` → Stop trading if down 3% today
- `PUMP_MAX_LOSS_PCT=0.02` → GUARANTEED max 2% loss per pump trade
- `DDL_ENABLED=true` → Adapt behavior to market conditions
- `SCRATCH_ENABLED=true` → Exit early if trade thesis fails

---

## Complete Example .env File

**Minimal working configuration for LIVE mode:**

```bash
# Mode
SIM_MODE=false

# Credentials (REPLACE THESE!)
MEXC_API_KEY=mx0vglxxxxxxxx
MEXC_SECRET_KEY=xxxxxxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Basic trading
STARTING_EQUITY=58
SCAN_INTERVAL_SECONDS=300
MAX_CONCURRENT_POSITIONS=2
RISK_PER_TRADE_BULL=0.0015
RISK_PER_TRADE_SIDEWAYS=0.0015
PUMP_RISK_PER_TRADE=0.0008

# Features (use defaults from template for all other settings)
DFE_ENABLED=true
DDL_ENABLED=true
SCRATCH_ENABLED=true
PUMP_ENGINE_ENABLED=true
```

**All other settings will use defaults from `config.py` if not specified in the .env file.**

---

## Next Steps After Configuration

1. **Restart the service:**
   ```bash
   sudo systemctl restart alpha-sniper-live.service
   ```

2. **Monitor startup logs:**
   ```bash
   sudo journalctl -u alpha-sniper-live.service -f | grep -E "Mode:|EQUITY_SYNC|Telegram|MEXC"
   ```

3. **Verify you receive Telegram startup message**

4. **Watch for first equity sync:**
   ```
   [EQUITY_SYNC] FIRST RUN DETECTED: Using MEXC balance as baseline
   💰 Equity updated: $1000.00 → $58.56
   ```

5. **Monitor DDL mode selection:**
   ```
   [DDL_ACTIVE] mode=GRIND | position_size_multiplier=1.00 | max_positions=2
   ```

---

## Security Best Practices

1. **Never commit .env files to git**
   - The `.env` file contains sensitive API keys
   - Only store the `.env.template` in git

2. **Restrict file permissions**
   ```bash
   sudo chmod 600 /etc/alpha-sniper/alpha-sniper-live.env
   ```

3. **Use MEXC IP whitelist**
   - Restrict API access to your VPS IP only
   - Go to MEXC → API Management → Edit API → IP Whitelist

4. **Enable 2FA on MEXC account**
   - Protect your exchange account with 2FA

5. **Use read-only API keys for monitoring**
   - Consider separate read-only keys for dashboards

---

**For production deployment guide, see:** [CRITICAL_LIVE_FIXES.md](../CRITICAL_LIVE_FIXES.md)
