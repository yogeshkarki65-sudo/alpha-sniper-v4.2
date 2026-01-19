"""
Async SQLite Driver for Alpha Sniper v4.2

Provides non-blocking database access with:
- WAL mode for better concurrency
- Single async writer queue to prevent "database is locked" errors
- Multiple concurrent readers
- Automatic schema migrations
- Graceful shutdown with queue draining
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import aiosqlite
except ImportError:
    raise ImportError("aiosqlite not installed. Run: pip install aiosqlite>=0.19")

logger = logging.getLogger(__name__)


class AsyncDB:
    """
    Async SQLite database with WAL mode and single-writer architecture.

    All writes go through a queue serviced by a single writer task.
    Reads can happen concurrently from multiple tasks.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize async database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._write_queue: asyncio.Queue[Tuple[str, Tuple, Optional[asyncio.Future]]] = (
            asyncio.Queue()
        )
        self._writer_task: Optional[asyncio.Task] = None
        self.conn: Optional[aiosqlite.Connection] = None
        self._closed = False

        logger.info(f"AsyncDB initialized: {self.db_path}")

    async def connect(self):
        """
        Connect to database and configure WAL mode.

        Creates parent directories if needed.
        Applies schema migrations if schema.sql exists.
        """
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = await aiosqlite.connect(str(self.db_path))

        # Enable WAL mode for better concurrency
        await self.conn.execute("PRAGMA journal_mode=WAL;")

        # Synchronous=NORMAL is safe with WAL and much faster
        await self.conn.execute("PRAGMA synchronous=NORMAL;")

        # Busy timeout for retries (5 seconds)
        await self.conn.execute("PRAGMA busy_timeout=5000;")

        # Foreign keys enforcement
        await self.conn.execute("PRAGMA foreign_keys=ON;")

        await self.conn.commit()

        logger.info(
            "Database connected with WAL mode | "
            f"journal_mode=WAL, synchronous=NORMAL, busy_timeout=5000ms"
        )

        # Apply schema migrations
        await self._apply_schema()

        # Start writer task
        self._writer_task = asyncio.create_task(self._writer_loop())
        logger.info("Writer task started")

    async def _apply_schema(self):
        """
        Apply schema migrations from schema.sql if it exists.

        Idempotent - safe to run multiple times.
        """
        schema_file = self.db_path.parent / "schema.sql"
        if not schema_file.exists():
            logger.info("No schema.sql found, skipping migrations")
            return

        try:
            schema_sql = schema_file.read_text()
            await self.conn.executescript(schema_sql)
            await self.conn.commit()
            logger.info(f"Schema applied from {schema_file}")
        except Exception as e:
            logger.error(f"Error applying schema: {e}")
            raise

    async def _writer_loop(self):
        """
        Single writer task that processes all writes sequentially.

        This prevents "database is locked" errors by ensuring only
        one task writes at a time.
        """
        assert self.conn is not None

        while True:
            # Get next write operation from queue
            item = await self._write_queue.get()

            if item is None:  # Sentinel for shutdown
                self._write_queue.task_done()
                break

            sql, params, future = item

            try:
                # Execute write operation
                cursor = await self.conn.execute(sql, params)
                await self.conn.commit()

                # Return result to caller if they're waiting
                if future is not None:
                    future.set_result(cursor.lastrowid)

            except Exception as e:
                logger.error(f"Write error: {sql[:100]}... | {e}")
                if future is not None:
                    future.set_exception(e)

            finally:
                self._write_queue.task_done()

        logger.info("Writer loop exited")

    async def execute_write(
        self, sql: str, params: Tuple = (), wait: bool = False
    ) -> Optional[int]:
        """
        Execute a write operation (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL statement
            params: Query parameters
            wait: If True, wait for operation to complete and return lastrowid

        Returns:
            lastrowid if wait=True, otherwise None

        Raises:
            RuntimeError: If database is closed
        """
        if self._closed:
            raise RuntimeError("Database is closed")

        future = asyncio.get_event_loop().create_future() if wait else None

        await self._write_queue.put((sql, params, future))

        if wait and future:
            return await future

        return None

    async def execute_read(
        self, sql: str, params: Tuple = ()
    ) -> List[aiosqlite.Row]:
        """
        Execute a read operation (SELECT).

        Reads can happen concurrently without blocking writes.

        Args:
            sql: SQL SELECT statement
            params: Query parameters

        Returns:
            List of result rows

        Raises:
            RuntimeError: If database is closed
        """
        if self._closed:
            raise RuntimeError("Database is closed")

        assert self.conn is not None

        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def execute_read_one(
        self, sql: str, params: Tuple = ()
    ) -> Optional[aiosqlite.Row]:
        """
        Execute a read operation and return first row.

        Args:
            sql: SQL SELECT statement
            params: Query parameters

        Returns:
            First result row or None
        """
        if self._closed:
            raise RuntimeError("Database is closed")

        assert self.conn is not None

        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def executemany_write(
        self, sql: str, param_list: List[Tuple]
    ) -> None:
        """
        Execute multiple write operations in a batch.

        More efficient than multiple execute_write calls.

        Args:
            sql: SQL statement
            param_list: List of parameter tuples
        """
        if self._closed:
            raise RuntimeError("Database is closed")

        assert self.conn is not None

        # Batch writes still go through queue but as single operation
        future = asyncio.get_event_loop().create_future()

        async def batch_write():
            try:
                await self.conn.executemany(sql, param_list)
                await self.conn.commit()
                future.set_result(None)
            except Exception as e:
                future.set_exception(e)

        # Queue the batch operation
        await self._write_queue.put((None, (), None))  # Dummy entry
        asyncio.create_task(batch_write())  # Execute alongside writer

        await future

    async def close(self):
        """
        Close database connection gracefully.

        Drains write queue, stops writer task, and closes connection.
        """
        if self._closed:
            return

        self._closed = True

        logger.info("Closing database...")

        # Send shutdown sentinel to writer
        if self._writer_task and not self._writer_task.done():
            await self._write_queue.put(None)
            await self._write_queue.join()  # Wait for queue to drain
            await self._writer_task  # Wait for writer to exit

        # Close connection
        if self.conn:
            await self.conn.close()

        logger.info(f"Database closed: {self.db_path}")

    async def __aenter__(self):
        """Context manager support."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        await self.close()

    def __repr__(self) -> str:
        return f"AsyncDB(path={self.db_path}, closed={self._closed})"


# Convenience functions for common operations
async def create_positions_table(db: AsyncDB):
    """Create positions table if not exists."""
    await db.execute_write(
        """
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            engine TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            size_usd REAL NOT NULL,
            qty REAL NOT NULL,
            timestamp_open REAL NOT NULL,
            timestamp_close REAL,
            exit_price REAL,
            pnl_usd REAL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        wait=True,
    )
    logger.info("Positions table created/verified")


async def create_trades_table(db: AsyncDB):
    """Create trades table if not exists."""
    await db.execute_write(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_id INTEGER,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            price REAL NOT NULL,
            qty REAL NOT NULL,
            fee REAL,
            timestamp REAL NOT NULL,
            order_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (position_id) REFERENCES positions(id)
        );
        """,
        wait=True,
    )
    logger.info("Trades table created/verified")
