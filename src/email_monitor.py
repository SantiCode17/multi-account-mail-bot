import asyncio
import email as email_lib
import imaplib
import socket
from datetime import datetime, timezone

from loguru import logger

from src.database import Database
from src.email_parser import EmailParser
from src.models import EmailAccount, EmailMessage
from src.oauth_manager import OAuthTokenManager, GmailOAuthClient

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
        """Create and return an authenticated IMAP connection (blocking).
        
        For Gmail accounts: automatically uses OAuth2 token if available,
        falls back to password authentication.
        
        For other providers: uses password authentication directly.
        """
        socket.setdefaulttimeout(IMAP_TIMEOUT_SECONDS)
        
        # Try OAuth2 first for Gmail accounts
        if "gmail" in account.imap_server.lower():
            oauth_token = OAuthTokenManager.load_token(account.email)
            if oauth_token and oauth_token.get("access_token"):
                try:
                    return EmailMonitor._connect_imap_oauth2(account, oauth_token)
                except Exception as e:
                    logger.warning(
                        "OAuth2 authentication failed for {email}, falling back to password: {e}",
                        email=account.email,
                        e=e,
                    )
        
        # Fall back to password authentication
        return EmailMonitor._connect_imap_password(account)

    @staticmethod
    def _connect_imap_password(
        account: EmailAccount,
    ) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Connect using standard password authentication."""
        if account.use_ssl:
            conn = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
        else:
            conn = imaplib.IMAP4(account.imap_server, account.imap_port)

        try:
            conn.login(account.email, account.password)
        except imaplib.IMAP4.error as e:
            conn.logout()
            raise ValueError(
                f"IMAP login failed for {account.email}. "
                f"For Gmail with 2FA: Run `python auth_setup.py` to generate OAuth2 tokens. "
                f"Error: {str(e)}"
            ) from e
        return conn

    @staticmethod
    def _connect_imap_oauth2(
        account: EmailAccount, oauth_token: dict
    ) -> imaplib.IMAP4_SSL | imaplib.IMAP4:
        """Connect using OAuth2 authentication."""
        access_token = oauth_token.get("access_token")
        if not access_token:
            raise ValueError(f"No access token for {account.email}")

        # Build XOAuth2 authentication string
        auth_string = f"user={account.email}\x01auth=Bearer {access_token}\x01\x01"

        conn = imaplib.IMAP4_SSL(account.imap_server, account.imap_port)
        try:
            conn.authenticate("XOAUTH2", lambda x: auth_string.encode())
        except imaplib.IMAP4.error as e:
            conn.logout()
            raise ValueError(
                f"XOAuth2 authentication failed for {account.email}. "
                f"Token may be expired. Run `python auth_setup.py` to refresh. "
                f"Error: {str(e)}"
            ) from e

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
                    status, msg_data = conn.fetch(num, "(RFC822)")
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

        except imaplib.IMAP4.error as exc:
            logger.error("IMAP error for {email}: {err}", email=account.email, err=exc)
            return []
        except socket.timeout:
            logger.warning(
                "Connection timeout for {email} ({server})",
                email=account.email, server=account.imap_server,
            )
            return []
        except socket.gaierror as exc:
            logger.error(
                "DNS resolution failed for {server} ({email}): {err}",
                server=account.imap_server, email=account.email, err=exc,
            )
            return []
        except ConnectionRefusedError:
            logger.error(
                "Connection refused by {server}:{port} ({email})",
                server=account.imap_server, port=account.imap_port, email=account.email,
            )
            return []
        except OSError as exc:
            logger.error("OS/network error for {email}: {err}", email=account.email, err=exc)
            return []
        except Exception as exc:
            logger.error("Unexpected error checking {email}: {err}", email=account.email, err=exc)
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
