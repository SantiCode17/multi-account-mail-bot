import html
import time
from datetime import datetime, timezone

from loguru import logger
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import load_accounts
from src.database import Database
from src.models import AppConfig


# ── Inline Keyboard Layouts ─────────────────────────────────────────

MAIN_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            InlineKeyboardButton("📋 Accounts", callback_data="menu_accounts"),
        ],
        [
            InlineKeyboardButton("🕐 History", callback_data="menu_history"),
            InlineKeyboardButton("ℹ️ Help", callback_data="menu_help"),
        ],
    ]
)

BACK_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("⬅️ Back to menu", callback_data="menu_back")]]
)


# ── Text Templates ──────────────────────────────────────────────────

WELCOME_TEXT = (
    "📬 <b>Welcome to Inbox Bridge</b>\n"
    "\n"
    "I monitor your <b>email accounts 24/7</b> and notify you "
    "instantly right here on Telegram whenever a new email arrives.\n"
    "\n"
    "🔹 Notifications are <b>fully automatic</b> — you don't need "
    "to do anything.\n"
    "🔹 Use the <b>menu below</b> to check the system status, view "
    "monitored accounts, or browse recent activity.\n"
    "\n"
    "Tap a button below to get started 👇"
)

HELP_TEXT = (
    "ℹ️ <b>Help — Inbox Bridge</b>\n"
    "\n"
    "<b>What does this bot do?</b>\n"
    "It monitors all your configured email accounts and sends you "
    "an instant Telegram notification whenever a new email arrives.\n"
    "\n"
    "<b>Menu options:</b>\n"
    "\n"
    "  📊 <b>Status</b> — Shows whether the system is running, "
    "uptime, accounts monitored, and notifications sent.\n"
    "\n"
    "  📋 <b>Accounts</b> — Lists all email accounts being "
    "monitored with per-account statistics.\n"
    "\n"
    "  🕐 <b>History</b> — Shows the last 10 emails detected "
    "by the system.\n"
    "\n"
    "  ℹ️ <b>Help</b> — This message.\n"
    "\n"
    "Notifications arrive <b>automatically</b> — you don't need "
    "to do anything to receive them."
)


class BotHandlers:
    """Interactive Telegram bot with inline button menus."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self._config = config
        self._db = database
        self._start_time = time.monotonic()
        self._started_at = datetime.now(timezone.utc)
        self._cycles_completed = 0
        self._total_notifications = 0

    # ── Public counters ─────────────────────────────────────────────

    def increment_cycles(self) -> None:
        self._cycles_completed += 1

    def add_notifications(self, count: int) -> None:
        self._total_notifications += count

    # ── Setup ───────────────────────────────────────────────────────

    async def setup_commands(self, app: Application) -> None:
        """Register the bot's slash-command menu visible in Telegram UI."""
        commands = [
            BotCommand("start", "Open main menu"),
            BotCommand("status", "Monitor status"),
            BotCommand("accounts", "Monitored accounts"),
            BotCommand("history", "Recent emails detected"),
            BotCommand("help", "Help"),
        ]
        try:
            await app.bot.set_my_commands(commands)
            logger.info("Bot command menu set")
        except Exception as exc:
            logger.warning("Could not set bot commands: {err}", err=exc)

    def register(self, app: Application) -> None:
        """Attach all handlers to the Application."""
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("accounts", self._cmd_accounts))
        app.add_handler(CommandHandler("history", self._cmd_history))
        app.add_handler(CallbackQueryHandler(self._on_callback, pattern=r"^menu_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        logger.info("Bot handlers registered")

    # ── Slash commands ──────────────────────────────────────────────

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=MAIN_MENU_KEYBOARD,
            )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_status(), parse_mode=ParseMode.HTML, reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_accounts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_accounts(), parse_mode=ParseMode.HTML, reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_history(), parse_mode=ParseMode.HTML, reply_markup=BACK_KEYBOARD,
            )

    # ── Inline button callbacks ─────────────────────────────────────

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()

        action = query.data
        handlers = {
            "menu_status": (self._build_status, BACK_KEYBOARD),
            "menu_accounts": (self._build_accounts, BACK_KEYBOARD),
            "menu_history": (self._build_history, BACK_KEYBOARD),
            "menu_help": (None, BACK_KEYBOARD),
            "menu_back": (None, MAIN_MENU_KEYBOARD),
        }

        if action not in handlers:
            return

        builder, keyboard = handlers[action]

        if action == "menu_help":
            text = HELP_TEXT
        elif action == "menu_back":
            text = WELCOME_TEXT
        else:
            text = await builder()

        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception:
            # Message unchanged — ignore
            pass

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reply to any non-command text with the welcome menu."""
        if update.effective_message:
            await update.effective_message.reply_text(
                WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=MAIN_MENU_KEYBOARD,
            )

    # ── Text builders ───────────────────────────────────────────────

    async def _build_status(self) -> str:
        uptime_s = int(time.monotonic() - self._start_time)
        h, remainder = divmod(uptime_s, 3600)
        m, s = divmod(remainder, 60)
        uptime = f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

        try:
            n_accounts = len(load_accounts(self._config.accounts_config_path))
        except Exception:
            n_accounts = len(self._config.accounts)

        total_tracked = await self._db.get_total_count()
        started = self._started_at.strftime("%d/%m/%Y %H:%M UTC")

        return (
            "📊 <b>Monitor Status</b>\n"
            "\n"
            f"  🟢 <b>Online</b> since {started}\n"
            f"  ⏱ Uptime: <b>{uptime}</b>\n"
            "\n"
            f"  📧 Accounts monitored: <b>{n_accounts}</b>\n"
            f"  🔄 Cycles completed: <b>{self._cycles_completed}</b>\n"
            f"  📨 Notifications sent: <b>{self._total_notifications}</b>\n"
            f"  🗄 Emails tracked: <b>{total_tracked}</b>\n"
            f"  ⏰ Check interval: <b>{self._config.monitor.check_interval}s</b>"
        )

    async def _build_accounts(self) -> str:
        try:
            accounts = load_accounts(self._config.accounts_config_path)
        except Exception:
            accounts = self._config.accounts

        if not accounts:
            return "⚠️ No email accounts configured."

        stats = await self._db.get_account_stats()
        stats_map = {s["account_email"]: s["total"] for s in stats}

        lines = ["📋 <b>Monitored Accounts</b>\n"]
        for i, acct in enumerate(accounts, 1):
            safe = html.escape(acct.email)
            count = stats_map.get(acct.email, 0)
            server = html.escape(acct.imap_server)
            lines.append(f"  {i}. <code>{safe}</code>\n      📡 {server} · 📩 {count} emails")

        lines.append(f"\n<b>Total:</b> {len(accounts)} account(s)")
        return "\n".join(lines)

    async def _build_history(self) -> str:
        recent = await self._db.get_recent(limit=10)
        if not recent:
            return "📭 No emails detected yet."

        lines = ["🕐 <b>Recent Emails Detected</b>\n"]
        for entry in recent:
            safe_email = html.escape(entry["account_email"])
            seen_at = entry["seen_at"][:19].replace("T", " ")
            lines.append(f"  📧 <code>{safe_email}</code>\n      🕐 {seen_at}")

        return "\n".join(lines)
