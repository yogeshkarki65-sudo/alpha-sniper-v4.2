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
