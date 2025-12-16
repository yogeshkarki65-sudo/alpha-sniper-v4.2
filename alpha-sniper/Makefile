.PHONY: help dev dev-once test lint clean install health status logs

# Default target
help:
	@echo "Alpha Sniper V4.2 - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev        - Run bot in SIM mode (safe)"
	@echo "  make dev-once   - Run single test cycle in SIM mode"
	@echo "  make live       - Run bot in LIVE mode (DANGEROUS!)"
	@echo ""
	@echo "Testing:"
	@echo "  make test       - Run test scripts"
	@echo "  make health     - Check bot health status"
	@echo ""
	@echo "Deployment:"
	@echo "  make install    - Install dependencies"
	@echo "  make status     - Show systemd service status"
	@echo "  make logs       - Tail bot logs"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      - Clean logs and cache"
	@echo "  make lint       - Run code quality checks (if configured)"

# Run in SIM mode for development
dev:
	python run.py --mode sim

# Run single cycle test
dev-once:
	python run.py --mode sim --once

# Run in LIVE mode (requires confirmation)
live:
	@echo "⚠️  WARNING: This will run LIVE trading mode!"
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || (echo "Cancelled." && exit 1)
	python run.py --mode live

# Run tests
test:
	@echo "Running tests..."
	python test_entry_dete.py
	python test_dfe.py
	python test_funding.py

# Check bot health
health:
	@python -m alpha_sniper.healthcheck

# Install dependencies
install:
	pip install -r requirements.txt

# Show systemd status (if deployed)
status:
	@systemctl status alpha-sniper-sim.service || echo "Service not installed"
	@systemctl status alpha-sniper-live.service || echo "Service not installed"

# Tail logs
logs:
	@if [ -d "/var/log/alpha-sniper" ]; then \
		tail -f /var/log/alpha-sniper/alpha-sniper-sim.log; \
	else \
		tail -f logs/bot.log; \
	fi

# Clean logs and cache
clean:
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -f logs/*.log
	rm -f heartbeat.json
	@echo "Cleaned up cache and logs"

# Lint (placeholder for future)
lint:
	@echo "Linting not configured yet"
	@echo "Consider adding: flake8, black, mypy"
