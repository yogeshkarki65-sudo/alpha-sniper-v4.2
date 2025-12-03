# Alpha Sniper V4.2 - Deployment Files

This directory contains production deployment configurations for Alpha Sniper V4.2.

## Contents

### systemd/
- `alpha-sniper-sim.service` - systemd service for SIM mode
- `alpha-sniper-live.service` - systemd service for LIVE mode (⚠️  real money!)

### config/
- `alpha-sniper-sim.env.example` - Environment template for SIM mode
- `alpha-sniper-live.env.example` - Environment template for LIVE mode

## Quick Deploy

### 1. Copy service files
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 2. Copy and configure environment
```bash
sudo cp config/alpha-sniper-sim.env.example /etc/alpha-sniper/alpha-sniper-sim.env
sudo nano /etc/alpha-sniper/alpha-sniper-sim.env
sudo chmod 600 /etc/alpha-sniper/alpha-sniper-sim.env
```

### 3. Start service
```bash
sudo systemctl enable --now alpha-sniper-sim.service
sudo systemctl status alpha-sniper-sim.service
```

## Full Documentation

See `../DEPLOYMENT.md` for complete deployment guide.

## File Locations (Production)

| File | Location | Purpose |
|------|----------|---------|
| Code | `/opt/alpha-sniper/` | Application files |
| Virtual env | `/opt/alpha-sniper/venv/` | Python dependencies |
| Config (SIM) | `/etc/alpha-sniper/alpha-sniper-sim.env` | SIM environment variables |
| Config (LIVE) | `/etc/alpha-sniper/alpha-sniper-live.env` | LIVE environment variables (secrets!) |
| Logs | `/var/log/alpha-sniper/` | Application logs |
| Heartbeat | `/var/run/alpha-sniper/heartbeat.json` | Health check file |
| Service (SIM) | `/etc/systemd/system/alpha-sniper-sim.service` | SIM systemd service |
| Service (LIVE) | `/etc/systemd/system/alpha-sniper-live.service` | LIVE systemd service |

## Security Notes

- All config files should be owned by `alpha-sniper:alpha-sniper`
- Environment files must be `chmod 600` (readable only by owner)
- Never commit actual API keys to version control
- Use different API keys for SIM and LIVE (if possible)

## Service Management

```bash
# Start
sudo systemctl start alpha-sniper-sim.service

# Stop
sudo systemctl stop alpha-sniper-sim.service

# Restart
sudo systemctl restart alpha-sniper-sim.service

# Status
sudo systemctl status alpha-sniper-sim.service

# Logs (real-time)
sudo journalctl -u alpha-sniper-sim.service -f

# Enable on boot
sudo systemctl enable alpha-sniper-sim.service

# Disable on boot
sudo systemctl disable alpha-sniper-sim.service
```
