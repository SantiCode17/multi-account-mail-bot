"""Telegram bot handlers with universal authentication system.

Authentication is based on username + password credentials.
Any Telegram user, from any device or account, can authenticate
by sending ``/login <user> <password>``.  Sessions are persisted
in SQLite so they survive bot restarts.  Every authenticated user
receives real-time email notifications.
"""

import html
import hmac
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

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
from src.models import AppConfig, SecurityConfig


# ═══════════════════════════════════════════════════════════════════
#  Keyboards
# ═══════════════════════════════════════════════════════════════════

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
        [
            InlineKeyboardButton("🔓 Logout", callback_data="menu_logout"),
        ],
    ]
)

BACK_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("⬅️ Back to menu", callback_data="menu_back")]]
)

AFTER_LOGIN_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("📬 Open Menu", callback_data="menu_back")]]
)


# ═══════════════════════════════════════════════════════════════════
#  Text templates
# ═══════════════════════════════════════════════════════════════════

LOCKED_TEXT = (
    "🔒 <b>Inbox Bridge</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "This is a <b>private</b> email monitoring bot.\n"
    "Access requires valid credentials.\n"
    "\n"
    "To authenticate, send:\n"
    "<code>/login username password</code>\n"
    "\n"
    "⚠️ Failed attempts are logged and rate-limited.\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━"
)

WELCOME_TEXT = (
    "📬 <b>Inbox Bridge</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "I monitor your email accounts <b>24 / 7</b> and notify you\n"
    "instantly whenever a new email arrives.\n"
    "\n"
    "🔹 Notifications are <b>fully automatic</b>.\n"
    "🔹 Your session is <b>persistent</b> — it survives bot restarts.\n"
    "🔹 Access this bot from <b>any device</b> or Telegram account\n"
    "    using the same credentials.\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "Tap a button to get started 👇"
)

HELP_TEXT = (
    "ℹ️ <b>Help — Inbox Bridge</b>\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "\n"
    "<b>What does this bot do?</b>\n"
    "It monitors all configured email accounts and sends\n"
    "Telegram notifications whenever a new email arrives.\n"
    "\n"
    "<b>Menu:</b>\n"
    "  📊 <b>Status</b> — system health &amp; statistics\n"
    "  📋 <b>Accounts</b> — monitored email accounts\n"
    "  🕐 <b>History</b> — last 10 emails detected\n"
    "  🔓 <b>Logout</b> — end your session\n"
    "\n"
    "<b>Commands:</b>\n"
    "  <code>/login user pass</code> — authenticate\n"
    "  <code>/logout</code> — end session\n"
    "  <code>/status</code>  <code>/accounts</code>  <code>/history</code>  <code>/help</code>\n"
    "\n"
    "<b>Security:</b>\n"
    "• Credentials are auto-deleted from chat\n"
    "• Brute-force protection with lockout\n"
    "• Sessions persist across restarts\n"
    "• All authenticated users receive notifications\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━"
)


# ═══════════════════════════════════════════════════════════════════
#  Authentication engine  (brute-force + persistent sessions)
# ═══════════════════════════════════════════════════════════════════

class AuthManager:
    """Universal credential-based authentication with persistent sessions."""

    def __init__(self, security: SecurityConfig, database: Database) -> None:
        self._security = security
        self._db = database
        # Brute-force state (in-memory, resets on restart — that's fine)
        self._failed_attempts: dict[int, list[float]] = defaultdict(list)
        self._lockouts: dict[int, float] = {}

    @property
    def security_enabled(self) -> bool:
        return bool(self._security.username and self._security.password)

    async def is_authorized(self, chat_id: int) -> bool:
        """Check whether a chat_id has an active persistent session."""
        if not self.security_enabled:
            return True  # open mode
        return await self._db.is_session_active(
            chat_id, timeout_hours=self._security.session_timeout_hours,
        )

    def is_locked_out(self, chat_id: int) -> tuple[bool, int]:
        if chat_id not in self._lockouts:
            return False, 0
        remaining = self._lockouts[chat_id] - time.monotonic()
        if remaining <= 0:
            del self._lockouts[chat_id]
            self._failed_attempts.pop(chat_id, None)
            return False, 0
        return True, int(remaining)

    async def attempt_login(
        self,
        chat_id: int,
        username: str,
        password: str,
        telegram_user: str = "",
        first_name: str = "",
    ) -> tuple[bool, str]:
        """Validate credentials. On success, create a persistent session."""

        locked, remaining = self.is_locked_out(chat_id)
        if locked:
            return False, (
                f"🚫 <b>Temporarily locked</b>\n\n"
                f"Too many failed attempts.\n"
                f"Try again in <b>{remaining}s</b>."
            )

        user_ok = hmac.compare_digest(username, self._security.username)
        pass_ok = hmac.compare_digest(password, self._security.password)

        if user_ok and pass_ok:
            await self._db.create_session(chat_id, telegram_user, first_name)
            self._failed_attempts.pop(chat_id, None)
            self._lockouts.pop(chat_id, None)
            logger.info(
                "Auth OK — chat_id={cid} user=@{u} name={n}",
                cid=chat_id, u=telegram_user, n=first_name,
            )
            return True, ""

        # ── Failed ──────────────────────────────────────────────────
        now = time.monotonic()
        window = self._security.lockout_seconds
        self._failed_attempts[chat_id] = [
            t for t in self._failed_attempts[chat_id] if now - t < window
        ]
        self._failed_attempts[chat_id].append(now)

        attempts = len(self._failed_attempts[chat_id])
        mx = self._security.max_login_attempts

        logger.warning(
            "Auth FAIL — chat_id={cid} ({n}/{mx})",
            cid=chat_id, n=attempts, mx=mx,
        )

        if attempts >= mx:
            self._lockouts[chat_id] = now + self._security.lockout_seconds
            return False, (
                f"🚫 <b>Locked out</b>\n\n"
                f"{attempts}/{mx} failed attempts.\n"
                f"Try again in <b>{self._security.lockout_seconds}s</b>."
            )

        left = mx - attempts
        return False, (
            f"❌ <b>Invalid credentials</b>\n\n"
            f"Attempts remaining: <b>{left}/{mx}</b>"
        )

    async def logout(self, chat_id: int) -> bool:
        """Destroy the persistent session."""
        removed = await self._db.delete_session(chat_id)
        if removed:
            logger.info("Logout — chat_id={cid}", cid=chat_id)
        return removed

    async def get_active_chat_ids(self) -> list[int]:
        """Return every chat_id that currently has a valid session."""
        return await self._db.get_all_active_chat_ids(
            timeout_hours=self._security.session_timeout_hours,
        )


# ═══════════════════════════════════════════════════════════════════
#  Bot handlers
# ═══════════════════════════════════════════════════════════════════

class BotHandlers:
    """Interactive Telegram bot with universal authentication."""

    def __init__(self, config: AppConfig, database: Database) -> None:
        self._config = config
        self._db = database
        self._auth = AuthManager(config.security, database)
        self._start_time = time.monotonic()
        self._started_at = datetime.now(timezone.utc)
        self._cycles_completed = 0
        self._total_notifications = 0

    # ── Public API ──────────────────────────────────────────────────

    @property
    def auth(self) -> AuthManager:
        return self._auth

    def increment_cycles(self) -> None:
        self._cycles_completed += 1

    def add_notifications(self, count: int) -> None:
        self._total_notifications += count

    # ── Registration ────────────────────────────────────────────────

    async def setup_commands(self, app: Application) -> None:
        commands = [
            BotCommand("start", "Open main menu"),
            BotCommand("login", "Authenticate (user + password)"),
            BotCommand("logout", "End your session"),
            BotCommand("status", "Monitor status"),
            BotCommand("accounts", "Monitored accounts"),
            BotCommand("history", "Recent emails detected"),
            BotCommand("help", "Help & commands"),
        ]
        try:
            await app.bot.set_my_commands(commands)
            logger.info("Bot command menu set")
        except Exception as exc:
            logger.warning("Could not set bot commands: {err}", err=exc)

    def register(self, app: Application) -> None:
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("login", self._cmd_login))
        app.add_handler(CommandHandler("logout", self._cmd_logout))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("status", self._cmd_status))
        app.add_handler(CommandHandler("accounts", self._cmd_accounts))
        app.add_handler(CommandHandler("history", self._cmd_history))
        app.add_handler(CallbackQueryHandler(self._on_callback, pattern=r"^menu_"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        logger.info("Bot handlers registered")

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _chat_id(update: Update) -> Optional[int]:
        return update.effective_chat.id if update.effective_chat else None

    async def _require_auth(self, update: Update) -> bool:
        cid = self._chat_id(update)
        if cid is None:
            return False
        if await self._auth.is_authorized(cid):
            return True
        if update.effective_message:
            await update.effective_message.reply_text(
                LOCKED_TEXT, parse_mode=ParseMode.HTML,
            )
        return False

    # ── /start ──────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        cid = self._chat_id(update)
        if cid is None:
            return
        if await self._auth.is_authorized(cid):
            if update.effective_message:
                await update.effective_message.reply_text(
                    WELCOME_TEXT, parse_mode=ParseMode.HTML,
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
        else:
            if update.effective_message:
                await update.effective_message.reply_text(
                    LOCKED_TEXT, parse_mode=ParseMode.HTML,
                )

    # ── /login user password ────────────────────────────────────────

    async def _cmd_login(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        cid = self._chat_id(update)
        if cid is None or not update.effective_message:
            return

        if await self._auth.is_authorized(cid):
            await update.effective_message.reply_text(
                "✅ Already authenticated — /start to open the menu.",
                parse_mode=ParseMode.HTML,
            )
            return

        if not ctx.args or len(ctx.args) < 2:
            await update.effective_message.reply_text(
                "🔑 <b>Usage:</b>  <code>/login username password</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        username = ctx.args[0]
        password = " ".join(ctx.args[1:])

        # Delete the message containing credentials
        try:
            await update.effective_message.delete()
        except Exception:
            pass

        tg_user = ""
        first_name = ""
        if update.effective_user:
            tg_user = update.effective_user.username or ""
            first_name = update.effective_user.first_name or ""

        ok, err = await self._auth.attempt_login(
            cid, username, password,
            telegram_user=tg_user, first_name=first_name,
        )

        if ok:
            greeting = f" {first_name}" if first_name else ""
            await ctx.bot.send_message(
                chat_id=cid,
                text=(
                    f"✅ <b>Welcome{greeting}!</b>\n\n"
                    "You are now authenticated.\n"
                    "You will receive email notifications in this chat.\n\n"
                    "Your session is <b>persistent</b> — it will survive\n"
                    "bot restarts. Log in from any device with the same\n"
                    "credentials to receive notifications there too."
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=AFTER_LOGIN_KEYBOARD,
            )
        else:
            await ctx.bot.send_message(
                chat_id=cid,
                text=err,
                parse_mode=ParseMode.HTML,
            )

    # ── /logout ─────────────────────────────────────────────────────

    async def _cmd_logout(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        cid = self._chat_id(update)
        if cid is None or not update.effective_message:
            return

        if await self._auth.logout(cid):
            await update.effective_message.reply_text(
                "🔒 <b>Session ended.</b>\n\n"
                "You will no longer receive notifications.\n"
                "Send <code>/login user pass</code> to re-authenticate.",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.effective_message.reply_text(
                LOCKED_TEXT, parse_mode=ParseMode.HTML,
            )

    # ── Protected commands ──────────────────────────────────────────

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return
        if update.effective_message:
            await update.effective_message.reply_text(
                HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_status(), parse_mode=ParseMode.HTML,
                reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_accounts(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_accounts(), parse_mode=ParseMode.HTML,
                reply_markup=BACK_KEYBOARD,
            )

    async def _cmd_history(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._require_auth(update):
            return
        if update.effective_message:
            await update.effective_message.reply_text(
                await self._build_history(), parse_mode=ParseMode.HTML,
                reply_markup=BACK_KEYBOARD,
            )

    # ── Inline-button callbacks ─────────────────────────────────────

    async def _on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()

        cid = self._chat_id(update)

        # Logout doesn't need prior auth check
        if query.data == "menu_logout":
            if cid:
                await self._auth.logout(cid)
            try:
                await query.edit_message_text(
                    "🔒 <b>Session ended.</b>\n\n"
                    "Send <code>/login user pass</code> to authenticate again.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            return

        # Everything else requires auth
        if cid is None or not await self._auth.is_authorized(cid):
            try:
                await query.edit_message_text(
                    LOCKED_TEXT, parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            return

        handlers = {
            "menu_status": (self._build_status, BACK_KEYBOARD),
            "menu_accounts": (self._build_accounts, BACK_KEYBOARD),
            "menu_history": (self._build_history, BACK_KEYBOARD),
            "menu_help": (None, BACK_KEYBOARD),
            "menu_back": (None, MAIN_MENU_KEYBOARD),
        }

        if query.data not in handlers:
            return

        builder, keyboard = handlers[query.data]

        if query.data == "menu_help":
            text = HELP_TEXT
        elif query.data == "menu_back":
            text = WELCOME_TEXT
        else:
            text = await builder()

        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
        except Exception:
            pass

    # ── Catch-all for non-command text ──────────────────────────────

    async def _on_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        cid = self._chat_id(update)
        if cid is None or not update.effective_message:
            return
        if await self._auth.is_authorized(cid):
            await update.effective_message.reply_text(
                WELCOME_TEXT, parse_mode=ParseMode.HTML,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        else:
            await update.effective_message.reply_text(
                LOCKED_TEXT, parse_mode=ParseMode.HTML,
            )

    # ═══════════════════════════════════════════════════════════════
    #  Text builders
    # ═══════════════════════════════════════════════════════════════

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
        sessions = await self._db.get_session_count()
        started = self._started_at.strftime("%d/%m/%Y %H:%M UTC")

        return (
            "📊 <b>Monitor Status</b>\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            f"  🟢 <b>Online</b> since {started}\n"
            f"  ⏱ Uptime: <b>{uptime}</b>\n"
            "\n"
            f"  📧 Accounts monitored: <b>{n_accounts}</b>\n"
            f"  🔄 Cycles completed: <b>{self._cycles_completed}</b>\n"
            f"  📨 Notifications sent: <b>{self._total_notifications}</b>\n"
            f"  🗄 Emails tracked: <b>{total_tracked}</b>\n"
            f"  ⏰ Check interval: <b>{self._config.monitor.check_interval}s</b>\n"
            "\n"
            f"  🔒 Security: <b>{'Enabled' if self._auth.security_enabled else 'Open'}</b>\n"
            f"  👥 Active sessions: <b>{sessions}</b>\n"
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
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

        lines = [
            "📋 <b>Monitored Accounts</b>\n",
            "━━━━━━━━━━━━━━━━━━━━━━\n",
        ]
        for i, acct in enumerate(accounts, 1):
            safe = html.escape(acct.email)
            count = stats_map.get(acct.email, 0)
            server = html.escape(acct.imap_server)
            lines.append(
                f"  {i}. <code>{safe}</code>\n"
                f"      📡 {server} · 📩 {count}"
            )

        lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<b>Total:</b> {len(accounts)} account(s)")
        return "\n".join(lines)

    async def _build_history(self) -> str:
        recent = await self._db.get_recent(limit=10)
        if not recent:
            return "📭 No emails detected yet."

        lines = [
            "🕐 <b>Recent Emails Detected</b>\n",
            "━━━━━━━━━━━━━━━━━━━━━━\n",
        ]
        for entry in recent:
            safe_email = html.escape(entry["account_email"])
            seen_at = entry["seen_at"][:19].replace("T", " ")
            lines.append(
                f"  📧 <code>{safe_email}</code>\n"
                f"      🕐 {seen_at}"
            )

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
