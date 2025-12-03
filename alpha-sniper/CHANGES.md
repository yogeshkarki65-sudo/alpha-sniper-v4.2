# Deployment Wrapper - What Changed

This document explains what was added for production deployment WITHOUT changing trading logic.

## What Changed

### ✅ Trading Logic (NO CHANGES)
- `main.py` - AlphaSniperBot class: **UNCHANGED**
- `signals/*.py` - All signal engines: **UNCHANGED**
- `risk_engine.py` - Risk management: **UNCHANGED**
- `exchange.py` - Exchange integration: **UNCHANGED**
- `config.py` - Configuration loader: **UNCHANGED**

### ✨ New Files (Deployment Wrapper)

#### Entry Point
- **`run.py`** - Production CLI entry point
  - Validates mode safety (CLI flag + env var must match)
  - Refuses to start if configuration is dangerous
  - Big scary warnings for LIVE mode
  - Starts health check server
  - Delegates to existing `main.py` logic

#### Health System
- **`alpha_sniper/health.py`** - Health check implementation
  - HTTP server on port 8080 (GET /health)
  - Heartbeat file updated every 30s
  - Runs in background threads
- **`alpha_sniper/healthcheck.py`** - CLI healthcheck command
  - Usage: `python -m alpha_sniper.healthcheck`
  - Exit code 0=healthy, 1=unhealthy, 2=unknown

#### Logging
- **`utils/logger_production.py`** - Production logging setup
  - Rotating file handlers (50MB INFO, 100MB DEBUG)
  - Writes to `/var/log/alpha-sniper/` in production
  - Falls back to `./logs/` for local dev
  - Backwards compatible with original logger

#### systemd
- **`deployment/systemd/alpha-sniper-sim.service`** - SIM mode service
- **`deployment/systemd/alpha-sniper-live.service`** - LIVE mode service
  - Runs as dedicated `alpha-sniper` user
  - Automatic restart on failure
  - Journal logging
  - Security hardening (NoNewPrivileges, PrivateTmp)

#### Configuration
- **`deployment/config/alpha-sniper-sim.env.example`** - SIM template
- **`deployment/config/alpha-sniper-live.env.example`** - LIVE template
  - LIVE has more conservative defaults
  - Clear comments on what's dangerous
  - Secrets redacted in examples

#### Developer Experience
- **`Makefile`** - Common tasks
  - `make dev` - Run in SIM mode
  - `make dev-once` - Single test cycle
  - `make test` - Run test scripts
  - `make health` - Check bot health
  - `make logs` - Tail logs

#### Documentation
- **`DEPLOYMENT.md`** - Complete deployment guide (5000+ words)
- **`QUICKSTART.md`** - Quick reference card
- **`deployment/README.md`** - Deployment files overview
- **`CHANGES.md`** - This file

#### Installation
- **`deployment/install.sh`** - Automated installation script

#### Updates
- **`utils/__init__.py`** - Added export for `setup_logger_production`
- **`.gitignore`** - Added deployment secrets exclusion

## How It Works

### Old Way
```bash
# User had to manually ensure SIM_MODE was correct
python main.py
```

### New Way
```bash
# Explicit mode flag + validation
python run.py --mode sim   # Safe
python run.py --mode live  # Scary confirmation required
```

### Safety Flow

1. User runs: `python run.py --mode live`
2. `run.py` loads config from `.env`
3. Validates: CLI wants "live" AND `SIM_MODE=false` in env
4. Validates: API keys are present
5. Shows big warning + requires confirmation
6. Starts health server in background
7. Calls `AlphaSniperBot()` from `main.py` (unchanged)
8. Bot runs normally

## Backwards Compatibility

### Original usage still works (local dev):
```bash
python main.py  # Uses original logger, no health checks
```

### Production usage:
```bash
python run.py --mode sim  # Uses production logger, health checks enabled
```

### For users upgrading:
- Old `.env` files work as-is
- No code changes required in `main.py`
- Tests run unchanged
- Can ignore new deployment files if not needed

## Testing

### Nothing broke:
```bash
# Original functionality
python main.py --once  # Still works

# Test scripts
python test_entry_dete.py  # Still works
python test_dfe.py         # Still works
python test_funding.py     # Still works

# New functionality
python run.py --mode sim --once  # Works with safety checks
make dev-once                     # Works with Make
```

## File Count

### Core files: **UNCHANGED** (except 1 line in utils/__init__.py)
- 0 changes to trading logic
- 0 changes to signal engines
- 0 changes to risk management
- 0 changes to exchange integration
- 1 import line added to `utils/__init__.py`

### New files: **14**
- 1 entry point (`run.py`)
- 3 health check files
- 1 production logger
- 2 systemd services
- 2 config templates
- 1 Makefile
- 3 documentation files
- 1 installation script

## Deployment Locations

### Development (unchanged):
```
~/alpha-sniper-v4.2/alpha-sniper/
├── main.py           # Original entry point
├── run.py            # New production entry point
├── config.py         # Unchanged
├── .env              # Your secrets
└── ...
```

### Production (new):
```
/opt/alpha-sniper/              # Application
/etc/alpha-sniper/              # Configuration (secrets)
/var/log/alpha-sniper/          # Logs
/var/run/alpha-sniper/          # Runtime (heartbeat)
/etc/systemd/system/            # Services
```

## Key Principles

1. **Zero trading logic changes** - Core bot unchanged
2. **Backwards compatible** - Old way still works
3. **Explicit mode selection** - No accidental LIVE trading
4. **Fail-safe defaults** - SIM mode is default everywhere
5. **Production-ready** - Proper logging, health checks, systemd
6. **Clear separation** - Deployment wrapper vs trading core

## Migration Path

### For existing users:

1. **No immediate action required** - Keep using `python main.py`

2. **To use production features:**
   - Use `python run.py --mode sim` instead
   - Optionally deploy with systemd

3. **To deploy to server:**
   - Follow `DEPLOYMENT.md`
   - Use `deployment/install.sh`

### For new users:

- Start with `python run.py --mode sim`
- Follow `QUICKSTART.md`
- Deploy with systemd when ready

## Summary

**What you asked for:**
- ✅ Production-friendly deployment structure
- ✅ Safe mode separation (SIM vs LIVE)
- ✅ Health checks and monitoring
- ✅ systemd integration
- ✅ Proper logging
- ✅ Safety guardrails
- ✅ Complete documentation

**What we preserved:**
- ✅ All trading logic unchanged
- ✅ All signals unchanged
- ✅ All risk management unchanged
- ✅ Backwards compatibility
- ✅ Existing tests work

**What we added:**
- ✅ Production entry point with validation
- ✅ HTTP health endpoint
- ✅ Heartbeat file
- ✅ Production logging
- ✅ systemd services
- ✅ Installation automation
- ✅ Developer convenience (Makefile)
- ✅ Comprehensive documentation
