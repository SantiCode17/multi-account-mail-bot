import asyncio
import html

import telegram
import telegram.error
from loguru import logger

from src.models import EmailMessage, TelegramConfig

MIN_SEND_INTERVAL = 0.05
TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramNotifier:
    """Sends formatted email notifications to a Telegram chat."""

    def __init__(self, config: TelegramConfig) -> None:
        self._token = config.bot_token
        self._chat_id = config.chat_id
        self._bot = telegram.Bot(token=self._token)
        self._send_lock = asyncio.Lock()

    async def validate(self) -> bool:
        """Verify the bot token is valid by calling getMe."""
        try:
            me = await self._bot.get_me()
            logger.info(
                "Telegram bot connected: @{username}",
                username=me.username,
            )
            return True
        except telegram.error.InvalidToken:
            logger.error("Invalid Telegram bot token")
            return False
        except Exception as exc:
            logger.error("Failed to validate Telegram bot: {err}", err=exc)
            return False

    @staticmethod
    def _format_message(msg: EmailMessage) -> str:
        """Build the Telegram HTML notification matching the required format."""
        safe_email = html.escape(msg.account_email)
        safe_subject = html.escape(msg.subject) if msg.subject else "(no subject)"
        safe_sender = html.escape(msg.sender) if msg.sender else "Unknown"
        safe_body = html.escape(msg.body_preview) if msg.body_preview else ""
        safe_date = html.escape(msg.date) if msg.date else ""

        lines = [
            f"❗ You've received a new message at <b>{safe_email}</b>",
            "",
            f"<b>From:</b> {safe_sender}",
            f"<b>Subject:</b> {safe_subject}",
            "",
        ]

        if safe_body:
            lines.append(safe_body)
            lines.append("")

        if safe_date:
            lines.append(f"📅 {safe_date}")

        return "\n".join(lines)[:TELEGRAM_MESSAGE_LIMIT]

    async def send_notification(
        self, message: EmailMessage, max_retries: int = 3
    ) -> bool:
        """Send a single notification with retry and rate-limit handling."""
        text = self._format_message(message)

        for attempt in range(1, max_retries + 1):
            try:
                async with self._send_lock:
                    await self._bot.send_message(
                        chat_id=self._chat_id,
                        text=text,
                        parse_mode=telegram.constants.ParseMode.HTML,
                    )
                    await asyncio.sleep(MIN_SEND_INTERVAL)
                logger.info(
                    "Notification sent for {email} — {subject}",
                    email=message.account_email,
                    subject=message.subject[:60],
                )
                return True

            except telegram.error.RetryAfter as exc:
                wait = exc.retry_after + 1
                logger.warning(
                    "Rate-limited by Telegram, retrying in {s}s",
                    s=wait,
                )
                await asyncio.sleep(wait)

            except telegram.error.Forbidden:
                logger.error(
                    "Bot was blocked or chat {cid} not accessible",
                    cid=self._chat_id,
                )
                return False

            except telegram.error.BadRequest as exc:
                logger.error(
                    "Telegram BadRequest: {err}",
                    err=exc,
                )
                return False

            except telegram.error.TimedOut:
                logger.warning(
                    "Telegram request timed out (attempt {a}/{m})",
                    a=attempt,
                    m=max_retries,
                )
                await asyncio.sleep(2 * attempt)

            except telegram.error.NetworkError as exc:
                logger.warning(
                    "Telegram network error (attempt {a}/{m}): {err}",
                    a=attempt,
                    m=max_retries,
                    err=exc,
                )
                await asyncio.sleep(2 * attempt)

            except Exception as exc:
                logger.error(
                    "Unexpected Telegram error: {err}",
                    err=exc,
                )
                return False

        logger.error(
            "Failed to send notification after {n} retries for {email}",
            n=max_retries,
            email=message.account_email,
        )
        return False

    async def send_notifications(self, messages: list[EmailMessage]) -> int:
        """Send notifications for a list of messages. Returns success count."""
        sent = 0
        for msg in messages:
            ok = await self.send_notification(msg)
            if ok:
                sent += 1
        return sent

    async def send_raw(self, text: str) -> bool:
        """Send a plain text message (used for status/startup messages)."""
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode=telegram.constants.ParseMode.HTML,
            )
            return True
        except Exception as exc:
            logger.error("Failed to send raw Telegram message: {err}", err=exc)
            return False
