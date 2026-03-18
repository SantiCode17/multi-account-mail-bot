"""Telegram notification service with multicast delivery.

Notifications are sent to **every** user who currently holds an
active authenticated session, so anyone logged in from any device
receives real-time email alerts.
"""

from __future__ import annotations

import asyncio
import html
from typing import TYPE_CHECKING, Callable, Coroutine

import telegram
import telegram.error
from loguru import logger

from src.models import EmailMessage, TelegramConfig

if TYPE_CHECKING:
    pass

MIN_SEND_INTERVAL = 0.05
TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramNotifier:
    """Sends formatted email notifications to all authenticated users."""

    def __init__(self, config: TelegramConfig) -> None:
        self._token = config.bot_token
        self._fallback_chat_id = config.chat_id  # used for system messages only
        self._bot = telegram.Bot(token=self._token)
        self._send_lock = asyncio.Lock()
        # Will be set by scheduler after BotHandlers is ready
        self._get_recipients: Callable[[], Coroutine[None, None, list[int]]] | None = None

    def set_recipient_provider(
        self, provider: Callable[[], Coroutine[None, None, list[int]]],
    ) -> None:
        """Register a coroutine that returns the list of active chat_ids."""
        self._get_recipients = provider

    async def _get_target_ids(self) -> list[int]:
        """Return all chat_ids that should receive notifications."""
        if self._get_recipients is not None:
            ids = await self._get_recipients()
            if ids:
                return ids
        # Fallback: admin chat_id from config
        return [int(self._fallback_chat_id)] if self._fallback_chat_id else []

    # ── Validation ──────────────────────────────────────────────────

    async def validate(self) -> bool:
        """Verify the bot token is valid by calling getMe."""
        try:
            me = await self._bot.get_me()
            logger.info("Telegram bot connected: @{username}", username=me.username)
            return True
        except telegram.error.InvalidToken:
            logger.error("Invalid Telegram bot token")
            return False
        except Exception as exc:
            logger.error("Failed to validate Telegram bot: {err}", err=exc)
            return False

    # ── Formatting ──────────────────────────────────────────────────

    @staticmethod
    def _format_message(msg: EmailMessage) -> str:
        safe_email = html.escape(msg.account_email)
        safe_subject = html.escape(msg.subject) if msg.subject else "(no subject)"
        safe_sender = html.escape(msg.sender) if msg.sender else "Unknown"
        safe_body = html.escape(msg.body_preview) if msg.body_preview else ""
        safe_date = html.escape(msg.date) if msg.date else ""

        lines = [
            "━━━━━━━━━━━━━━━━━━━━━━",
            "📩 <b>New email received</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📬 <b>Account:</b> <code>{safe_email}</code>",
            f"👤 <b>From:</b> {safe_sender}",
            f"📋 <b>Subject:</b> {safe_subject}",
        ]
        if safe_date:
            lines.append(f"📅 <b>Date:</b> {safe_date}")
        if safe_body:
            lines.append("")
            lines.append(f"💬 <i>{safe_body}</i>")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)[:TELEGRAM_MESSAGE_LIMIT]

    # ── Sending ─────────────────────────────────────────────────────

    async def _send_to(self, chat_id: int, text: str, max_retries: int = 3) -> bool:
        """Send a message to a single chat_id with retry logic."""
        for attempt in range(1, max_retries + 1):
            try:
                async with self._send_lock:
                    await self._bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=telegram.constants.ParseMode.HTML,
                    )
                    await asyncio.sleep(MIN_SEND_INTERVAL)
                return True

            except telegram.error.RetryAfter as exc:
                await asyncio.sleep(exc.retry_after + 1)
            except telegram.error.Forbidden:
                logger.warning("Bot blocked by chat_id={cid}", cid=chat_id)
                return False
            except telegram.error.BadRequest as exc:
                logger.error("BadRequest for chat_id={cid}: {err}", cid=chat_id, err=exc)
                return False
            except telegram.error.TimedOut:
                await asyncio.sleep(2 * attempt)
            except telegram.error.NetworkError:
                await asyncio.sleep(2 * attempt)
            except Exception as exc:
                logger.error("Unexpected error sending to {cid}: {err}", cid=chat_id, err=exc)
                return False

        return False

    async def send_notification(self, message: EmailMessage) -> int:
        """Send one email notification to ALL authenticated users.

        Returns the number of users who successfully received it.
        """
        text = self._format_message(message)
        targets = await self._get_target_ids()
        if not targets:
            return 0

        delivered = 0
        for cid in targets:
            if await self._send_to(cid, text):
                delivered += 1

        logger.info(
            "Notification: {email} — {subj} → {ok}/{total} recipients",
            email=message.account_email,
            subj=message.subject[:50],
            ok=delivered,
            total=len(targets),
        )
        return delivered

    async def send_notifications(self, messages: list[EmailMessage]) -> int:
        """Send multiple notifications. Returns total successful deliveries."""
        total = 0
        for msg in messages:
            total += await self.send_notification(msg)
        return total

    async def send_raw(self, text: str) -> bool:
        """Send a system/status message to all authenticated users.

        Falls back to the admin chat_id if no sessions exist.
        """
        targets = await self._get_target_ids()
        if not targets:
            return False

        ok = False
        for cid in targets:
            if await self._send_to(cid, text):
                ok = True
        return ok
