# Alpha Sniper V4.2 - Quick Start

## Local Development (Safe)

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run SIM mode
python run.py --mode sim

# Or use Make
make dev
```

## Production (Ubuntu + systemd)

### One-Command Install

```bash
# As root
sudo /opt/alpha-sniper/deployment/install.sh
```

### Manual Steps

```bash
# 1. Create user & directories
sudo adduser --system --group --home /opt/alpha-sniper alpha-sniper
sudo mkdir -p /var/log/alpha-sniper /var/run/alpha-sniper /etc/alpha-sniper
sudo chown -R alpha-sniper:alpha-sniper /var/log/alpha-sniper /var/run/alpha-sniper /etc/alpha-sniper

# 2. Deploy code
sudo cp -r . /opt/alpha-sniper/
sudo chown -R alpha-sniper:alpha-sniper /opt/alpha-sniper

# 3. Install dependencies
sudo -u alpha-sniper python3 -m venv /opt/alpha-sniper/venv
sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/pip install -r /opt/alpha-sniper/requirements.txt

# 4. Configure
sudo cp deployment/config/alpha-sniper-sim.env.example /etc/alpha-sniper/alpha-sniper-sim.env
sudo nano /etc/alpha-sniper/alpha-sniper-sim.env
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-sim.env

# 5. Install systemd service
sudo cp deployment/systemd/alpha-sniper-sim.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now alpha-sniper-sim.service
```

## Common Commands

```bash
# Check status
sudo systemctl status alpha-sniper-sim.service

# View logs
sudo journalctl -u alpha-sniper-sim.service -f
tail -f /var/log/alpha-sniper/alpha-sniper-sim.log

# Health check
curl http://localhost:8080/health
python -m alpha_sniper.healthcheck

# Restart
sudo systemctl restart alpha-sniper-sim.service

# Stop
sudo systemctl stop alpha-sniper-sim.service
```

## Safety Checklist (LIVE Mode)

Before switching to LIVE mode:

- [ ] Tested 24+ hours in SIM mode
- [ ] API keys configured
- [ ] Telegram notifications working
- [ ] Risk parameters reviewed
- [ ] Small initial capital
- [ ] Emergency stop procedure ready

**Stop bot:** `sudo systemctl stop alpha-sniper-live.service`

## Files You Need to Edit

| File | Purpose | Required for |
|------|---------|--------------|
| `/etc/alpha-sniper/alpha-sniper-sim.env` | SIM configuration | SIM mode |
| `/etc/alpha-sniper/alpha-sniper-live.env` | LIVE configuration | LIVE mode |

**Must set:**
- `MEXC_API_KEY` (LIVE only)
- `MEXC_SECRET_KEY` (LIVE only)
- `TELEGRAM_BOT_TOKEN` (recommended)
- `TELEGRAM_CHAT_ID` (recommended)

## Health Monitoring

### HTTP Endpoint
```bash
curl http://localhost:8080/health
# Returns: {"status": "healthy", ...}
```

### Heartbeat File
```bash
cat /var/run/alpha-sniper/heartbeat.json
# Updated every 30s
```

### CLI Check
```bash
sudo -u alpha-sniper /opt/alpha-sniper/venv/bin/python -m alpha_sniper.healthcheck
# Exit code 0 = healthy, 1 = unhealthy
```

## Architecture

```
Old way:    python main.py
New way:    python run.py --mode sim|live

Entry:      run.py (validates safety)
Core:       main.py (unchanged trading logic)
Health:     HTTP :8080 + heartbeat file
Logs:       /var/log/alpha-sniper/*.log (rotating)
Config:     /etc/alpha-sniper/*.env (secrets)
Service:    systemd manages lifecycle
```

## Full Documentation

- **Complete guide:** `DEPLOYMENT.md`
- **Pump-only mode:** `PUMP_ONLY_MODE.md`
- **Deployment files:** `deployment/README.md`

## Support

- Logs: `sudo journalctl -u alpha-sniper-sim.service -f`
- Health: `curl localhost:8080/health`
- Issues: https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2/issues
