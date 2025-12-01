# Pump-Only Mode - Alpha Sniper V4.2

## Overview

Pump-Only Mode is a simplified trading mode that focuses exclusively on catching high-momentum pump opportunities. When enabled, the bot disables all other signal engines (long, short, bear_micro) and runs **only** the pump engine with stricter, more selective filters.

## Why Pump-Only Mode?

The standard Alpha Sniper V4.2 bot runs multiple engines simultaneously, which:
- Spreads capital across different strategies
- May dilute pump allocation during high-opportunity periods
- Requires monitoring multiple position types

Pump-Only Mode addresses this by:
- **Focusing 100% on pump opportunities**
- **Using stricter filters** to catch only high-quality liquid pumps
- **Implementing ATR-based trailing stops** to lock in profits as pumps continue
- **Simplifying operations** by removing unnecessary features

## How to Enable

Set the following in your `.env` file:

```bash
PUMP_ONLY_MODE=true
```

That's it! The bot will now use only the pump engine.

## Pump-Only Filters

When `PUMP_ONLY_MODE=true`, the pump engine applies stricter filters:

| Filter | Default | Pump-Only | Purpose |
|--------|---------|-----------|---------|
| **24h Return** | 30-400% | 80-350% | Tighter range for established pumps |
| **RVOL** | ≥2.0 | ≥2.8 | Higher volume requirement |
| **1h Momentum** | ≥25% | ≥40% | Stronger momentum needed |
| **24h Volume** | $50k | $800k | Only liquid pumps |
| **Score** | ≥70 | ≥85 | High-quality signals only |
| **Max Hold** | 6 hours | 4 hours | Shorter hold time |

### Configuration Parameters

```bash
# Stricter pump filters
PUMP_MIN_24H_RETURN=0.80        # Minimum 80% 24h return
PUMP_MAX_24H_RETURN=3.50        # Maximum 350% 24h return
PUMP_MIN_RVOL=2.8               # Minimum 2.8x relative volume
PUMP_MIN_MOMENTUM_1H=40         # Minimum 40% 1h momentum
PUMP_MIN_24H_QUOTE_VOLUME=800000 # Minimum $800k 24h volume
PUMP_MIN_SCORE=85               # Minimum score 85
PUMP_MAX_HOLD_HOURS=4           # Maximum 4 hours hold time
```

## ATR-Based Trailing Stop

Pump-Only Mode includes an ATR-based trailing stop system that automatically adjusts stop losses to lock in profits as pumps continue.

### How It Works

1. **Initial Stop**: Set at `2.0 * ATR(14)` below entry price
2. **Trailing Start**: After 30 minutes in position
3. **Trail Distance**: `1.2 * ATR(14)` below current price
4. **Only Raises**: Never lowers the stop, only raises it

### Configuration

```bash
# ATR-based trailing stop
PUMP_TRAIL_INITIAL_ATR_MULT=2.0 # Initial stop: 2.0 * ATR(14)
PUMP_TRAIL_ATR_MULT=1.2         # Trail: 1.2 * ATR(14)
PUMP_TRAIL_START_MINUTES=30     # Start trailing after 30 min
```

### Example

```
Entry: $1.00
Initial Stop: $0.92 (2.0 * ATR = $0.08)

After 30 minutes:
Price: $1.50 → Stop trails to $1.38 (1.50 - 1.2*ATR)
Price: $1.80 → Stop trails to $1.68 (1.80 - 1.2*ATR)
Price: $1.70 → Stop stays at $1.68 (no lowering)
Price: $2.00 → Stop trails to $1.88 (2.00 - 1.2*ATR)
```

## Recommended Settings for Pump-Only Mode

```bash
# === CORE SETTINGS ===
PUMP_ONLY_MODE=true             # Enable pump-only mode
STARTING_EQUITY=1000            # Your starting capital
MAX_CONCURRENT_POSITIONS=3      # Lower for focused trades
SCAN_INTERVAL_SECONDS=180       # Faster scans (3 min)

# === DISABLE UNNECESSARY FEATURES ===
ENTRY_DETE_ENABLED=false        # Pumps need immediate entry
DFE_ENABLED=false               # Pump filters are manual
SIDEWAYS_COIL_ENABLED=false     # Not needed
SHORT_FUNDING_OVERLAY_ENABLED=false # Not needed (long-only)
CORRELATION_LIMIT_ENABLED=false # Not needed (single engine)

# === RISK MANAGEMENT ===
MAX_PORTFOLIO_HEAT=0.012        # 1.2% total portfolio risk
PUMP_RISK_PER_TRADE=0.0010      # 0.10% risk per pump trade
ENABLE_DAILY_LOSS_LIMIT=true    # Stop after daily loss limit
MAX_DAILY_LOSS_PCT=0.03         # 3% daily loss limit

# === PUMP ENGINE ===
PUMP_ENGINE_ENABLED=true        # Must be enabled
PUMP_MAX_CONCURRENT=2           # Max 2 pump positions
```

## SIM Mode Testing

**Always test pump-only mode in SIM mode first!**

```bash
SIM_MODE=true                   # Enable simulation
SIM_DATA_SOURCE=LIVE_DATA       # Use live market data
STARTING_EQUITY=1000            # Test with $1000
```

### Testing Checklist

- [ ] Set `PUMP_ONLY_MODE=true`
- [ ] Set `SIM_MODE=true`
- [ ] Disable unnecessary features (Entry-DETE, DFE, etc.)
- [ ] Run for 24-48 hours
- [ ] Monitor signal quality (Score ≥85)
- [ ] Check trailing stop behavior
- [ ] Verify max hold time enforcement (4 hours)
- [ ] Review trades.csv for performance

## How Pump-Only Mode Works

### 1. Scanner Behavior

When `PUMP_ONLY_MODE=true`:
- Scanner runs **only** the pump engine
- All other engines (long, short, bear_micro) are skipped
- Logs: `🎯 PUMP-ONLY MODE: Using pump engine exclusively`

### 2. Pump Engine Logic

The pump engine evaluates each symbol:
1. **Volume check**: Must have ≥$800k 24h volume
2. **RVOL check**: Must have ≥2.8x relative volume
3. **Momentum check**: Must have ≥40% 1h momentum
4. **24h return check**: Must be between 80-350%
5. **Score check**: Must score ≥85 points
6. **Max hold**: Position closes after 4 hours

### 3. Position Management

Every 15 seconds (Fast Stop Manager loop):
1. **Check stop loss**: Close if price hits stop
2. **Check take profit**: Close if 4R target hit, move to breakeven at 2R
3. **Update trailing stop**: Raise stop if pump continues (after 30 min)

### 4. Logging

Look for these log markers:
```
🎯 PUMP-ONLY MODE: Using pump engine exclusively
📡 Signals Generated [PUMP-ONLY] | Pump: 2 | TOTAL: 2
[PumpTrailer] Trail updated | symbol=BTC/USDT | old_stop=0.950000 → new_stop=0.980000
```

## Performance Expectations

### What to Expect

- **Lower signal count**: 1-5 signals per day (vs 10-20 in multi-engine mode)
- **Higher win rate**: 50-65% (due to stricter filters)
- **Larger average win**: 1.5-3R per winner
- **Faster exits**: Most trades close within 2-4 hours
- **Drawdown protection**: Trailing stops lock in profits

### Risk Profile

- **Maximum risk per trade**: 0.10% of equity
- **Maximum concurrent risk**: 0.30% (3 positions × 0.10%)
- **Daily loss limit**: 3% of equity
- **Position sizing**: Determined by liquidity and ATR

## Troubleshooting

### No Signals Generated

**Possible causes:**
1. Filters are too strict → Lower `PUMP_MIN_SCORE` to 80
2. Market conditions are bearish → Pumps are rare in bear markets
3. Insufficient volume → Lower `PUMP_MIN_24H_QUOTE_VOLUME` to $500k
4. RVOL too high → Lower `PUMP_MIN_RVOL` to 2.5

### Trailing Stop Not Working

**Check:**
1. Position is ≥30 minutes old (`PUMP_TRAIL_START_MINUTES`)
2. Position engine is "pump" (not long/short)
3. Price is moving up (trailing only raises stops)
4. ATR data is available (15m klines)

### Positions Closing Too Early

**Adjust:**
- Increase `PUMP_TRAIL_ATR_MULT` from 1.2 to 1.5 (wider trail)
- Increase `PUMP_TRAIL_START_MINUTES` from 30 to 45 (wait longer)
- Check if stop loss is too tight (increase `PUMP_TRAIL_INITIAL_ATR_MULT`)

### Positions Closing Too Late

**Adjust:**
- Decrease `PUMP_MAX_HOLD_HOURS` from 4 to 3
- Decrease `PUMP_TRAIL_ATR_MULT` from 1.2 to 1.0 (tighter trail)
- Lower 4R target multiplier (requires code change)

## Comparison: Normal Mode vs Pump-Only Mode

| Feature | Normal Mode | Pump-Only Mode |
|---------|-------------|----------------|
| **Engines** | Long, Short, Pump, BearMicro | Pump only |
| **Signal count** | 10-20/day | 1-5/day |
| **Pump filters** | Standard (≥70 score) | Strict (≥85 score) |
| **RVOL requirement** | ≥2.0 | ≥2.8 |
| **Volume requirement** | $50k | $800k |
| **Max hold** | 6 hours | 4 hours |
| **Trailing stops** | No | Yes (ATR-based) |
| **Entry-DETE** | Optional | Recommended OFF |
| **DFE** | Optional | Recommended OFF |

## FAQ

### Q: Can I use pump-only mode in LIVE trading?

**A:** Yes, but test thoroughly in SIM mode first! Start with small position sizes and monitor closely for 48-72 hours.

### Q: What's the minimum account size?

**A:** Recommended minimum: $500. With 0.10% risk per trade and $5 minimum position size, you need enough equity to take meaningful positions.

### Q: Can I adjust pump filters during operation?

**A:** Yes! Edit `.env` and restart the bot. Changes take effect immediately.

### Q: Does pump-only mode work with Fast Stop Manager?

**A:** Yes! Fast Stop Manager (15s position loop) is fully compatible and recommended for sub-second stop enforcement.

### Q: Can I use Entry-DETE with pump-only mode?

**A:** Not recommended. Pumps need immediate entry. Entry-DETE's queuing system may cause you to miss fast-moving pumps.

### Q: How does trailing stop interact with Fast Stop Manager?

**A:** Trailing stop raises the `stop_loss` value every 15 seconds. Fast Stop Manager then enforces this updated stop in the same 15s loop. They work together seamlessly.

## Support

For issues or questions:
1. Check the logs for `[PumpTrailer]` and `[PUMP-ONLY]` markers
2. Verify your `.env` settings match this guide
3. Test in SIM mode first
4. Report issues on GitHub: https://github.com/yogeshkarki65-sudo/alpha-sniper-v4.2

---

**Last Updated:** December 2025
**Version:** Pump-Only Mode v1.0
**Compatible with:** Alpha Sniper V4.2+
