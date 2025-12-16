# 🔬 Alpha Sniper V4.2 - Pump Strategy Backtester

Professional backtesting system for the PUMP-ONLY trading strategy using historical OHLCV data.

**Key Feature: Reuses EXACT same signal logic as LIVE mode** - no code duplication, no divergence.

---

## 📋 Table of Contents

1. [Architecture](#architecture)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Detailed Usage](#detailed-usage)
5. [Data Format](#data-format)
6. [Output Files](#output-files)
7. [Example Workflow](#example-workflow)
8. [Interpreting Results](#interpreting-results)

---

## 🏗️ Architecture

### Design Principles

1. **Zero Modification to Live Code**: All backtesting logic is in new modules under `backtest/`
2. **Exact Strategy Reuse**: The `PumpEngine` class is used directly for signal generation
3. **Realistic Simulation**: Includes fees (0.1%), slippage, portfolio heat limits, daily loss limits
4. **Clean Separation**: Backtest runs offline using CSV data, no exchange API calls

### Component Breakdown

```
alpha-sniper/
├── backtest/
│   ├── __init__.py
│   ├── data_loader.py      # Loads historical OHLCV from CSV
│   ├── portfolio.py         # Simulates positions, risk management
│   └── engine.py            # Main backtesting orchestrator
├── signals/
│   └── pump_engine.py       # ✅ REUSED for signal generation
├── utils/
│   └── helpers.py           # ✅ REUSED for indicators (ATR, RVOL, RSI, etc.)
└── backtest_pump.py         # CLI entry point

backtest_results/            # Output directory
├── trades_YYYYMMDD_HHMMSS.csv
├── equity_YYYYMMDD_HHMMSS.csv
└── summary_YYYYMMDD_HHMMSS.txt
```

### How It Works

```
┌─────────────────┐
│  Historical     │
│  OHLCV CSV      │
│  Files          │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  BacktestDataLoader                     │
│  - Loads 1m, 15m, 1h candles           │
│  - Provides data at each timestamp      │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PumpEngine (REUSED FROM LIVE)          │
│  - Same filters: RVOL, 24h return       │
│  - Same scoring                         │
│  - Same stop/TP calculation             │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  BacktestPortfolio                      │
│  - Position sizing (R-based)            │
│  - Portfolio heat tracking              │
│  - Daily loss limits                    │
│  - Trailing stops                       │
│  - Max hold time                        │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Results                                │
│  - Trade log CSV                        │
│  - Equity curve CSV                     │
│  - Summary statistics                   │
└─────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites

```bash
# Python 3.8+ required
python3 --version

# Install dependencies
cd /home/ubuntu/alpha-sniper-v4.2
pip install pandas numpy ccxt
```

### Verify Installation

```bash
# Test backtester
python backtest_pump.py --help

# Test data downloader
python download_mexc_data.py --help
```

---

## 🚀 Quick Start

### Step 1: Download Historical Data

```bash
# Download 60 days of data for pump candidates
python download_mexc_data.py \
    --symbols SOLUSDT,SUIUSDT,1000PEPEUSDT,BARKUSDT \
    --days 60 \
    --output-dir data
```

**What this does:**
- Downloads 1m, 15m, 1h OHLCV candles
- Saves as `data/SOLUSDT_1m.csv`, `data/SOLUSDT_15m.csv`, etc.
- Uses MEXC spot market data

### Step 2: Run Backtest

```bash
# Backtest with your LIVE config parameters
python backtest_pump.py \
    --symbols SOLUSDT,SUIUSDT,1000PEPEUSDT \
    --start 2025-10-01 \
    --end 2025-12-01 \
    --equity 62.88 \
    --pump-risk 0.004 \
    --pump-min-rvol 1.5 \
    --pump-min-24h-return 0.20 \
    --pump-max-24h-return 5.00 \
    --pump-min-score 72 \
    --pump-max-hold-hours 2
```

### Step 3: Review Results

```bash
# Check output directory
ls -lh backtest_results/

# View summary
cat backtest_results/summary_*.txt

# Analyze trades
head -20 backtest_results/trades_*.csv
```

---

## 📚 Detailed Usage

### Command Line Arguments

```bash
python backtest_pump.py --help
```

#### Required Arguments

- `--symbols`: Comma-separated symbols (e.g., `BTCUSDT,ETHUSDT,SOLUSDT`)
- `--start`: Start date (`YYYY-MM-DD` or ISO timestamp)
- `--end`: End date (`YYYY-MM-DD` or ISO timestamp)

#### Strategy Parameters

| Argument | Default | Description |
|----------|---------|-------------|
| `--equity` | 62.88 | Starting equity in USDT |
| `--pump-risk` | 0.004 | Risk per trade (0.4%) |
| `--pump-max-concurrent` | 1 | Max concurrent positions |
| `--pump-min-rvol` | 1.5 | Minimum relative volume |
| `--pump-min-24h-return` | 0.20 | Min 24h return (20%) |
| `--pump-max-24h-return` | 5.00 | Max 24h return (500%) |
| `--pump-min-volume` | 500000 | Min 24h quote volume (USDT) |
| `--pump-min-score` | 72 | Minimum signal score |
| `--pump-max-hold-hours` | 2.0 | Max hold time (hours) |
| `--pump-aggressive` | false | Enable aggressive mode |

#### Risk Management

| Argument | Default | Description |
|----------|---------|-------------|
| `--max-portfolio-heat` | 0.008 | Max portfolio heat (0.8%) |
| `--max-daily-loss` | 0.02 | Max daily loss (2%) |
| `--trailing-stop` | 0.35 | Trailing stop (35%) |

#### Output Control

| Argument | Default | Description |
|----------|---------|-------------|
| `--data-dir` | data | CSV data directory |
| `--output-dir` | backtest_results | Results directory |
| `--scan-interval` | 30 | Scan frequency (minutes) |
| `--quiet` | false | Suppress detailed logs |

---

## 📊 Data Format

### Required CSV Files

For each symbol, you need 3 CSV files:

```
data/
├── BTCUSDT_1m.csv
├── BTCUSDT_15m.csv
├── BTCUSDT_1h.csv
├── ETHUSDT_1m.csv
├── ETHUSDT_15m.csv
├── ETHUSDT_1h.csv
...
```

### CSV Format

```csv
timestamp,open,high,low,close,volume
1609459200000,29000.0,29500.0,28800.0,29200.0,1500.5
1609459260000,29200.0,29300.0,29100.0,29250.0,1200.3
...
```

**Requirements:**
- `timestamp`: Unix timestamp in milliseconds
- `open`, `high`, `low`, `close`: Price values
- `volume`: Volume in base asset

**Notes:**
- All numeric values
- Sorted by timestamp (ascending)
- No missing candles (backtester will handle gaps gracefully)

---

## 📁 Output Files

### 1. Trade Log (`trades_YYYYMMDD_HHMMSS.csv`)

Detailed record of every trade:

```csv
timestamp_open,timestamp_close,symbol,side,entry_price,exit_price,stop_loss,size_usd,pnl_usd,pnl_pct,r_multiple,hold_minutes,exit_reason,score,rvol,return_24h,volume_24h
2025-10-15T08:30:00Z,2025-10-15T09:45:00Z,SOL/USDT,long,145.20,148.50,143.10,25.60,5.80,2.27,1.57,75,TP 2R hit,85,2.3,0.45,850000
```

**Columns:**
- `timestamp_open/close`: Entry/exit times (ISO format)
- `symbol`: Trading pair
- `entry_price/exit_price`: Prices
- `stop_loss`: Initial stop
- `size_usd`: Position size in USDT
- `pnl_usd/pnl_pct`: P&L in dollars and percentage
- `r_multiple`: Risk-reward multiple (2R = 2x initial risk)
- `hold_minutes`: Position duration
- `exit_reason`: Why closed (`TP 2R hit`, `Stop hit`, `Max hold time`, `Trailing stop hit`)
- `score/rvol/return_24h/volume_24h`: Signal metrics

### 2. Equity Curve (`equity_YYYYMMDD_HHMMSS.csv`)

Account balance over time:

```csv
timestamp,equity,pnl,symbol
2025-10-15T09:45:00Z,68.68,5.80,SOL/USDT
2025-10-16T14:20:00Z,66.18,-2.50,SUI/USDT
```

**Use for:**
- Plotting equity curve
- Analyzing drawdown periods
- Visualizing growth

### 3. Summary (`summary_YYYYMMDD_HHMMSS.txt`)

Human-readable statistics:

```
======================================================================
PUMP BACKTEST SUMMARY
======================================================================

Period: 2025-10-01 to 2025-12-01
Symbols: SOL/USDT, SUI/USDT, 1000PEPE/USDT
Starting Equity: $62.88

Total Trades: 45
Wins / Losses: 28W / 17L
Win Rate: 62.2%
Average R: 0.85R
Avg Win: $8.50
Avg Loss: $-3.20

Final Equity: $95.44
Total P&L: $+32.56 (+51.8%)
Total Fees: $4.50
Max Drawdown: -8.5%

Best Trade: SOL/USDT $15.20
Worst Trade: 1000PEPE/USDT $-5.80

Strategy Parameters:
  PUMP_RISK_PER_TRADE: 0.004
  PUMP_MIN_RVOL: 1.5
  PUMP_MIN_24H_RETURN: 0.2
  ...
```

---

## 🎯 Example Workflow

### Scenario: Testing Current LIVE Config

**Goal:** Backtest your exact LIVE strategy to see historical performance.

```bash
# 1. Download recent data for pump candidates
python download_mexc_data.py \
    --symbols SOLUSDT,SUIUSDT,BARKUSDT,1000PEPEUSDT,WIFUSDT \
    --days 90 \
    --output-dir data

# 2. Run backtest matching LIVE .env
python backtest_pump.py \
    --symbols SOLUSDT,SUIUSDT,BARKUSDT,1000PEPEUSDT,WIFUSDT \
    --start 2025-09-01 \
    --end 2025-12-01 \
    --equity 62.88 \
    --pump-risk 0.004 \
    --pump-max-concurrent 1 \
    --pump-min-rvol 1.5 \
    --pump-min-24h-return 0.20 \
    --pump-max-24h-return 5.00 \
    --pump-min-volume 500000 \
    --pump-min-score 72 \
    --pump-max-hold-hours 2 \
    --pump-aggressive \
    --max-portfolio-heat 0.008 \
    --max-daily-loss 0.02 \
    --trailing-stop 0.35 \
    --scan-interval 30

# 3. Review results
cat backtest_results/summary_*.txt

# 4. Analyze trade-by-trade
head -30 backtest_results/trades_*.csv
```

### Scenario: Testing Parameter Sensitivity

**Goal:** See if looser RVOL filter increases trades without hurting win rate.

```bash
# Test 1: RVOL 1.5 (current)
python backtest_pump.py \
    --symbols SOLUSDT \
    --start 2025-10-01 \
    --end 2025-12-01 \
    --equity 62.88 \
    --pump-min-rvol 1.5 \
    --output-dir backtest_results/rvol_1.5

# Test 2: RVOL 1.2 (looser)
python backtest_pump.py \
    --symbols SOLUSDT \
    --start 2025-10-01 \
    --end 2025-12-01 \
    --equity 62.88 \
    --pump-min-rvol 1.2 \
    --output-dir backtest_results/rvol_1.2

# Compare
echo "RVOL 1.5:"
grep "Total Trades:" backtest_results/rvol_1.5/summary_*.txt
grep "Win Rate:" backtest_results/rvol_1.5/summary_*.txt

echo "RVOL 1.2:"
grep "Total Trades:" backtest_results/rvol_1.2/summary_*.txt
grep "Win Rate:" backtest_results/rvol_1.2/summary_*.txt
```

---

## 📈 Interpreting Results

### Key Metrics

#### Total Trades
- **What it means**: Number of positions taken during backtest period
- **Good range**: 30-60 trades per month for pump strategy
- **Red flags**:
  - < 10 trades/month: Filters too tight, missing opportunities
  - > 100 trades/month: Filters too loose, overtrading

#### Win Rate
- **What it means**: Percentage of profitable trades
- **Good range**: 50-70% for pump strategy
- **Red flags**:
  - < 45%: Strategy not selective enough
  - > 75%: May be curve-fitted, won't hold in live

#### Average R Multiple
- **What it means**: Average risk-reward ratio achieved
- **Good range**: 0.5R - 1.5R
- **How to interpret**:
  - > 1.0R: Winning more than risking on average (excellent)
  - 0.5R - 1.0R: Positive expectancy (good)
  - < 0.5R: Losing strategy (adjust parameters)

#### Max Drawdown
- **What it means**: Largest peak-to-trough equity drop
- **Good range**: -10% to -20%
- **Red flags**:
  - > -25%: Too aggressive, reduce risk per trade
  - < -5%: Sample size too small or unrealistic

#### Avg Win vs Avg Loss
- **What it means**: Size of average winning vs losing trade
- **Good ratio**: 2:1 or better (avg win = 2× avg loss)
- **Pump strategy typically**: 2.5:1 to 3:1 due to momentum

### Example Analysis

```
Total Trades: 45
Win Rate: 62.2%
Average R: 0.85R
Max Drawdown: -8.5%
Total P&L: +51.8%
```

**Interpretation:**
- ✅ Good trade frequency (45 trades in 2 months ≈ 22/month)
- ✅ Solid win rate (62% > 50%)
- ✅ Positive expectancy (0.85R means winning 85% of risk per trade)
- ✅ Reasonable drawdown (-8.5%)
- ✅ Strong returns (+51.8% on $62 account)

**Verdict**: This config is likely profitable in LIVE if:
1. Market conditions remain similar
2. Execution matches backtest (slippage, fees realistic)
3. You can psychologically handle -8.5% drawdowns

### Red Flags to Watch For

❌ **Zero or Very Few Trades**
```
Total Trades: 3
```
**Problem**: Filters too strict, missing pumps
**Fix**: Lower `--pump-min-score` or `--pump-min-rvol`

❌ **High Win Rate, Low R Multiple**
```
Win Rate: 85%
Average R: 0.2R
```
**Problem**: Taking profits too early, cutting winners short
**Fix**: Let winners run, increase `--pump-max-hold-hours`

❌ **Many Trades, Low Win Rate**
```
Total Trades: 200
Win Rate: 35%
```
**Problem**: Chasing low-quality pumps
**Fix**: Increase `--pump-min-score` or `--pump-min-rvol`

❌ **Huge Drawdown**
```
Max Drawdown: -45%
```
**Problem**: Position sizing too aggressive
**Fix**: Reduce `--pump-risk` from 0.004 to 0.002

---

## 💡 Tips & Best Practices

### 1. Match Your LIVE Config

Always backtest with the **exact parameters** from your `/etc/alpha-sniper/alpha-sniper-live.env`:

```bash
# Extract from .env
PUMP_RISK_PER_TRADE=0.004
PUMP_MIN_RVOL=1.5
PUMP_MIN_24H_RETURN=0.20
...

# Use same values in backtest
python backtest_pump.py \
    --pump-risk 0.004 \
    --pump-min-rvol 1.5 \
    --pump-min-24h-return 0.20 \
    ...
```

### 2. Test Multiple Market Conditions

Run backtests across different periods:

```bash
# Bull market (Oct-Nov 2024)
python backtest_pump.py --start 2024-10-01 --end 2024-11-30 ...

# Bear market (Aug-Sep 2024)
python backtest_pump.py --start 2024-08-01 --end 2024-09-30 ...

# Sideways (Jun-Jul 2024)
python backtest_pump.py --start 2024-06-01 --end 2024-07-31 ...
```

### 3. Focus on Recent Data

Crypto markets evolve quickly. Recent data (last 3-6 months) is more relevant than 1-year-old data.

### 4. Don't Overfit

If you run 50 backtests tweaking parameters, you'll find one that looks amazing. That's curve-fitting. Stick to 2-3 variations max.

### 5. Account for Slippage

Backtester assumes you enter at exact signal price. In LIVE:
- Fast pumps have 0.1-0.5% slippage
- Illiquid coins have 1-2% slippage
- Add mental buffer: If backtest shows +50%, expect +40% live

---

## ❓ FAQ

**Q: Can I backtest non-pump strategies?**
A: Current backtester only supports PUMP-ONLY mode. For multi-strategy, you'd need to extend the code.

**Q: Why are my backtest results different from LIVE?**
A: Common reasons:
1. Slippage (backtest assumes perfect fills)
2. Market regime changed since backtest period
3. Different symbols (backtest only tests loaded symbols)
4. Fees/spreads (backtester uses 0.1% fee approximation)

**Q: How much historical data do I need?**
A: Minimum 60 days, ideally 90-180 days for statistical significance.

**Q: Can I backtest with incomplete data?**
A: Yes, but trades will only occur when all 3 timeframes (1m, 15m, 1h) have data.

**Q: Does backtester simulate Entry-DETE?**
A: No, it assumes immediate entry at signal price. Entry-DETE waits for dips, which would improve results slightly.

**Q: What about trailing stops?**
A: Implemented! The backtester applies trailing stops based on `--trailing-stop` parameter.

---

## 🔧 Troubleshooting

### "No data loaded"

```
❌ No data loaded. Please check:
   - CSV files exist in data/
```

**Solution:**
1. Run `download_mexc_data.py` first
2. Verify files exist: `ls -lh data/`
3. Check filenames match: `SYMBOLNAME_timeframe.csv` (e.g., `BTCUSDT_1m.csv`)

### "AttributeError: module 'helpers' has no attribute 'calculate_spread_pct'"

**Solution:**
Add missing helper function to `utils/helpers.py`:

```python
def calculate_spread_pct(bid: float, ask: float) -> float:
    """Calculate spread percentage"""
    if bid == 0:
        return 999
    return ((ask - bid) / bid) * 100
```

### Backtest runs but shows 0 trades

**Possible causes:**
1. Filters too strict (lower `--pump-min-score`)
2. No pumps in data period (try different date range)
3. Volume threshold too high (lower `--pump-min-volume`)
4. Symbols don't have enough data (check CSV completeness)

---

## 📝 Next Steps

1. **Download data** for your target symbols
2. **Run baseline backtest** with current LIVE config
3. **Analyze results** - are you getting enough trades? Good win rate?
4. **Test 2-3 variations** - try looser/tighter filters
5. **Choose best config** - balance trade frequency vs quality
6. **Update LIVE .env** if backtest beats current config

Remember: Backtesting shows what **would have happened**. It doesn't guarantee future results. Use it as a tool to:
- Validate your strategy logic
- Find optimal parameters
- Understand expected drawdowns
- Set realistic profit expectations

---

## 📞 Support

Issues or questions? Check:
1. This README (you are here)
2. Code comments in `backtest/*.py`
3. Main project docs in `/home/ubuntu/alpha-sniper-v4.2/alpha-sniper/`

---

**Happy Backtesting! 🚀**
