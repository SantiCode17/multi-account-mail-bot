import asyncio
import email as email_lib
import imaplib
import socket
from datetime import datetime, timezone

from loguru import logger

from src.database import Database
from src.email_parser import EmailParser
from src.models import EmailAccount, EmailMessage
from src import oauth_manager

IMAP_TIMEOUT_SECONDS = 15


class EmailMonitor:
    """Core IMAP monitoring engine.

    Strategy
    --------
    1. **Seed** (first run): fetch *only* the Message-ID header of every
       current UNSEEN email via ``BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]``.
       This is extremely lightweight and stores *real* Message-IDs so that
       the normal cycle can recognise them.
    2. **Normal cycle**: search ``UNSEEN SINCE <today>``, download only
       messages not yet in the DB.  The ``SINCE`` filter avoids
       re-evaluating thousands of old unread emails every cycle.
    """

    def __init__(self, database: Database, preview_length: int = 500) -> None:
        self._db = database
        self._parser = EmailParser(preview_length=preview_length)

    # ── IMAP connection ─────────────────────────────────────────────

    @staticmethod
    def _connect_imap(account: EmailAccount) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Create and return an authenticated IMAP connection.

        * Gmail accounts → XOAuth2 (token auto-refreshed).
        * Everything else → plain password login.
        """
        socket.setdefaulttimeout(IMAP_TIMEOUT_SECONDS)

        if account.use_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_server, account.imap_port)

        # Gmail → OAuth2
        if "gmail" in account.imap_server.lower():
            token = oauth_manager.get_access_token(account.email)
            if token:
                auth_str = (
                    f"user={account.email}\x01"
                    f"auth=Bearer {token}\x01\x01"
                )
                conn.authenticate("XOAUTH2", lambda _: auth_str.encode())
                return conn
            # No token → fall through to password (will likely fail
            # for 2FA accounts, but lets non-2FA ones still work).

        # Plain password login (supports non-ASCII passwords)
        password = account.password
        try:
            conn.login(account.email, password)
        except imaplib.IMAP4.error:
            # Retry with UTF-8 encoded password for non-ASCII chars
            if any(ord(c) > 127 for c in password):
                conn2 = imaplib.IMAP4_SSL(account.imap_server, account.imap_port) if account.use_ssl else imaplib.IMAP4(account.imap_server, account.imap_port)
                conn2._encoding = "utf-8"
                conn2.login(account.email, password)
                return conn2
            raise
        return conn

    @staticmethod
    def _safe_logout(conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None) -> None:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass

    # ── Seed (first run — lightweight header-only fetch) ────────────

    def _fetch_all_unseen_message_ids(self, account: EmailAccount) -> list[str]:
        """Return the real Message-ID headers of every current UNSEEN email.

        Uses ``BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]`` — only a few bytes
        per message, no body, no attachments, doesn't mark as read.
        """
        conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        try:
            conn = self._connect_imap(account)
            conn.select("INBOX", readonly=True)

            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []

            msg_nums = data[0].split()
            if not msg_nums:
                return []

            logger.info(
                "Seed: fetching Message-ID headers for {n} UNSEEN emails in {email}",
                n=len(msg_nums), email=account.email,
            )

            message_ids: list[str] = []

            # Fetch in batches of 100 to avoid IMAP command-line length limits
            batch_size = 100
            for i in range(0, len(msg_nums), batch_size):
                batch = msg_nums[i : i + batch_size]
                num_set = b",".join(batch)
                try:
                    status, fetch_data = conn.fetch(
                        num_set,
                        "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])",
                    )
                    if status != "OK" or not fetch_data:
                        continue

                    for item in fetch_data:
                        if isinstance(item, tuple) and len(item) >= 2:
                            header_bytes = item[1]
                            if isinstance(header_bytes, bytes):
                                try:
                                    msg = email_lib.message_from_bytes(header_bytes)
                                    mid = msg.get("Message-ID", "").strip()
                                    if mid:
                                        message_ids.append(mid)
                                except Exception:
                                    pass
                except Exception as exc:
                    logger.warning(
                        "Seed batch fetch failed for {email}: {err}",
                        email=account.email, err=exc,
                    )

            return message_ids

        except Exception as exc:
            logger.warning(
                "Seed fetch failed for {email}: {err}",
                email=account.email, err=exc,
            )
            return []
        finally:
            self._safe_logout(conn)

    async def seed_existing_emails(self, account: EmailAccount) -> int:
        """Mark every currently-UNSEEN email as already-seen using its
        **real** Message-ID (fetched via lightweight header peek).

        Returns the number of emails seeded.
        """
        message_ids = await asyncio.to_thread(
            self._fetch_all_unseen_message_ids, account,
        )
        if not message_ids:
            return 0

        bulk = [(account.email, mid) for mid in message_ids]
        await self._db.mark_seen_bulk(bulk)
        return len(message_ids)

    # ── Normal fetch (SINCE-filtered) ───────────────────────────────

    @staticmethod
    def _imap_date_str() -> str:
        """Return today's date as IMAP-compatible (e.g. ``01-Jun-2025``)."""
        return datetime.now(timezone.utc).strftime("%d-%b-%Y")

    def _fetch_recent_unseen(self, account: EmailAccount) -> list[tuple[str, bytes]]:
        """Search INBOX for ``UNSEEN SINCE <today>``, download full RFC822.

        The ``SINCE`` filter limits the search to today's messages,
        avoiding re-download of thousands of old unread emails.

        Returns a list of ``(uid_str, raw_bytes)`` tuples.
        """
        conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        try:
            conn = self._connect_imap(account)
            conn.select("INBOX", readonly=True)

            since = self._imap_date_str()
            status, data = conn.search(None, f"(UNSEEN SINCE {since})")
            if status != "OK" or not data or not data[0]:
                return []

            msg_nums = data[0].split()
            results: list[tuple[str, bytes]] = []

            for num in msg_nums:
                try:
                    status, msg_data = conn.fetch(num, "(BODY.PEEK[])")
                    if status != "OK" or not msg_data or msg_data[0] is None:
                        continue
                    raw_email = msg_data[0]
                    if isinstance(raw_email, tuple) and len(raw_email) >= 2:
                        results.append((num.decode(), raw_email[1]))
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch message {num} for {email}: {err}",
                        num=num, email=account.email, err=exc,
                    )

            return results

        except imaplib.IMAP4.error:
            raise  # Let scheduler handle auth failures
        except socket.timeout:
            logger.debug(
                "Timeout for {email}",
                email=account.email,
            )
            return []
        except socket.gaierror:
            return []
        except ConnectionRefusedError:
            return []
        except OSError:
            return []
        except Exception:
            return []
        finally:
            self._safe_logout(conn)

    async def fetch_new_emails(self, account: EmailAccount) -> list[EmailMessage]:
        """Return only truly new (unseen in DB) emails for *account*.

        Uses ``SINCE <today>`` IMAP filter so only recent messages are
        evaluated.
        """
        raw_messages = await asyncio.to_thread(self._fetch_recent_unseen, account)
        if not raw_messages:
            return []

        new_messages: list[EmailMessage] = []
        bulk_seen: list[tuple[str, str]] = []

        for _uid, raw_bytes in raw_messages:
            try:
                parsed = self._parser.parse_email(raw_bytes, account.email)
            except Exception as exc:
                logger.warning(
                    "Parse failure for a message in {email}: {err}",
                    email=account.email, err=exc,
                )
                continue

            already_seen = await self._db.is_seen(account.email, parsed.message_id)
            if already_seen:
                continue

            new_messages.append(parsed)
            bulk_seen.append((account.email, parsed.message_id))

        if bulk_seen:
            await self._db.mark_seen_bulk(bulk_seen)

        return new_messages
