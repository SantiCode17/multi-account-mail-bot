import html
import time

from loguru import logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import load_accounts
from src.database import Database
from src.models import AppConfig


WELCOME_TEXT = (
    "📬 <b>Welcome to Inbox Bridge</b>\n"
    "\n"
    "I monitor multiple email accounts and notify you instantly "
    "when new messages arrive.\n"
    "\n"
    "Use /help to see available commands."
)

HELP_TEXT = (
    "📬 <b>Inbox Bridge — Commands</b>\n"
    "\n"
    "  /start — Show welcome message\n"
    "  /status — Monitor status and statistics\n"
    "  /accounts — List monitored email accounts\n"
    "  /history — Show last 10 detected emails\n"
    "  /help — Show this help message\n"
)


class BotHandlers:
    """Registers interactive Telegram bot commands."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self._config = config
        self._db = database
        self._start_time = time.monotonic()
        self._cycles_completed = 0
        self._total_notifications = 0

    def increment_cycles(self) -> None:
        self._cycles_completed += 1

    def add_notifications(self, count: int) -> None:
        self._total_notifications += count

    def register(self, app: Application) -> None:
        """Register all command handlers on the given Application."""
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("accounts", self._cmd_accounts))
        app.add_handler(CommandHandler("history", self._cmd_history))
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text)
        )
        logger.info("Bot command handlers registered")

    async def _cmd_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                WELCOME_TEXT, parse_mode=ParseMode.HTML
            )

    async def _cmd_help(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                HELP_TEXT, parse_mode=ParseMode.HTML
            )

    async def _cmd_status(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_message:
            return

        uptime_s = int(time.monotonic() - self._start_time)
        hours, remainder = divmod(uptime_s, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

        try:
            account_count = len(
                load_accounts(self._config.accounts_config_path)
            )
        except Exception:
            account_count = len(self._config.accounts)

        total_tracked = await self._db.get_total_count()
        interval = self._config.monitor.check_interval

        text = (
            "📊 <b>Monitor Status</b>\n"
            "\n"
            f"  ⏱ Uptime: <b>{uptime_str}</b>\n"
            f"  📧 Accounts monitored: <b>{account_count}</b>\n"
            f"  🔄 Cycles completed: <b>{self._cycles_completed}</b>\n"
            f"  📨 Notifications sent: <b>{self._total_notifications}</b>\n"
            f"  🗄 Emails tracked in DB: <b>{total_tracked}</b>\n"
            f"  ⏰ Check interval: <b>{interval}s</b>\n"
        )
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.HTML
        )

    async def _cmd_accounts(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_message:
            return

        try:
            accounts = load_accounts(self._config.accounts_config_path)
        except Exception:
            accounts = self._config.accounts

        if not accounts:
            await update.effective_message.reply_text(
                "⚠️ No email accounts configured."
            )
            return

        stats = await self._db.get_account_stats()
        stats_map = {s["account_email"]: s["total"] for s in stats}

        lines = ["📋 <b>Monitored Accounts</b>\n"]
        for i, acct in enumerate(accounts, 1):
            safe = html.escape(acct.email)
            count = stats_map.get(acct.email, 0)
            server = html.escape(acct.imap_server)
            lines.append(
                f"  {i}. <code>{safe}</code>\n"
                f"      {server} · {count} emails tracked"
            )

        lines.append(f"\n<b>Total:</b> {len(accounts)} accounts")
        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )

    async def _cmd_history(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not update.effective_message:
            return

        recent = await self._db.get_recent(limit=10)
        if not recent:
            await update.effective_message.reply_text(
                "📭 No emails detected yet."
            )
            return

        lines = ["🕐 <b>Last 10 Detected Emails</b>\n"]
        for entry in recent:
            safe_email = html.escape(entry["account_email"])
            seen_at = entry["seen_at"][:19].replace("T", " ")
            lines.append(f"  📧 <code>{safe_email}</code>\n      {seen_at}")

        await update.effective_message.reply_text(
            "\n".join(lines), parse_mode=ParseMode.HTML
        )

    async def _on_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Reply to any non-command text with a helpful hint."""
        if update.effective_message:
            await update.effective_message.reply_text(
                "💡 Use /help to see available commands."
            )
