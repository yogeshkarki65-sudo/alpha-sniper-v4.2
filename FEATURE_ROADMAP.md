# Alpha Sniper v4.2 - Feature Roadmap & Implementation Plan

**Date:** 2025-12-29
**Current Status:** Async infrastructure deployed, trading engines NOT integrated yet
**Next Phase:** Integrate trading logic + Add new features

---

## 🚨 CRITICAL DISCOVERY

**The async bot is currently NOT trading!**

Line 172-183 in `app_async.py` shows:
```python
# Step 3: TODO - Run trading engines on market_data
# This is where you would integrate your existing engine logic
# For now, just log that we have the data
logger.info(f"Market data ready for engines: {len(market_data)} symbols")
```

**What the async bot DOES:**
- ✅ Scans 80 symbols every 60 seconds
- ✅ Fetches OHLCV data (4.2s per scan)
- ✅ Computes indicators (RSI, EMA, volume, etc.)
- ✅ Sends Telegram notifications

**What the async bot DOES NOT DO (yet):**
- ❌ Run pump detection engine
- ❌ Generate trading signals
- ❌ Place orders
- ❌ Manage positions
- ❌ Execute risk management

**Existing engines (not integrated):**
- `signals/pump_engine.py` - Pump detection logic
- `signals/long_engine.py` - Long position engine
- `signals/short_engine.py` - Short position engine
- `signals/scanner.py` - Signal scanning
- `risk_engine.py` - Risk management

---

## 📋 PHASE 1: Core Trading Integration (MUST DO FIRST)

### Priority 1A: Integrate Pump Detection Engine
**Why:** This is your primary strategy - must work before going full LIVE

**Tasks:**
1. Port `signals/pump_engine.py` to async
2. Integrate into `app_async.py` trading loop
3. Test signal generation with historical data
4. Validate pump scores match sync bot

**Expected outcome:**
- Bot detects pump signals during scans
- Telegram alerts when pumps detected
- Signals logged to database

**Implementation complexity:** Medium (2-3 days)

---

### Priority 1B: Integrate Order Placement
**Why:** Can't trade without placing orders!

**Tasks:**
1. Port order placement logic from `main.py` to async
2. Implement async order execution via `AsyncExchange`
3. Add order validation (liquidity, spread, viability)
4. Implement retry logic with exponential backoff

**Expected outcome:**
- Bot places orders when signals trigger
- Orders respect risk limits
- Telegram notifies on order placement

**Implementation complexity:** Medium (2-3 days)

---

### Priority 1C: Integrate Risk Management
**Why:** Prevents blowing up your account

**Tasks:**
1. Port `risk_engine.py` to async
2. Implement position sizing
3. Add portfolio heat tracking
4. Enforce max concurrent positions limit

**Expected outcome:**
- Position sizes calculated correctly
- Portfolio heat < 1.2%
- Max 5 concurrent positions enforced

**Implementation complexity:** Medium-High (3-4 days)

---

### Priority 1D: Position Management
**Why:** Need to track and close positions

**Tasks:**
1. Create async position tracker
2. Implement stop-loss monitoring
3. Add take-profit logic
4. Create position database table

**Expected outcome:**
- Open positions tracked in DB
- Stop-losses executed automatically
- Take-profits hit automatically
- P&L calculated in real-time

**Implementation complexity:** High (4-5 days)

---

## 🚀 PHASE 2: Go Full LIVE (After Phase 1 Complete)

### Remove LIVE_TEST_MODE
**Why:** Trade with full capital once validated

**Tasks:**
1. Backup database before change
2. Remove or set `ALPHA_LIVE_TEST_MODE=false`
3. Adjust position sizing for larger capital
4. Set appropriate risk limits

**Configuration changes:**
```bash
# In .env.async - REMOVE these lines or set to false:
# ALPHA_LIVE_TEST_MODE=true
# ALPHA_MAX_ORDERS_PER_DAY=3
# ALPHA_MAX_USD_PER_ORDER=7.50

# ADD/ADJUST these:
ALPHA_MAX_PORTFOLIO_HEAT=0.012  # 1.2% max risk
ALPHA_RISK_PER_TRADE=0.0025     # 0.25% per trade
ALPHA_MAX_CONCURRENT_POSITIONS=5
```

**Safety checklist before going LIVE:**
- [ ] Pump engine generating valid signals
- [ ] Orders executing correctly
- [ ] Stop-losses working
- [ ] Position tracking accurate
- [ ] Risk limits enforced
- [ ] Tested for at least 1 week with LIVE_TEST_MODE
- [ ] Reviewed all trades manually
- [ ] Profitable in test mode

---

## 🎯 PHASE 3: High-Value Features to Add

### Feature 1: Advanced Stop-Loss Strategies
**Value:** Protect profits, reduce losses

**Implementation:**
- Trailing stop-loss (moves with price)
- Break-even stop (moves to entry after X% profit)
- Time-based stop (close if no movement)
- Volatility-adjusted stop (based on ATR)

**Complexity:** Medium (3-4 days)

---

### Feature 2: Position Analytics Dashboard
**Value:** Track performance in real-time

**Implementation:**
- Daily P&L report via Telegram
- Win rate tracking
- Average hold time
- Best/worst performers
- Equity curve visualization

**Complexity:** Medium (3-4 days)

---

### Feature 3: Multi-Timeframe Analysis
**Value:** Better signal quality

**Implementation:**
- Check 1m, 5m, 15m timeframes
- Require alignment across timeframes
- Higher scores for multi-TF confirmation

**Complexity:** Medium (2-3 days)

---

### Feature 4: Dynamic Position Sizing
**Value:** Optimize capital allocation

**Implementation:**
- Kelly Criterion sizing
- Volatility-adjusted sizing (use ATR)
- Confidence-based sizing (higher score = larger size)
- Win rate adaptive sizing

**Complexity:** Medium-High (4-5 days)

---

### Feature 5: Smart Order Execution
**Value:** Better entry prices, lower slippage

**Implementation:**
- TWAP (Time-Weighted Average Price)
- Limit orders with timeout fallback to market
- Ladder entry (split orders)
- Iceberg orders (hide size)

**Complexity:** High (5-6 days)

---

### Feature 6: Signal Quality Scoring
**Value:** Filter out low-quality signals

**Implementation:**
- Machine learning score (if data available)
- Historical backtest score
- Liquidity quality score
- Time-of-day filter (avoid low-volume hours)

**Complexity:** High (6-7 days)

---

### Feature 7: Multi-Exchange Support
**Value:** More opportunities, diversification

**Implementation:**
- Add Binance, Bybit, OKX connectors
- Cross-exchange arbitrage detection
- Exchange health monitoring
- Failover if exchange down

**Complexity:** Very High (7-10 days)

---

### Feature 8: Backtesting Framework
**Value:** Test strategies before live deployment

**Implementation:**
- Historical data replay
- Simulated order execution
- Performance metrics calculation
- Strategy comparison reports

**Complexity:** Very High (10-14 days)

---

### Feature 9: Auto-Rebalancing
**Value:** Maintain optimal portfolio allocation

**Implementation:**
- Define target allocations (e.g., 50% BTC, 30% ETH, 20% alts)
- Periodic rebalancing (daily/weekly)
- Threshold-based rebalancing (5% drift triggers)
- Tax-aware rebalancing (minimize taxable events)

**Complexity:** Medium-High (4-5 days)

---

### Feature 10: Circuit Breakers
**Value:** Prevent catastrophic losses

**Implementation:**
- Daily loss limit (e.g., -5% stops trading)
- Consecutive loss limit (3 losses in row = pause)
- Drawdown protection (20% drawdown = reduce size)
- Exchange API error circuit breaker
- Auto-restart after cooldown period

**Complexity:** Medium (3-4 days)

---

## 📊 Recommended Priority Order

### **MUST DO FIRST (Weeks 1-2):**
1. ✅ Integrate Pump Engine
2. ✅ Integrate Order Placement
3. ✅ Integrate Risk Management
4. ✅ Position Management

**Why:** Bot is useless without these - not trading at all currently!

---

### **HIGH VALUE (Weeks 3-4):**
5. Advanced Stop-Loss Strategies
6. Circuit Breakers
7. Position Analytics Dashboard

**Why:** Protect capital and improve decision making

---

### **NICE TO HAVE (Month 2):**
8. Dynamic Position Sizing
9. Signal Quality Scoring
10. Multi-Timeframe Analysis

**Why:** Improve profitability and signal quality

---

### **ADVANCED (Month 3+):**
11. Smart Order Execution
12. Backtesting Framework
13. Multi-Exchange Support

**Why:** Optimization and scaling

---

## 💡 My Top Recommendations

If I were you, here's what I'd focus on:

### Week 1-2: **Make it Trade!**
- Integrate pump engine + order placement + risk management
- Get the bot actually trading (even with LIVE_TEST_MODE)
- Test with small amounts first

### Week 3: **Protect Capital**
- Add circuit breakers
- Implement trailing stops
- Add daily loss limits

### Week 4: **Optimize**
- Track performance metrics
- Tune parameters based on results
- Remove LIVE_TEST_MODE if profitable

### Month 2: **Scale**
- Add multi-timeframe analysis
- Improve position sizing
- Consider more exchanges

---

## 🎯 Quick Wins (Easy Features - Do These ASAP)

### 1. Equity Tracking
**Time:** 1 hour
**Value:** High - know your P&L at all times

```python
# Add to app_async.py after exchange init:
async def log_equity_snapshot():
    balance = await exchange.fetch_balance()
    equity = balance['total']['USDT']
    await db.execute(
        "INSERT INTO equity_snapshots (timestamp, equity) VALUES (?, ?)",
        (time.time(), equity)
    )
    await telegram.send(f"💰 Equity: ${equity:.2f}")
```

---

### 2. Daily Performance Report
**Time:** 2 hours
**Value:** High - track progress daily

```python
# Send at midnight UTC via scheduled task
async def daily_report():
    # Query DB for today's trades
    trades_today = await db.fetch_all("SELECT * FROM trades WHERE date = ?", today)

    total_pnl = sum(t['pnl'] for t in trades_today)
    win_rate = len([t for t in trades_today if t['pnl'] > 0]) / len(trades_today)

    await telegram.send(
        f"📊 Daily Report\n"
        f"Trades: {len(trades_today)}\n"
        f"P&L: ${total_pnl:.2f}\n"
        f"Win Rate: {win_rate:.1%}"
    )
```

---

### 3. Error Alerting
**Time:** 30 minutes
**Value:** High - catch issues fast

```python
# Wrap critical operations:
try:
    await place_order(...)
except Exception as e:
    await telegram.send(f"🚨 ERROR: {str(e)}")
    logger.error(f"Order placement failed: {e}", exc_info=True)
```

---

### 4. Uptime Monitoring
**Time:** 1 hour
**Value:** Medium - peace of mind

```python
# Send heartbeat every 6 hours
async def send_heartbeat():
    while not stop_event.is_set():
        await telegram.send(f"💚 Bot alive | Scans: {scan_count} | Uptime: {uptime}")
        await asyncio.sleep(21600)  # 6 hours
```

---

## 📈 Expected ROI by Feature

| Feature | Implementation Time | Expected ROI | Priority |
|---------|-------------------|--------------|----------|
| Integrate Pump Engine | 2-3 days | ∞ (required) | P0 |
| Order Placement | 2-3 days | ∞ (required) | P0 |
| Risk Management | 3-4 days | ∞ (required) | P0 |
| Position Management | 4-5 days | ∞ (required) | P0 |
| Circuit Breakers | 3-4 days | High (prevent -20% days) | P1 |
| Trailing Stops | 3-4 days | High (+5-10% on winners) | P1 |
| Analytics Dashboard | 3-4 days | Medium (better decisions) | P2 |
| Dynamic Sizing | 4-5 days | Medium (+2-5% returns) | P2 |
| Multi-Timeframe | 2-3 days | Medium (filter bad signals) | P2 |
| Smart Execution | 5-6 days | Low-Medium (+1-2% on fills) | P3 |
| Multi-Exchange | 7-10 days | Low (unless exchange issues) | P3 |

---

## 🚦 Next Steps

### **TODAY:**
1. Review this roadmap
2. Decide: Start integrating trading engines? Or add features to non-trading async bot?
3. Create GitHub issues for Phase 1 tasks

### **THIS WEEK:**
1. Integrate pump engine into async bot
2. Test signal generation
3. Integrate order placement
4. Test with LIVE_TEST_MODE

### **THIS MONTH:**
1. Complete Phase 1 (all trading engines integrated)
2. Add circuit breakers and advanced stops
3. Test thoroughly
4. Go full LIVE (remove test mode)

---

## ⚠️ IMPORTANT NOTE

**Your async bot is NOT trading yet!** It's just:
- Scanning markets ✅
- Fetching data ✅
- Computing indicators ✅
- Doing nothing with signals ❌

Before you can "go full LIVE," you need to integrate the actual trading logic from your sync bot.

**The good news:** Your async infrastructure is solid and 10x faster. Once you integrate the trading engines, you'll have a beast of a bot! 🚀

---

**Ready to start Phase 1? Let me know and I'll help you integrate the pump engine first!**
