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
        try:
            cursor = await self._conn().execute(
                "SELECT 1 FROM seen_emails WHERE account_email = ? AND message_id = ?",
                (account_email, message_id),
            )
            row = await cursor.fetchone()
            return row is not None
        except Exception as exc:
            logger.error("DB is_seen query failed: {err}", err=exc)
            return False

    async def mark_seen(self, account_email: str, message_id: str) -> None:
        """Record a single message as seen (ignores duplicates)."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            await self._conn().execute(
                "INSERT OR IGNORE INTO seen_emails (account_email, message_id, seen_at) "
                "VALUES (?, ?, ?)",
                (account_email, message_id, now),
            )
            await self._conn().commit()
        except Exception as exc:
            logger.error("DB mark_seen failed: {err}", err=exc)

    async def mark_seen_bulk(
        self, entries: list[tuple[str, str]]
    ) -> None:
        """Record multiple messages as seen in one transaction.

        Each entry is a tuple of (account_email, message_id).
        """
        if not entries:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            await self._conn().executemany(
                "INSERT OR IGNORE INTO seen_emails (account_email, message_id, seen_at) "
                "VALUES (?, ?, ?)",
                [(acct, mid, now) for acct, mid in entries],
            )
            await self._conn().commit()
            logger.debug("Bulk-marked {count} messages as seen", count=len(entries))
        except Exception as exc:
            logger.error("DB mark_seen_bulk failed: {err}", err=exc)

    async def cleanup_old(self, days: int = 30) -> int:
        """Delete records older than *days*. Returns the number of rows removed."""
        try:
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
        except Exception as exc:
            logger.error("DB cleanup_old failed: {err}", err=exc)
            return 0

    async def get_recent(self, limit: int = 10) -> list[dict]:
        """Return the most recent seen-email entries."""
        try:
            cursor = await self._conn().execute(
                "SELECT account_email, message_id, seen_at "
                "FROM seen_emails ORDER BY seen_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "account_email": row["account_email"],
                    "message_id": row["message_id"],
                    "seen_at": row["seen_at"],
                }
                for row in rows
            ]
        except Exception as exc:
            logger.error("DB get_recent failed: {err}", err=exc)
            return []

    async def get_account_stats(self) -> list[dict]:
        """Return per-account counts of seen emails."""
        try:
            cursor = await self._conn().execute(
                "SELECT account_email, COUNT(*) as total "
                "FROM seen_emails GROUP BY account_email "
                "ORDER BY total DESC"
            )
            rows = await cursor.fetchall()
            return [
                {"account_email": row["account_email"], "total": row["total"]}
                for row in rows
            ]
        except Exception as exc:
            logger.error("DB get_account_stats failed: {err}", err=exc)
            return []

    async def get_total_count(self) -> int:
        """Return total number of tracked emails."""
        try:
            cursor = await self._conn().execute(
                "SELECT COUNT(*) as cnt FROM seen_emails"
            )
            row = await cursor.fetchone()
            return row["cnt"] if row else 0
        except Exception as exc:
            logger.error("DB get_total_count failed: {err}", err=exc)
            return 0
