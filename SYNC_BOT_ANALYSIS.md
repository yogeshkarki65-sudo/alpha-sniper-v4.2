# Sync Bot Trading Logic Analysis

**Date:** 2025-12-29
**Purpose:** Document how the sync bot trades so we can port it to async

---

## 🔍 Complete Trading Flow

### **1. Scanner Phase (`signals/scanner.py`)**

**Method:** `Scanner.scan()`

**Steps:**
1. Get current regime from risk_engine (BULL/BEAR/SIDEWAYS)
2. Build universe via `_build_universe()`:
   - Filters by quote currency (USDT)
   - Excludes leveraged tokens (3L/3S)
   - Excludes perps
   - Sorts by 24h volume
   - Takes top N symbols

3. Fetch market data via `_fetch_market_data()`:
   - Fetches OHLCV (500 candles @ 1m)
   - Fetches ticker data (price, volume, etc.)
   - Computes indicators (RSI, EMA, RVOL, momentum)

4. Run pump engine (PUMP_ONLY mode):
   ```python
   pump_signals = pump_engine.generate_signals(market_data, regime)
   ```

5. Return all signals

---

### **2. Pump Engine (`signals/pump_engine.py`)**

**Method:** `PumpEngine.generate_signals(market_data, regime)`

**Logic:**
1. Get regime-specific thresholds:
   - min_24h_quote_volume (default: $47,000)
   - min_score (default: 28)
   - min_rvol (default: 2.0)
   - min_24h_return (default: 30%)
   - max_24h_return (default: 400%)
   - min_momentum

2. For each symbol:
   - **Filter 1:** Check data quality (OHLCV, ticker)
   - **Filter 2:** Check 24h volume >= threshold
   - **Filter 3:** Check spread < max_spread_pct
   - **Filter 4:** Calculate pump score (based on RVOL, momentum, return)
   - **Filter 5:** Check score >= min_score
   - **Filter 6:** Check not already in position
   - **Filter 7:** Additional core filters (depth, liquidity)

3. If passes all filters, create signal:
   ```python
   signal = {
       'symbol': symbol,
       'side': 'long',
       'engine': 'pump',
       'entry_price': current_price,
       'stop_loss': stop_loss_price,
       'tp_2r': tp_2r_price,
       'tp_4r': tp_4r_price,
       'score': pump_score,
       'regime': regime,
       'max_hold_hours': 6  # Pumps have short hold time
   }
   ```

4. Return list of signals

---

### **3. Signal Processing (`main.py::_process_signals()`)**

**Method:** `_process_signals(signals)`

**For each signal:**

#### **Step 1: Core Position Check**
```python
can_open, reason = risk_engine.can_open_new_position(sig)
```
Checks:
- Not exceeding max concurrent positions
- Not exceeding portfolio heat limit
- Not in same symbol already
- Account has sufficient balance

#### **Step 2: Early Depth Gate**
```python
liquidity = exchange.get_liquidity_metrics(symbol)
if liquidity['depth_usd'] < min_depth_usd:
    reject()
```

#### **Step 3: Calculate Position Size**
```python
size_usd = risk_engine.calculate_position_size(sig, entry_price, stop_loss)
```
- Calculates based on risk % (0.25% default)
- Applies LiquidityGuard scaling (reduces size if low liquidity)
- Returns 0 if too risky

#### **Step 4: Viability Gate #1 - LiquidityGuard Check**
```python
if size_usd <= 0:
    reject()  # LiquidityGuard rejected
```

#### **Step 5: Viability Gate #2 - Spread & Depth**
```python
if spread_pct > max_spread_pct_order:  # 0.30% default
    reject()

required_depth = size_usd * min_depth_multiple  # 200x default
if depth_usd < required_depth:
    reject()
```

#### **Step 6: Exchange Validation**
```python
valid, reason, details = exchange.validate_order(symbol, size_usd, entry_price)
```
Checks:
- minQty (minimum quantity per exchange rules)
- minNotional (minimum USD value)
- Quantity precision (decimals)
- Price precision

#### **Step 7: LIVE_TEST_MODE Check**
```python
if live_test_mode:
    if orders_today >= 3:
        reject()  # Max 3 orders per day
    if size_usd > 7.50:
        size_usd = 7.50  # Cap at $7.50
```

#### **Step 8: Create Position Object**
```python
position = {
    'symbol': symbol,
    'side': 'long',
    'engine': 'pump',
    'entry_price': entry_price,
    'stop_loss': stop_loss,
    'tp_2r': tp_2r,
    'tp_4r': tp_4r,
    'size_usd': size_usd,
    'qty': qty,
    'risk_pct': risk_pct,
    'initial_risk_usd': initial_risk_usd,
    'equity_at_entry': equity_at_entry,
    'score': score,
    'regime': regime,
    'timestamp_open': timestamp,
    'max_hold_hours': 6
}
```

#### **Step 9: Place Order**
```python
order = exchange.create_order(
    symbol=symbol,
    type='market',
    side='buy',  # or 'sell' for short
    amount=qty,
    params={'leverage': 1}  # 1x isolated
)
```

#### **Step 10: Add Position & Notify**
```python
if order and order.get('id'):
    position['order_id'] = order['id']
    risk_engine.add_position(position)
    telegram.send_trade_open_notification(position)
```

---

### **4. Position Management (`main.py::_manage_positions()`)**

**Method:** `_manage_positions()`

**For each open position:**

#### **Step 1: Fetch Current Price**
```python
ticker = exchange.get_ticker(symbol)
current_price = ticker['last']
```

#### **Step 2: Calculate PnL%**
```python
if side == 'long':
    pnl_pct = ((current_price / entry_price) - 1) * 100
else:  # short
    pnl_pct = ((entry_price / current_price) - 1) * 100
```

#### **Step 3: Calculate R-Multiple**
```python
risk_per_unit = abs(entry_price - stop_loss)
unrealized_pnl_per_unit = current_price - entry_price  # long
unrealized_r = unrealized_pnl_per_unit / risk_per_unit
```

#### **Step 4: Breakeven at +0.7R**
```python
if unrealized_r >= 0.7 and not 'breakeven_moved_at_07r' in position:
    position['stop_loss'] = entry_price  # Move stop to breakeven
    position['breakeven_moved_at_07r'] = True
```

#### **Step 5: Partial TP at +2R**
```python
if unrealized_r >= 2.0 and not 'partial_tp_taken' in position:
    partial_qty = qty * 0.5  # Close 50%
    order = exchange.create_order(
        symbol=symbol,
        type='market',
        side='sell',  # opposite side
        amount=partial_qty
    )
    position['partial_tp_taken'] = True
    position['qty'] = qty * 0.5  # Reduce remaining qty
```

#### **Step 6: Check Stop-Loss**
```python
if side == 'long' and current_price <= stop_loss:
    close_position(position, 'STOP_LOSS')
elif side == 'short' and current_price >= stop_loss:
    close_position(position, 'STOP_LOSS')
```

#### **Step 7: Check Take-Profit**
```python
if side == 'long' and current_price >= tp_4r:
    close_position(position, 'TP_4R')
elif side == 'long' and current_price >= tp_2r:
    close_position(position, 'TP_2R')
```

#### **Step 8: Check Max Hold Time**
```python
hours_held = (current_time - timestamp_open) / 3600
if hours_held >= max_hold_hours:
    close_position(position, 'MAX_HOLD_TIME')
```

#### **Step 9: Close Position**
```python
def close_position(position, reason):
    order = exchange.create_order(
        symbol=symbol,
        type='market',
        side='sell',  # opposite of entry side
        amount=qty
    )

    if order and order['id']:
        # Calculate final PnL
        realized_pnl_usd = (current_price - entry_price) * qty  # long
        realized_pnl_pct = ((current_price / entry_price) - 1) * 100
        realized_r = realized_pnl_usd / initial_risk_usd

        # Save to trade history
        risk_engine.save_closed_trade(position, realized_pnl_usd, reason)

        # Remove from open positions
        risk_engine.remove_position(symbol)

        # Send Telegram notification
        telegram.send_trade_close_notification(position, realized_pnl_usd, reason)
```

---

## 📊 Key Components Used

### **RiskEngine** (`risk_engine.py`)
- `can_open_new_position(signal)` - Checks if new position allowed
- `calculate_position_size(signal, entry, stop)` - Calculates position size
- `add_position(position)` - Adds to open_positions list
- `remove_position(symbol)` - Removes from open_positions list
- `save_closed_trade(position, pnl, reason)` - Logs to trade history
- `save_positions(file)` - Persists to JSON file
- `get_risk_per_trade(engine)` - Returns risk % for engine type

### **Exchange** (`exchange.py`)
- `get_ticker(symbol)` - Fetches current price/volume
- `get_liquidity_metrics(symbol)` - Fetches spread/depth
- `validate_order(symbol, size_usd, price)` - Validates order params
- `create_order(symbol, type, side, amount, params)` - Places order
- `fetch_balance()` - Gets account balance

### **TelegramNotifier** (`utils/telegram.py`)
- `send(message)` - Sends raw message
- `send_trade_open_notification(position)` - Trade open alert
- `send_trade_close_notification(position, pnl, reason)` - Trade close alert

---

## 🔧 Configuration Parameters

### **Universe Selection**
- `universe_size`: 80 (top N symbols by volume)
- `universe_base_quote`: "USDT"
- `universe_min_quote_volume`: $47,000 (24h volume)

### **Pump Engine Thresholds**
- `min_pump_score`: 28
- `min_rvol`: 2.0 (relative volume)
- `min_24h_return`: 30%
- `max_24h_return`: 400%
- `min_24h_quote_volume`: $47,000

### **Risk Management**
- `risk_per_trade`: 0.0025 (0.25% of equity)
- `max_concurrent_positions`: 5
- `max_portfolio_heat`: 0.012 (1.2%)

### **Viability Checks**
- `min_viable_trade_usd`: $5.0
- `max_spread_pct_order`: 0.30% (30 bps)
- `min_depth_multiple`: 200x (depth must be 200x order size)
- `min_depth_usd`: $0 (optional absolute depth floor)

### **LIVE_TEST_MODE**
- `live_test_mode`: true
- `live_test_max_orders_per_day`: 3
- `live_test_max_usd_per_order`: $7.50
- Resets daily at midnight UTC

### **Pump-Specific**
- `max_hold_hours`: 6 (for pump trades)
- `min_stop_pct_pump`: 0.02 (2% default stop)

---

## 🎯 What Needs to Be Ported to Async

### **1. Pump Engine Integration**
**File:** `signals/pump_engine.py`
**Status:** ✅ Already synchronous, can be used as-is initially
**Future:** Convert to async for better performance

**Integration point in `app_async.py`:**
```python
# After market_data = await scan_symbols(...)
from signals.pump_engine import PumpEngine

pump_engine = PumpEngine(settings, logger)
signals = pump_engine.generate_signals(market_data, regime='SIDEWAYS')
```

---

### **2. Signal Processing Logic**
**File:** `main.py::_process_signals()`
**Status:** ❌ Needs async port

**New async function:**
```python
async def process_signals_async(
    signals: list,
    exchange: AsyncExchange,
    risk_engine: AsyncRiskEngine,
    telegram: AsyncTelegram,
    settings: Settings
) -> tuple[int, int]:
    """
    Process signals and place orders asynchronously.

    Returns:
        (signals_opened, signals_skipped)
    """
    signals_opened = 0

    for sig in signals:
        # 1. Check if can open
        can_open, reason = await risk_engine.can_open_new_position_async(sig)
        if not can_open:
            continue

        # 2. Calculate position size
        size_usd = await risk_engine.calculate_position_size_async(
            sig, sig['entry_price'], sig['stop_loss']
        )

        if size_usd <= 0:
            continue

        # 3. Viability checks
        liquidity = await exchange.get_liquidity_metrics_async(sig['symbol'])
        if liquidity['spread_pct'] > settings.MAX_SPREAD_PCT_ORDER:
            continue

        # 4. Exchange validation
        valid, reason, details = await exchange.validate_order_async(
            sig['symbol'], size_usd, sig['entry_price']
        )
        if not valid:
            continue

        # 5. Place order
        order = await exchange.create_order_async(
            symbol=sig['symbol'],
            type='market',
            side='buy' if sig['side'] == 'long' else 'sell',
            amount=size_usd / sig['entry_price'],
            params={'leverage': 1}
        )

        if order and order.get('id'):
            # 6. Add position
            position = {...}  # Create position object
            await risk_engine.add_position_async(position)

            # 7. Notify
            await telegram.send(f"✅ Opened {sig['symbol']} @ ${sig['entry_price']}")

            signals_opened += 1

    return signals_opened
```

---

### **3. Position Management**
**File:** `main.py::_manage_positions()`
**Status:** ❌ Needs async port

**New async function:**
```python
async def manage_positions_async(
    risk_engine: AsyncRiskEngine,
    exchange: AsyncExchange,
    telegram: AsyncTelegram
) -> tuple[int, int]:
    """
    Manage open positions: check SL/TP, breakeven, partial TP.

    Returns:
        (positions_closed, positions_updated)
    """
    open_positions = await risk_engine.get_open_positions_async()

    positions_closed = 0
    positions_updated = 0

    for position in open_positions:
        # 1. Get current price
        ticker = await exchange.get_ticker_async(position['symbol'])
        current_price = ticker['last']

        # 2. Calculate R-multiple
        risk_per_unit = abs(position['entry_price'] - position['stop_loss'])
        unrealized_pnl = current_price - position['entry_price']
        unrealized_r = unrealized_pnl / risk_per_unit

        # 3. Breakeven at +0.7R
        if unrealized_r >= 0.7 and not position.get('breakeven_moved'):
            position['stop_loss'] = position['entry_price']
            position['breakeven_moved'] = True
            await risk_engine.update_position_async(position)
            positions_updated += 1

        # 4. Partial TP at +2R
        if unrealized_r >= 2.0 and not position.get('partial_tp_taken'):
            partial_qty = position['qty'] * 0.5
            await exchange.create_order_async(
                symbol=position['symbol'],
                type='market',
                side='sell',
                amount=partial_qty
            )
            position['qty'] *= 0.5
            position['partial_tp_taken'] = True
            await risk_engine.update_position_async(position)
            positions_updated += 1

        # 5. Check stop-loss
        if current_price <= position['stop_loss']:
            await close_position_async(position, 'STOP_LOSS')
            positions_closed += 1

        # 6. Check take-profit
        elif current_price >= position.get('tp_4r', float('inf')):
            await close_position_async(position, 'TP_4R')
            positions_closed += 1

        # 7. Check max hold time
        elif time.time() - position['timestamp_open'] > position['max_hold_hours'] * 3600:
            await close_position_async(position, 'MAX_HOLD_TIME')
            positions_closed += 1

    return positions_closed, positions_updated


async def close_position_async(
    position: dict,
    reason: str,
    exchange: AsyncExchange,
    risk_engine: AsyncRiskEngine,
    telegram: AsyncTelegram
):
    """Close a position and record the trade."""
    # Place close order
    order = await exchange.create_order_async(
        symbol=position['symbol'],
        type='market',
        side='sell' if position['side'] == 'long' else 'buy',
        amount=position['qty']
    )

    if order and order.get('id'):
        # Calculate PnL
        avg_price = order.get('average', order.get('price'))
        if position['side'] == 'long':
            pnl_usd = (avg_price - position['entry_price']) * position['qty']
        else:
            pnl_usd = (position['entry_price'] - avg_price) * position['qty']

        pnl_pct = (pnl_usd / position['size_usd']) * 100
        r_multiple = pnl_usd / position['initial_risk_usd']

        # Save trade
        await risk_engine.save_closed_trade_async(position, pnl_usd, reason)

        # Remove from open positions
        await risk_engine.remove_position_async(position['symbol'])

        # Notify
        await telegram.send(
            f"🔴 Closed {position['symbol']}\n"
            f"Reason: {reason}\n"
            f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%)\n"
            f"R: {r_multiple:.2f}R"
        )
```

---

### **4. Async Risk Engine**
**Status:** ❌ Needs to be created

**New file:** `alpha-sniper/risk/async_risk_engine.py`

**Key methods:**
- `async can_open_new_position_async(signal)` - Async position check
- `async calculate_position_size_async(signal, entry, stop)` - Async size calc
- `async add_position_async(position)` - Add to DB
- `async get_open_positions_async()` - Query from DB
- `async update_position_async(position)` - Update in DB
- `async remove_position_async(symbol)` - Remove from DB
- `async save_closed_trade_async(position, pnl, reason)` - Save to trades table

---

## 📝 Integration Checklist

### **Phase 1: Pump Engine (Week 1)**
- [ ] Create `from signals.pump_engine import PumpEngine` in app_async.py
- [ ] Call `pump_engine.generate_signals(market_data, regime)` after scanning
- [ ] Log signals generated
- [ ] Test signal generation WITHOUT placing orders

### **Phase 2: Order Placement (Week 1-2)**
- [ ] Create `process_signals_async()` function
- [ ] Port all viability checks to async
- [ ] Implement async order placement
- [ ] Test with LIVE_TEST_MODE (3 orders @ $7.50 max)

### **Phase 3: Position Management (Week 2)**
- [ ] Create `manage_positions_async()` function
- [ ] Implement breakeven at +0.7R
- [ ] Implement partial TP at +2R
- [ ] Implement stop-loss / take-profit checks
- [ ] Test position lifecycle

### **Phase 4: Risk Engine (Week 2-3)**
- [ ] Create `AsyncRiskEngine` class
- [ ] Port all risk calculations to async
- [ ] Integrate with AsyncDB
- [ ] Add position tracking to database

### **Phase 5: Testing & Validation (Week 3)**
- [ ] Test complete trade lifecycle
- [ ] Validate PnL calculations
- [ ] Confirm Telegram notifications
- [ ] Monitor for 1 week with LIVE_TEST_MODE

### **Phase 6: Go Full LIVE (Week 4)**
- [ ] Remove LIVE_TEST_MODE
- [ ] Adjust risk parameters for full capital
- [ ] Monitor closely for first 48 hours

---

## 🚀 Quick Start Integration

**Minimal integration to get trading ASAP:**

```python
# In app_async.py, after Step 2 (market data fetched):

# Import pump engine
from signals.pump_engine import PumpEngine

# Initialize pump engine
pump_engine = PumpEngine(settings, logger)

# Generate signals (synchronous for now)
signals = pump_engine.generate_signals(market_data, regime='SIDEWAYS')

logger.info(f"🎯 Generated {len(signals)} pump signals")

# For each signal:
for sig in signals:
    logger.info(
        f"🔔 SIGNAL: {sig['symbol']} | "
        f"score={sig['score']} | "
        f"entry=${sig['entry_price']:.6f} | "
        f"stop=${sig['stop_loss']:.6f}"
    )

    # TODO: Place order here
    # order = await exchange.create_order_async(...)
```

**This will get you signals FAST.** Then you can add order placement incrementally.

---

## 💡 Summary

**The sync bot is a complete, working trading system.** It has:
- ✅ Signal generation (pump engine)
- ✅ Risk management (position sizing, limits)
- ✅ Order placement (market orders)
- ✅ Position management (SL/TP, breakeven, partial TP)
- ✅ Telegram notifications
- ✅ Trade history tracking

**The async bot has:**
- ✅ Fast market scanning (4.2s vs 30-60s)
- ✅ Indicator computation
- ✅ Database infrastructure
- ✅ Telegram integration
- ❌ NO signal generation
- ❌ NO order placement
- ❌ NO position management
- ❌ NO trading!

**To make the async bot trade, we need to:**
1. Integrate pump engine → Generate signals
2. Port signal processing → Place orders
3. Port position management → Manage trades
4. Create async risk engine → Calculate sizes, track positions

**Estimated time:** 2-3 weeks for full integration

**Fast path:** 2-3 days to get basic signal generation + order placement working

---

**Ready to start? Let's begin with Phase 1: Pump Engine Integration!**
