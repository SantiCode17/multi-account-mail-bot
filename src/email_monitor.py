import asyncio
import imaplib
import socket

from loguru import logger

from src.database import Database
from src.email_parser import EmailParser
from src.models import EmailAccount, EmailMessage

IMAP_TIMEOUT_SECONDS = 30


class EmailMonitor:
    """Core IMAP monitoring engine.

    Uses the stdlib *imaplib* wrapped in ``asyncio.to_thread`` so that
    every blocking IMAP call runs in a thread-pool without stalling the
    event loop.
    """

    def __init__(self, database: Database, preview_length: int = 500) -> None:
        self._db = database
        self._parser = EmailParser(preview_length=preview_length)

    def _connect_imap(self, account: EmailAccount) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Create and return an authenticated IMAP connection (blocking)."""
        socket.setdefaulttimeout(IMAP_TIMEOUT_SECONDS)
        if account.use_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_server, account.imap_port)
        conn.login(account.email, account.password)
        return conn

    def _fetch_raw_messages(
        self,
        account: EmailAccount,
    ) -> list[tuple[str, bytes]]:
        """Connect, search INBOX for UNSEEN messages, and return raw data.

        Returns a list of ``(uid, raw_bytes)`` tuples.  This method runs
        entirely on a worker thread (called via ``to_thread``).
        """
        conn: imaplib.IMAP4_SSL | imaplib.IMAP4 | None = None
        try:
            conn = self._connect_imap(account)
            conn.select("INBOX", readonly=True)

            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []

            msg_nums = data[0].split()
            results: list[tuple[str, bytes]] = []

            for num in msg_nums:
                try:
                    status, msg_data = conn.fetch(num, "(RFC822)")
                    if status != "OK" or not msg_data or msg_data[0] is None:
                        continue
                    raw_email = msg_data[0]
                    if isinstance(raw_email, tuple) and len(raw_email) >= 2:
                        results.append((num.decode(), raw_email[1]))
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch message {num} for {email}: {err}",
                        num=num,
                        email=account.email,
                        err=exc,
                    )
            return results

        except imaplib.IMAP4.error as exc:
            logger.error(
                "IMAP error for {email}: {err}",
                email=account.email,
                err=exc,
            )
            return []
        except socket.timeout:
            logger.warning(
                "Connection timeout for {email} ({server})",
                email=account.email,
                server=account.imap_server,
            )
            return []
        except socket.gaierror as exc:
            logger.error(
                "DNS resolution failed for {server} ({email}): {err}",
                server=account.imap_server,
                email=account.email,
                err=exc,
            )
            return []
        except ConnectionRefusedError:
            logger.error(
                "Connection refused by {server}:{port} ({email})",
                server=account.imap_server,
                port=account.imap_port,
                email=account.email,
            )
            return []
        except OSError as exc:
            logger.error(
                "OS/network error for {email}: {err}",
                email=account.email,
                err=exc,
            )
            return []
        except Exception as exc:
            logger.error(
                "Unexpected error checking {email}: {err}",
                email=account.email,
                err=exc,
            )
            return []
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:
                    pass

    async def fetch_new_emails(
        self, account: EmailAccount
    ) -> list[EmailMessage]:
        """Return only truly new (unseen in DB) emails for *account*."""
        raw_messages = await asyncio.to_thread(
            self._fetch_raw_messages, account
        )
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
                    email=account.email,
                    err=exc,
                )
                continue

            already_seen = await self._db.is_seen(
                account.email, parsed.message_id
            )
            if already_seen:
                continue

            new_messages.append(parsed)
            bulk_seen.append((account.email, parsed.message_id))

        if bulk_seen:
            await self._db.mark_seen_bulk(bulk_seen)

        return new_messages
