import os
from datetime import datetime, timedelta, timezone

import aiosqlite
from loguru import logger

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS seen_emails (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_email TEXT NOT NULL,
    message_id  TEXT    NOT NULL,
    seen_at     TEXT    NOT NULL,
    UNIQUE(account_email, message_id)
)
"""

_INDEX = """
CREATE INDEX IF NOT EXISTS idx_seen_emails_account
ON seen_emails(account_email, message_id)
"""


class Database:
    """Async SQLite store for tracking already-seen email Message-IDs."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create the database file, table, and index if they don't exist."""
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute(_CREATE_TABLE)
        await self._connection.execute(_INDEX)
        await self._connection.commit()
        logger.info("Database initialized at {path}", path=self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.debug("Database connection closed")

    def _conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._connection

    async def is_seen(self, account_email: str, message_id: str) -> bool:
        """Check whether a message has already been recorded."""
        cursor = await self._conn().execute(
            "SELECT 1 FROM seen_emails WHERE account_email = ? AND message_id = ?",
            (account_email, message_id),
        )
        row = await cursor.fetchone()
        return row is not None

    async def mark_seen(self, account_email: str, message_id: str) -> None:
        """Record a single message as seen (ignores duplicates)."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn().execute(
            "INSERT OR IGNORE INTO seen_emails (account_email, message_id, seen_at) "
            "VALUES (?, ?, ?)",
            (account_email, message_id, now),
        )
        await self._conn().commit()

    async def mark_seen_bulk(
        self, entries: list[tuple[str, str]]
    ) -> None:
        """Record multiple messages as seen in one transaction.

        Each entry is a tuple of (account_email, message_id).
        """
        if not entries:
            return
        now = datetime.now(timezone.utc).isoformat()
        await self._conn().executemany(
            "INSERT OR IGNORE INTO seen_emails (account_email, message_id, seen_at) "
            "VALUES (?, ?, ?)",
            [(acct, mid, now) for acct, mid in entries],
        )
        await self._conn().commit()
        logger.debug("Bulk-marked {count} messages as seen", count=len(entries))

    async def cleanup_old(self, days: int = 30) -> int:
        """Delete records older than *days*. Returns the number of rows removed."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._conn().execute(
            "DELETE FROM seen_emails WHERE seen_at < ?", (cutoff,)
        )
        await self._conn().commit()
        removed = cursor.rowcount
        if removed:
            logger.info(
                "Cleaned up {count} seen-email records older than {days} days",
                count=removed,
                days=days,
            )
        return removed
