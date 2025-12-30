"""
Async Risk Engine for Alpha Sniper v4.2

Handles:
- Position sizing based on risk parameters
- Circuit breakers (daily loss cap, streak breaker)
- Position tracking in SQLite database
- Trade history persistence
"""
from __future__ import annotations

import aiosqlite
import time
import math
import logging
from typing import Any, Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class AsyncRiskEngine:
    """
    Async risk management engine with DB-backed position tracking.

    Provides:
    - Risk-based position sizing
    - Circuit breaker enforcement
    - Position CRUD operations
    - Trade history logging
    """

    def __init__(self, db_path: str, settings, logger_instance):
        """
        Initialize async risk engine.

        Args:
            db_path: Path to SQLite database
            settings: Settings object with risk parameters
            logger_instance: Logger instance
        """
        self.db_path = db_path
        self.settings = settings
        self.log = logger_instance
        self.conn: Optional[aiosqlite.Connection] = None

        # Track daily orders for LIVE_TEST_MODE
        self.orders_today = 0
        self.orders_reset_date = time.strftime("%Y-%m-%d")

    async def connect(self):
        """Connect to database and initialize schema."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA synchronous=NORMAL;")
        await self.conn.commit()
        await self._migrate()
        self.log.info(f"AsyncRiskEngine connected to {self.db_path}")

    async def _migrate(self):
        """Create tables if they don't exist."""
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                side TEXT,
                engine TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp_2r REAL,
                tp_4r REAL,
                qty REAL,
                size_usd REAL,
                risk_pct REAL,
                initial_risk_usd REAL,
                equity_at_entry REAL,
                score REAL,
                regime TEXT,
                timestamp_open INTEGER,
                max_hold_hours REAL,
                breakeven_moved INTEGER DEFAULT 0,
                partial_tp_taken INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                engine TEXT,
                entry_price REAL,
                exit_price REAL,
                qty REAL,
                pnl_usd REAL,
                pnl_pct REAL,
                r_multiple REAL,
                reason TEXT,
                closed_at INTEGER,
                hold_time_hours REAL
            );

            CREATE TABLE IF NOT EXISTS equity_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER,
                equity REAL,
                open_positions_count INTEGER,
                daily_pnl REAL
            );

            CREATE INDEX IF NOT EXISTS idx_trades_closed_at ON trades(closed_at);
            CREATE INDEX IF NOT EXISTS idx_equity_timestamp ON equity_snapshots(timestamp);
            """
        )
        await self.conn.commit()
        self.log.info("Database schema initialized")

    async def close(self):
        """Close database connection."""
        if self.conn:
            await self.conn.close()
            self.log.info("AsyncRiskEngine connection closed")

    # === RISK DECISIONS ===

    async def can_open_new_position_async(
        self, sig: Dict[str, Any], exchange=None
    ) -> Tuple[bool, str]:
        """
        Check if a new position can be opened.

        Enforces:
        - Max concurrent positions limit
        - Streak breaker (consecutive losses)
        - Daily loss cap
        - Symbol not already in position

        Args:
            sig: Signal dict with symbol, side, etc.
            exchange: Optional AsyncExchange instance for real equity

        Returns:
            (can_open, reason)
        """
        symbol = sig.get('symbol')

        # Check if already in this symbol
        cur = await self.conn.execute(
            "SELECT COUNT(1) FROM positions WHERE symbol=?", (symbol,)
        )
        if (await cur.fetchone())[0] > 0:
            return False, "ALREADY_IN_POSITION"

        # Max concurrent positions
        cur = await self.conn.execute("SELECT COUNT(1) FROM positions")
        n = (await cur.fetchone())[0]
        max_pos = getattr(self.settings, 'MAX_CONCURRENT_POSITIONS', 5)
        if n >= max_pos:
            return False, f"MAX_CONCURRENT_POSITIONS_{max_pos}"

        # Daily loss cap check
        equity = await self.get_real_equity_async(exchange) if exchange else await self._get_equity_estimate()
        daily_loss_cap_pct = getattr(self.settings, 'DAILY_LOSS_CAP_PCT', -0.02)
        daily_pnl = await self._get_daily_pnl()

        if daily_pnl <= equity * daily_loss_cap_pct:
            return False, f"DAILY_LOSS_CAP_TRIGGERED_{daily_loss_cap_pct:.1%}"

        # Streak breaker: if last N trades are all losses, pause
        streak_losses = getattr(self.settings, 'STREAK_BREAKER_LOSSES', 3)
        cur = await self.conn.execute(
            "SELECT pnl_usd FROM trades ORDER BY id DESC LIMIT ?", (streak_losses,)
        )
        rows = await cur.fetchall()

        if len(rows) == streak_losses and all((r[0] or 0) < 0 for r in rows):
            return False, f"STREAK_BREAKER_ACTIVE_{streak_losses}_LOSSES"

        return True, "OK"

    async def calculate_position_size_async(
        self, sig: Dict[str, Any], entry: float, stop: float, exchange=None
    ) -> float:
        """
        Calculate position size in USD based on risk parameters.

        Uses fixed risk % of equity per trade.

        Args:
            sig: Signal dict
            entry: Entry price
            stop: Stop-loss price
            exchange: Optional AsyncExchange instance for real equity

        Returns:
            Position size in USD (0 if invalid)
        """
        equity = await self.get_real_equity_async(exchange) if exchange else await self._get_equity_estimate()
        risk_pct = getattr(self.settings, 'RISK_PER_TRADE', 0.0025)  # 0.25%
        risk_usd = equity * risk_pct

        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0:
            return 0.0

        qty = risk_usd / risk_per_unit
        size_usd = qty * entry

        min_viable = getattr(self.settings, 'MIN_VIABLE_TRADE_USD', 5.0)
        if size_usd < min_viable:
            return 0.0

        return float(size_usd)

    async def _get_equity_estimate(self) -> float:
        """
        Estimate current equity.

        Calculates: starting_equity + sum(closed_pnl) + unrealized_pnl

        Returns:
            Current equity in USD
        """
        # Get total realized PnL from closed trades
        cur = await self.conn.execute("SELECT SUM(pnl_usd) FROM trades")
        realized_pnl = (await cur.fetchone())[0] or 0.0

        # Get unrealized PnL from open positions (simplified)
        # In production, you'd fetch current prices and calculate
        # For now, assume unrealized = 0
        unrealized_pnl = 0.0

        # Starting equity (configurable)
        base_equity = getattr(self.settings, 'SIM_STARTING_EQUITY', 100.0)

        return base_equity + realized_pnl + unrealized_pnl

    async def get_real_equity_async(self, exchange) -> float:
        """
        Get real equity from exchange balance + unrealized PnL.

        Args:
            exchange: AsyncExchange instance to fetch balance from

        Returns:
            Current equity in USD (USDT balance from exchange)
        """
        try:
            # Fetch real balance from exchange
            balance = await exchange.fetch_balance()
            self.log.info(f"Balance response keys: {list(balance.keys())}")
            self.log.info(f"Total balances: {balance.get('total', {})}")
            usdt_total = balance.get('total', {}).get('USDT', 0.0)

            # Add unrealized PnL from open positions
            positions = await self.get_open_positions_async()
            unrealized_pnl = 0.0

            for pos in positions:
                try:
                    symbol = pos.get('symbol')
                    entry = pos.get('entry_price', 0)
                    qty = pos.get('qty', 0)
                    side = pos.get('side', 'buy')

                    # Fetch current price
                    ticker = await exchange.fetch_ticker(symbol)
                    current_price = ticker.get('last', 0)

                    # Calculate unrealized PnL
                    if side == 'buy':
                        unrealized_pnl += (current_price - entry) * qty
                    else:
                        unrealized_pnl += (entry - current_price) * qty

                except Exception as e:
                    self.log.warning(f"Failed to calculate unrealized PnL for {symbol}: {e}")

            total_equity = float(usdt_total) + unrealized_pnl
            self.log.info(f"Real equity: USDT={usdt_total:.2f}, unrealized={unrealized_pnl:.2f}, total={total_equity:.2f}")

            return total_equity

        except Exception as e:
            self.log.error(f"Failed to fetch real equity from exchange: {e}")
            # Fallback to DB-based estimate
            return await self._get_equity_estimate()

    async def _get_daily_pnl(self) -> float:
        """
        Get today's realized PnL.

        Returns:
            PnL in USD for today
        """
        today_start = int(
            time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
        )

        cur = await self.conn.execute(
            "SELECT SUM(pnl_usd) FROM trades WHERE closed_at >= ?", (today_start,)
        )
        return (await cur.fetchone())[0] or 0.0

    # === POSITION CRUD ===

    async def add_position_async(self, position: Dict[str, Any]):
        """
        Add a new open position to database.

        Args:
            position: Position dict with all required fields
        """
        cols = ",".join(position.keys())
        qs = ",".join(["?"] * len(position))
        await self.conn.execute(
            f"INSERT OR REPLACE INTO positions ({cols}) VALUES ({qs})",
            tuple(position.values()),
        )
        await self.conn.commit()
        self.log.info(f"Position added: {position['symbol']}")

        # Increment orders today counter for LIVE_TEST_MODE
        await self._increment_orders_today()

    async def get_open_positions_async(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of position dicts
        """
        cur = await self.conn.execute("SELECT * FROM positions")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]

    async def update_position_async(self, position: Dict[str, Any]):
        """
        Update an existing position.

        Args:
            position: Position dict with symbol as primary key
        """
        keys = [k for k in position.keys() if k != 'symbol']
        sets = ", ".join([f"{k}=?" for k in keys])
        vals = [position[k] for k in keys] + [position['symbol']]
        await self.conn.execute(f"UPDATE positions SET {sets} WHERE symbol=?", vals)
        await self.conn.commit()
        self.log.debug(f"Position updated: {position['symbol']}")

    async def remove_position_async(self, symbol: str):
        """
        Remove a position from open positions.

        Args:
            symbol: Trading symbol
        """
        await self.conn.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
        await self.conn.commit()
        self.log.info(f"Position removed: {symbol}")

    async def save_closed_trade_async(
        self,
        position: Dict[str, Any],
        exit_price: float,
        pnl_usd: float,
        reason: str,
    ):
        """
        Save a closed trade to history.

        Args:
            position: Position dict
            exit_price: Exit price
            pnl_usd: Realized PnL in USD
            reason: Close reason (STOP_LOSS, TP_2R, etc.)
        """
        entry_price = position.get('entry_price', 0)
        size_usd = position.get('size_usd', 0)
        pnl_pct = (pnl_usd / size_usd * 100) if size_usd > 0 else 0
        initial_risk = position.get('initial_risk_usd', 1)
        r_multiple = (pnl_usd / initial_risk) if initial_risk > 0 else 0

        timestamp_open = position.get('timestamp_open', time.time())
        hold_time_hours = (time.time() - timestamp_open) / 3600

        await self.conn.execute(
            """
            INSERT INTO trades(
                symbol, side, engine, entry_price, exit_price,
                qty, pnl_usd, pnl_pct, r_multiple, reason,
                closed_at, hold_time_hours
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                position.get('symbol'),
                position.get('side'),
                position.get('engine'),
                entry_price,
                exit_price,
                position.get('qty'),
                float(pnl_usd),
                float(pnl_pct),
                float(r_multiple),
                reason,
                int(time.time()),
                hold_time_hours,
            ),
        )
        await self.conn.commit()
        self.log.info(
            f"Trade saved: {position.get('symbol')} | "
            f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%) | "
            f"R: {r_multiple:.2f}R | "
            f"Reason: {reason}"
        )

    async def save_equity_snapshot_async(self, exchange=None):
        """
        Save current equity snapshot for tracking.

        Args:
            exchange: Optional AsyncExchange instance for real equity
        """
        equity = await self.get_real_equity_async(exchange) if exchange else await self._get_equity_estimate()
        daily_pnl = await self._get_daily_pnl()

        cur = await self.conn.execute("SELECT COUNT(1) FROM positions")
        open_count = (await cur.fetchone())[0]

        await self.conn.execute(
            """
            INSERT INTO equity_snapshots(timestamp, equity, open_positions_count, daily_pnl)
            VALUES (?,?,?,?)
            """,
            (int(time.time()), equity, open_count, daily_pnl),
        )
        await self.conn.commit()

    # === LIVE_TEST_MODE TRACKING ===

    async def _increment_orders_today(self):
        """Increment daily order counter and reset if needed."""
        current_date = time.strftime("%Y-%m-%d")

        if current_date != self.orders_reset_date:
            # New day - reset counter
            self.orders_today = 0
            self.orders_reset_date = current_date
            self.log.info(f"Daily order counter reset (new day: {current_date})")

        self.orders_today += 1

    async def check_live_test_limits_async(
        self, size_usd: float, symbol: str
    ) -> Tuple[bool, float, str]:
        """
        Check LIVE_TEST_MODE limits.

        Args:
            size_usd: Requested order size in USD
            symbol: Trading symbol

        Returns:
            (allowed, adjusted_size_usd, reason)
        """
        if not getattr(self.settings, 'LIVE_TEST_MODE', False):
            return True, size_usd, "LIVE_TEST_MODE_DISABLED"

        max_orders = getattr(self.settings, 'LIVE_TEST_MAX_ORDERS_PER_DAY', 3)
        max_usd = getattr(self.settings, 'LIVE_TEST_MAX_USD_PER_ORDER', 7.50)

        # Reset counter if new day
        current_date = time.strftime("%Y-%m-%d")
        if current_date != self.orders_reset_date:
            self.orders_today = 0
            self.orders_reset_date = current_date
            self.log.info(f"LIVE_TEST_MODE: Daily counter reset (new day: {current_date})")

        # Check daily limit
        if self.orders_today >= max_orders:
            return False, 0.0, f"MAX_ORDERS_TODAY_{max_orders}"

        # Cap order size
        if size_usd > max_usd:
            self.log.info(
                f"LIVE_TEST_MODE: Capping order {symbol} from ${size_usd:.2f} to ${max_usd:.2f}"
            )
            return True, max_usd, "SIZE_CAPPED"

        return True, size_usd, "OK"

    async def get_recent_trades_async(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Get recent trades for analysis/autotuning.

        Args:
            limit: Max number of trades to fetch

        Returns:
            List of trade dicts
        """
        cur = await self.conn.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]
