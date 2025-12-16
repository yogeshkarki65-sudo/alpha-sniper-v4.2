# ⚡ Backtest Quickstart - 5 Minutes to Results

Get from zero to your first backtest in 5 minutes.

---

## 📋 Prerequisites

```bash
# Ensure you have required packages
pip install pandas numpy ccxt
```

---

## 🚀 Option A: Quick Test with Sample Data (1 minute)

Perfect for testing the system without downloading real data.

```bash
cd /home/ubuntu/alpha-sniper-v4.2

# 1. Generate sample pump data (30 days, 5 pumps)
python generate_sample_data.py --symbols TESTUSDT --days 30 --pumps 5

# 2. Run backtest
python backtest_pump.py \
    --symbols TESTUSDT \
    --start 2024-11-01 \
    --end 2024-12-01 \
    --equity 62.88 \
    --data-dir sample_data

# 3. Check results
cat backtest_results/summary_*.txt
```

**Expected Output:**
```
======================================================================
🎯 BACKTEST RESULTS
======================================================================
Total Trades: 4-6
Win Rate: ~60%
Total P&L: Variable (depends on random pumps)
```

---

## 🎯 Option B: Real Data Backtest (5 minutes)

Test your actual LIVE strategy with real MEXC data.

```bash
cd /home/ubuntu/alpha-sniper-v4.2

# 1. Download 60 days of real data (takes 2-3 min)
python download_mexc_data.py \
    --symbols SOLUSDT,SUIUSDT,1000PEPEUSDT \
    --days 60 \
    --output-dir data

# 2. Run backtest matching your LIVE .env config
python backtest_pump.py \
    --symbols SOLUSDT,SUIUSDT,1000PEPEUSDT \
    --start 2024-10-01 \
    --end 2024-12-01 \
    --equity 62.88 \
    --pump-risk 0.004 \
    --pump-min-rvol 1.5 \
    --pump-min-24h-return 0.20 \
    --pump-max-24h-return 5.00 \
    --pump-min-score 72 \
    --pump-max-hold-hours 2 \
    --pump-aggressive

# 3. Review results
cat backtest_results/summary_*.txt
head -20 backtest_results/trades_*.csv
```

**Expected Output:**
```
Total Trades: 30-50 (varies by market conditions)
Win Rate: 55-65%
Total P&L: Will reflect actual historical performance
```

---

## 📊 Understanding Your Results

### Key Metrics to Focus On

1. **Total Trades**: Should be 20-30 per month
   - Too few? Lower `--pump-min-score`
   - Too many? Increase `--pump-min-rvol`

2. **Win Rate**: Should be 50-70%
   - Below 50%? Strategy needs work
   - Above 70%? May be overfitted

3. **Average R**: Should be 0.5R+
   - Above 1.0R: Excellent
   - 0.5-1.0R: Good
   - Below 0.5R: Losing strategy

4. **Max Drawdown**: Should be under -20%
   - Above -25%? Too aggressive, reduce `--pump-risk`

---

## 🔧 Next Steps

### 1. Compare with Your LIVE Config

Extract your current config:
```bash
# Show your LIVE settings
grep "PUMP_" /etc/alpha-sniper/alpha-sniper-live.env | grep -v "^#"
```

Run backtest with **exact same values**:
```bash
python backtest_pump.py \
    --symbols <YOUR_SYMBOLS> \
    --equity <YOUR_EQUITY> \
    --pump-risk <FROM_PUMP_RISK_PER_TRADE> \
    --pump-min-rvol <FROM_PUMP_MIN_RVOL> \
    --pump-min-score <FROM_PUMP_MIN_SCORE> \
    --pump-max-hold-hours <FROM_PUMP_MAX_HOLD_HOURS>
```

### 2. Test Parameter Variations

Try 2-3 variations:
```bash
# Current config
python backtest_pump.py --pump-min-rvol 1.5 --output-dir results_base

# Looser RVOL (more trades)
python backtest_pump.py --pump-min-rvol 1.2 --output-dir results_loose

# Tighter score (fewer but better trades)
python backtest_pump.py --pump-min-score 80 --output-dir results_tight

# Compare
for dir in results_*; do
    echo "=== $dir ==="
    grep "Total Trades:" $dir/summary_*.txt
    grep "Win Rate:" $dir/summary_*.txt
    grep "Total P&L:" $dir/summary_*.txt
    echo
done
```

### 3. Analyze Individual Trades

Find your best and worst trades:
```bash
# Best trades
head -1 backtest_results/trades_*.csv > header.csv
cat header.csv > best_trades.csv
tail -n +2 backtest_results/trades_*.csv | sort -t, -k9 -nr | head -10 >> best_trades.csv

# Worst trades
cat header.csv > worst_trades.csv
tail -n +2 backtest_results/trades_*.csv | sort -t, -k9 -n | head -10 >> worst_trades.csv

# View
cat best_trades.csv
cat worst_trades.csv
```

### 4. Update LIVE Config (If Backtest is Better)

If backtest shows better results than current LIVE performance:

```bash
# 1. Stop the bot
sudo systemctl stop alpha-sniper

# 2. Edit config
sudo nano /etc/alpha-sniper/alpha-sniper-live.env

# 3. Update parameters based on backtest
# PUMP_MIN_RVOL=1.2  (if backtest with 1.2 was better)
# PUMP_MIN_SCORE=75  (adjust as needed)

# 4. Restart
sudo systemctl start alpha-sniper

# 5. Monitor
sudo journalctl -u alpha-sniper -f
```

---

## 🐛 Troubleshooting

### "No data loaded"
```bash
# Check if CSV files exist
ls -lh data/

# Expected files:
# SOLUSDT_1m.csv
# SOLUSDT_15m.csv
# SOLUSDT_1h.csv
```

**Solution:** Run `download_mexc_data.py` first.

### "Zero trades in backtest"
```bash
# Your filters are too strict. Try:
python backtest_pump.py \
    --pump-min-score 60 \  # Lower from 72
    --pump-min-rvol 1.2    # Lower from 1.5
```

### "ImportError: No module named 'ccxt'"
```bash
pip install ccxt pandas numpy
```

---

## 📚 Further Reading

- **Full Documentation**: `BACKTEST_README.md` (800+ lines)
- **Architecture Details**: `BACKTEST_SUMMARY.md`
- **Example Commands**: See "Example Workflow" in `BACKTEST_README.md`

---

## ✅ Validation Checklist

Before trusting backtest results:

- [ ] Tested with **same symbols** as you'll trade LIVE
- [ ] Used **recent data** (last 3-6 months)
- [ ] Matched **exact LIVE config** parameters
- [ ] Got **reasonable trade frequency** (20-30/month)
- [ ] **Max drawdown** acceptable for your risk tolerance
- [ ] **Win rate** and **avg R** make sense (50-70%, 0.5-1.5R)

If all checkboxes ✅, your backtest is likely realistic!

---

**That's it! You're ready to backtest. 🚀**

Questions? See `BACKTEST_README.md` for detailed guide.
