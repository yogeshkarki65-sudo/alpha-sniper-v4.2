# Alpha Sniper V4.2 - Complete Technical Documentation

## 🏗️ ARCHITECTURE OVERVIEW

### System Design
The bot is a Python-based cryptocurrency trading system that runs on a VPS as a systemd service. It operates in a continuous loop, scanning markets, generating signals, and managing positions.

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEMD SERVICE                          │
│  Service: alpha-sniper-live.service                         │
│  User: ubuntu                                               │
│  Auto-restart on failure                                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    MAIN BOT LOOP                            │
│  File: /opt/alpha-sniper/alpha-sniper/main.py              │
│                                                             │
│  1. Detect market regime (STRONG_BULL, SIDEWAYS, etc.)     │
│  2. Manage existing positions (check exits)                │
│  3. Scan market (generate signals)                         │
│  4. Process signals (open new positions)                   │
│  5. Sleep and repeat                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 FILE LOCATIONS & PERMISSIONS

### Critical Directories

```bash
/opt/alpha-sniper/                    # Main application directory
├── alpha-sniper/                     # Python source code
│   ├── main.py                       # Main bot loop (755)
│   ├── config.py                     # Configuration loader (755)
│   ├── regime_detector.py            # Market regime detection (755)
│   ├── scanner.py                    # Signal generation (755)
│   ├── risk_engine.py                # Position management (755)
│   ├── engines/                      # Trading engines
│   │   ├── pump_engine.py            # Pump detection engine (755)
│   │   ├── long_engine.py            # Long position engine (755)
│   │   └── short_engine.py           # Short position engine (755)
│   └── utils/
│       ├── telegram_alerts.py        # Telegram notifications (755)
│       └── exchange_utils.py         # MEXC API wrapper (755)
├── deployment/                       # Deployment scripts
│   ├── verify_all.sh                 # Health check script (755)
│   ├── fix_critical_issues.sh        # Fix common issues (755)
│   └── clear_old_positions.sh        # Clear old positions (755)
├── logs/                             # Log files (777 - writable!)
│   └── bot.log                       # Main log file
├── venv/                             # Python virtual environment (755)
└── requirements.txt                  # Python dependencies

/var/lib/alpha-sniper/                # State directory (777 - writable!)
└── positions.json                    # Open positions state (664)

/etc/alpha-sniper/                    # Configuration directory (755)
└── alpha-sniper-live.env             # Environment variables (600 - secure!)

/etc/systemd/system/                  # System services
└── alpha-sniper-live.service         # Systemd service file (644)
```

### Permission Requirements

**Why specific permissions?**

1. **777 on /var/lib/alpha-sniper/** - Bot needs to create temp files (.tmp) for atomic writes
2. **777 on /opt/alpha-sniper/logs/** - Python logging needs to create/append log files
3. **600 on env file** - Contains API keys (only ubuntu user can read)
4. **755 on Python files** - Readable/executable by service, not writable by others

---

## 🔄 HOW THE BOT WORKS (Step by Step)

### Main Loop Flow

```python
# Pseudo-code of main.py run() method

while True:
    # STEP 1: REGIME DETECTION
    regime = regime_detector.detect()  # Returns: STRONG_BULL, SIDEWAYS, MILD_BEAR, or FULL_BEAR
    # Uses: BTC dominance, price trends, volatility

    # STEP 2: MANAGE EXISTING POSITIONS
    for position in open_positions:
        check_if_should_exit(position)
        # Exit conditions:
        #   - Hit target price
        #   - Hit stop loss
        #   - Max hold time reached (24h for pump)
        #   - Synthetic watchdog triggered (max loss exceeded)

    # STEP 3: SCAN MARKET
    signals = scanner.scan()
    # Scanner checks 800 symbols (SCAN_UNIVERSE_MAX)
    # Applies filters:
    #   - Volume > minimum
    #   - Spread < maximum
    #   - Engine-specific patterns

    # STEP 4: PROCESS SIGNALS (ENTRY LOGIC)
    for signal in signals:
        if signal.score >= MIN_SCORE_PUMP:  # 0.75 threshold
            if passes_risk_checks(signal):
                open_position(signal)

    # STEP 5: SLEEP
    sleep(SCAN_INTERVAL)  # Default: 5 minutes
```

---

## 💰 ENTRY POINT LOGIC (How Bot Buys)

### Entry Decision Tree

```
Signal Generated by Engine
         ↓
    Score >= 0.75?
         ↓ YES
    Portfolio Risk OK?
         ↓ YES
    Max Positions Not Reached?
         ↓ YES
    Sufficient Balance?
         ↓ YES
    ┌──────────────┐
    │  OPEN TRADE  │
    └──────────────┘
```

### Entry Parameters (from config)

```bash
# Signal Quality
MIN_SCORE_PUMP=0.75              # Minimum signal quality (0.0-1.0)
                                  # Higher = stricter, fewer trades
                                  # 0.75 = top 25% of signals only

# Position Sizing
POSITION_SIZE_PCT_SIDEWAYS=0.10  # 10% of portfolio per trade
CAPITAL_AT_RISK_PCT=0.10         # Max 10% of capital at risk total

# Risk Per Trade
PUMP_MAX_LOSS_PCT=0.02           # Max 2% loss per pump trade
                                  # Stop loss = entry - 2%

# Example:
# Portfolio: $1000
# Position size: $100 (10%)
# Stop loss: entry - 2% = risk $2 per trade
```

### Pump Engine Entry Logic (pump_engine.py)

```python
def analyze(symbol, regime):
    """
    Pump detection logic:
    1. Volume spike (recent volume >> average)
    2. Price acceleration (sharp upward movement)
    3. Momentum indicators (RSI, MACD confirming)
    4. Liquidity check (can we exit without slippage?)
    """

    # Calculate components
    volume_score = current_volume / avg_volume  # Want: >3x
    price_score = price_change_1h               # Want: >5%
    momentum_score = rsi + macd_signal          # Want: strong momentum

    # Combine into final score
    final_score = weighted_average([
        volume_score * 0.4,   # 40% weight on volume
        price_score * 0.35,   # 35% weight on price
        momentum_score * 0.25 # 25% weight on momentum
    ])

    return {
        'score': final_score,
        'entry': current_price,
        'target': calculate_target(),  # Based on volatility
        'stop': entry * (1 - PUMP_MAX_LOSS_PCT)  # 2% below entry
    }
```

---

## 🎯 EXIT POINT LOGIC (How Bot Sells)

### Exit Decision Tree

```
Position Open
     ↓
  ┌──────────────────────────────┐
  │  Continuous Monitoring       │
  │  (Every 1 second - watchdog) │
  └──────────────────────────────┘
           ↓
  ┌─────────────────────┐
  │  Exit Triggered?    │
  └─────────────────────┘
           ↓
    ┌─────┴─────┐
    │           │
  YES          NO
    │           │
    ↓           ↓
  EXIT       CONTINUE
```

### Exit Conditions (Priority Order)

```python
# 1. SYNTHETIC STOP WATCHDOG (Highest Priority)
# Runs every 1 second in background
if current_price <= entry * (1 - PUMP_MAX_LOSS_PCT):
    # INSTANT MARKET SELL
    # Loss: -2% (or regime-specific override)
    exit_reason = "Max loss triggered (synthetic watchdog)"

# 2. TARGET PRICE REACHED
if current_price >= target_price:
    # MARKET SELL
    # Win: Variable based on target (typically +3% to +10%)
    exit_reason = "Target reached"

# 3. EXCHANGE STOP LOSS
if stop_loss_order_filled:
    # ALREADY SOLD BY EXCHANGE
    # Loss: -2% (or slippage)
    exit_reason = "Stop loss hit"

# 4. MAX HOLD TIME
if time_held >= MAX_HOLD_HOURS_PUMP:  # 24 hours
    # MARKET SELL (close at market price)
    # P&L: Whatever current price is
    exit_reason = "Max hold time (24h)"

# 5. PARTIAL TAKE PROFIT (Optional)
if current_price >= entry * 1.05:  # +5%
    sell_portion = 50%  # Lock in partial gains
    exit_reason = "Partial TP (50% at +5%)"
```

### Exit Parameters

```bash
MAX_HOLD_HOURS_PUMP=24           # Maximum hold time
                                  # Was 1.5h (too short!)
                                  # Now 24h (optimized)

PUMP_MAX_LOSS_PCT=0.02           # Hard stop at -2%
                                  # Enforced by watchdog

# Regime-specific overrides (optional):
PUMP_MAX_LOSS_PCT_STRONG_BULL=0.03  # Allow -3% in bull market
PUMP_MAX_LOSS_PCT_FULL_BEAR=0.01    # Tight -1% in bear market
```

---

## 🛡️ RISK MANAGEMENT (Synthetic Watchdog)

### What is the Synthetic Watchdog?

```python
# File: alpha-sniper/risk_engine.py

async def synthetic_stop_watchdog():
    """
    Independent async loop that monitors positions EVERY 1 SECOND

    Why needed?
    - Exchange stop-loss can be rejected/cancelled
    - Ensures position NEVER loses more than configured max
    - Virtual stop enforced in code (can't be cancelled)
    """

    while bot_running:
        for position in pump_positions:
            max_loss_pct = config.get_pump_max_loss_pct(position.regime)
            hard_stop_price = position.entry * (1 - max_loss_pct)

            current_price = get_current_price(position.symbol)

            if current_price <= hard_stop_price:
                # INSTANT MARKET SELL
                logger.critical(f"🚨 PUMP_MAX_LOSS triggered: {position.symbol}")
                force_close_position(position, reason="synthetic_watchdog")

        await asyncio.sleep(1)  # Check every second
```

**Key Features:**
- ✅ Runs independently of main loop
- ✅ 1-second monitoring interval
- ✅ Cannot be disabled or cancelled
- ✅ Per-regime configurable limits
- ✅ Instant market sell (no waiting for exchange SL)

---

## 📊 ENVIRONMENT OPTIMIZER EXPLAINED

### What It Does

```bash
# File: deployment/alpha-sniper-live.env.OPTIMIZED
# Created from analysis of 60 trades showing:
#   - Win rate: 30%
#   - 98% hit time limit (1.5h-3h)
#   - Average hold: 2.8h
#   - No trades reached targets
```

### Key Optimizations Made

| Setting | Old Value | New Value | Reason |
|---------|-----------|-----------|--------|
| `MAX_HOLD_HOURS_PUMP` | 1.5h | 24h | Positions needed more time to reach targets |
| `MIN_SCORE_PUMP` | 0.7 | 0.75 | Filter out lower-quality signals |
| `PUMP_ONLY` | false | true | Disable other engines, focus on pump |
| `POSITION_SIZE_PCT` | 0.05 | 0.10 | Increase position size (better R:R) |
| `TELEGRAM_SCAN_SUMMARY` | false | true | Enable scan summaries for visibility |

### Why These Changes?

**1. MAX_HOLD_HOURS_PUMP: 1.5h → 24h**
```
Problem: 98% of trades hit 1.5h time limit before reaching targets
Analysis: Pump movements can take 6-12 hours to fully develop
Solution: Allow 24h for trades to reach targets
Impact: More trades reach target price instead of timing out
```

**2. MIN_SCORE_PUMP: 0.7 → 0.75**
```
Problem: 30% win rate suggests quality issues
Analysis: Lower-scored signals (0.7-0.75) had worse performance
Solution: Only trade top 25% of signals (0.75+)
Impact: Fewer trades but higher quality/win rate
```

**3. PUMP_ONLY: true**
```
Problem: All 60 trades were LONG engine (pump disabled?)
Analysis: Mixed signals from multiple engines caused confusion
Solution: Focus exclusively on pump detection
Impact: Clearer strategy, better execution
```

---

## 🔧 CONFIGURATION FILES EXPLAINED

### /etc/alpha-sniper/alpha-sniper-live.env

```bash
# EXCHANGE CREDENTIALS
MEXC_API_KEY=your_api_key_here     # DO NOT SHARE!
MEXC_SECRET_KEY=your_secret_here   # DO NOT SHARE!

# TRADING MODE
LIVE_TRADING=true                   # true = real money, false = paper trading
PUMP_ONLY=true                      # Only use pump engine

# REGIME DETECTION
REGIME_AUTO_DETECT=true             # Auto-detect market conditions
CURRENT_REGIME=SIDEWAYS             # Manual override (if auto=false)

# PUMP ENGINE SETTINGS
MIN_SCORE_PUMP=0.75                 # Signal quality threshold (0.0-1.0)
MAX_HOLD_HOURS_PUMP=24              # Max time to hold position
PUMP_MAX_LOSS_PCT=0.02              # Max loss per trade (2%)
PUMP_MAX_LOSS_WATCHDOG_INTERVAL=1.0 # Watchdog check interval (seconds)

# POSITION SIZING
POSITION_SIZE_PCT_SIDEWAYS=0.10     # 10% per trade in sideways market
CAPITAL_AT_RISK_PCT=0.10            # Max 10% total portfolio risk

# SCANNING
SCAN_INTERVAL_SECONDS=300           # Scan every 5 minutes
SCAN_UNIVERSE_MAX=800               # Check top 800 symbols by volume

# TELEGRAM NOTIFICATIONS
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_SCAN_SUMMARY=true          # Send scan summaries
TELEGRAM_TRADE_ALERTS=true          # Send trade entry/exit alerts
TELEGRAM_WHY_NO_TRADE=true          # Explain why no trade opened

# LOGGING
LOG_LEVEL=INFO                      # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

---

## 🎯 IMPROVING ENTRY/EXIT POINTS

### Current Entry Logic Issues

```python
# Current problem areas for discussion:

1. SIGNAL SCORING
   Current: Simple weighted average
   Issue: Doesn't account for market regime differences
   Improvement ideas:
   - Dynamic weights based on regime
   - Machine learning score prediction
   - Backtested optimal thresholds per regime

2. ENTRY TIMING
   Current: Enters immediately when signal >= 0.75
   Issue: May enter too early in pump development
   Improvement ideas:
   - Wait for confirmation candle
   - Enter on pullback (better price)
   - Ladder entries (scale in)

3. POSITION SIZING
   Current: Fixed 10% per trade
   Issue: Doesn't adjust for signal confidence
   Improvement ideas:
   - Size proportional to score (0.75=5%, 0.9=15%)
   - Reduce size in FULL_BEAR regime
   - Increase size for high-conviction setups
```

### Current Exit Logic Issues

```python
# Current problem areas for discussion:

1. TARGET CALCULATION
   Current: Static target based on historical volatility
   Issue: Doesn't adapt to current market conditions
   Improvement ideas:
   - Dynamic targets based on regime
   - Fibonacci extensions
   - Trailing stop once in profit

2. STOP LOSS PLACEMENT
   Current: Fixed 2% below entry
   Issue: May be too tight or too loose depending on volatility
   Improvement ideas:
   - ATR-based stops (adjust for volatility)
   - Support/resistance-based stops
   - Regime-specific stops (tighter in bear, looser in bull)

3. TIME-BASED EXIT
   Current: Hard 24h cutoff
   Issue: Arbitrary timeframe, may exit winning trades early
   Improvement ideas:
   - No time limit if in profit
   - Shorter time limit if underwater
   - Extend time if near target
```

---

## 📈 DATA FOR OPTIMIZATION

### Historical Performance (Last 60 Trades)

```
Total Trades: 60
Win Rate: 30% (18W / 42L)
Average Hold Time: 2.8 hours
Max Hold Time: 22.7 hours

Exit Reasons:
- 49 trades: Max hold time (1.5h)
- 10 trades: Max hold time (3.0h)
- 1 trade: Stop loss hit
- 0 trades: Target reached

Key Insight: NO TRADES REACHED TARGET!
Problem: Either targets too aggressive or hold time too short
```

### Signal Quality Distribution

```
Score Range    | Count | Win Rate
---------------|-------|----------
0.90 - 1.00   |   3   |  67%  ← Best performing
0.80 - 0.89   |  12   |  42%
0.75 - 0.79   |  18   |  28%  ← New threshold
0.70 - 0.74   |  27   |  19%  ← Filtered out now
```

### Regime Performance

```
Regime        | Trades | Win Rate | Avg Hold
--------------|--------|----------|----------
STRONG_BULL   |   8    |  50%     |  2.1h
SIDEWAYS      |  41    |  27%     |  2.9h  ← Current regime
MILD_BEAR     |   9    |  22%     |  3.2h
FULL_BEAR     |   2    |  0%      |  3.0h
```

---

## 🚀 QUESTIONS FOR OPTIMIZATION DISCUSSION

### Entry Points
1. Should we wait for confirmation before entering? (e.g., 2 consecutive candles showing pump)
2. Should entry size scale with signal confidence? (0.75 = 5%, 0.90 = 15%)
3. Should we enter on pullbacks instead of breakouts?
4. Should we use limit orders vs market orders for better prices?

### Exit Points
1. Should we use trailing stops once in profit?
2. Should we scale out (sell portions at multiple targets)?
3. Should we remove time limit if trade is profitable?
4. Should we tighten stop loss as trade moves in our favor?

### Risk Management
1. Current 2% max loss - is this optimal for all regimes?
2. Should we reduce position size in SIDEWAYS regime? (low win rate)
3. Should we increase max loss tolerance in STRONG_BULL? (give room to run)
4. Should we exit all positions when regime changes to FULL_BEAR?

### Signal Quality
1. Current 0.75 threshold - should we make it higher in SIDEWAYS?
2. Should we add more filters (e.g., recent news, social sentiment)?
3. Should we backtest different scoring algorithms?
4. Should we use machine learning for signal scoring?

---

## 📝 FILES TO MODIFY FOR IMPROVEMENTS

```
Entry Logic:
- /opt/alpha-sniper/alpha-sniper/engines/pump_engine.py (line 150-300)
- /opt/alpha-sniper/alpha-sniper/scanner.py (line 80-120)

Exit Logic:
- /opt/alpha-sniper/alpha-sniper/risk_engine.py (line 200-400)
- /opt/alpha-sniper/alpha-sniper/main.py (line 180-250)

Configuration:
- /etc/alpha-sniper/alpha-sniper-live.env (all settings)
- /opt/alpha-sniper/alpha-sniper/config.py (add new params)

Watchdog:
- /opt/alpha-sniper/alpha-sniper/risk_engine.py (line 50-100)
```

---

## 🔍 CURRENT STATUS SUMMARY

✅ **Working Correctly:**
- Service running 24/7 (auto-restart on failure)
- Watchdog protecting positions (1-second monitoring)
- Scans running every ~7 minutes
- Telegram notifications working
- Permissions all correct
- Optimized config deployed

⚠️ **Needs Attention:**
- No pump trades in last 24h (0.75 threshold may be too strict, or market conditions not suitable)
- Scan summaries not being sent to Telegram (code issue - investigating)
- 30% win rate (needs strategy improvement)
- 0 trades reaching targets (targets too aggressive or hold time too short)

🎯 **Next Steps:**
1. Wait for scan summary fix to deploy
2. Monitor for pump signals over 24-48 hours
3. Analyze entry/exit performance
4. Discuss improvements with ChatGPT/advisor
5. Backtest proposed changes
6. Implement and deploy improvements

---

END OF DOCUMENTATION
