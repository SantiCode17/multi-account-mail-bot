import asyncio
import signal
import time

from loguru import logger
from telegram.ext import Application

from src.bot_handlers import BotHandlers
from src.config import load_accounts
from src.database import Database
from src.email_monitor import EmailMonitor
from src.models import AppConfig, EmailAccount, EmailMessage
from src.telegram_notifier import TelegramNotifier

CLEANUP_INTERVAL_HOURS = 24


class MonitorScheduler:
    """Orchestrates periodic monitoring of all email accounts."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._db = Database(config.database_path)
        self._monitor = EmailMonitor(
            database=self._db,
            preview_length=config.monitor.preview_length,
        )
        self._notifier = TelegramNotifier(config.telegram)
        self._semaphore = asyncio.Semaphore(config.monitor.max_concurrent)
        self._running = True
        self._last_cleanup = time.monotonic()
        self._bot_handlers = BotHandlers(config, self._db)

    # ── Account checking ────────────────────────────────────────────

    async def _check_account(self, account: EmailAccount) -> list[EmailMessage]:
        """Check a single account, guarded by the concurrency semaphore."""
        async with self._semaphore:
            try:
                return await self._monitor.fetch_new_emails(account)
            except Exception as exc:
                logger.error("Unhandled error checking {email}: {err}", email=account.email, err=exc)
                return []

    async def _run_cycle(self) -> None:
        """Execute one full monitoring cycle over all accounts."""
        try:
            accounts = load_accounts(self._config.accounts_config_path)
        except Exception as exc:
            logger.error("Failed to reload accounts config: {err}", err=exc)
            accounts = self._config.accounts

        total_accounts = len(accounts)
        if total_accounts == 0:
            logger.warning("No email accounts configured — skipping cycle")
            return

        batch_size = self._config.monitor.batch_size
        all_new: list[EmailMessage] = []
        errors = 0

        for batch_start in range(0, total_accounts, batch_size):
            batch = accounts[batch_start : batch_start + batch_size]
            tasks = [asyncio.create_task(self._check_account(acct)) for acct in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    errors += 1
                elif isinstance(result, list):
                    all_new.extend(result)

            if batch_start + batch_size < total_accounts:
                await asyncio.sleep(0.5)

        if all_new:
            sent = await self._notifier.send_notifications(all_new)
            self._bot_handlers.add_notifications(sent)
            logger.info(
                "Cycle complete: {accts} accounts | {new} new | {sent} sent | {errs} errors",
                accts=total_accounts, new=len(all_new), sent=sent, errs=errors,
            )
        else:
            logger.info(
                "Cycle complete: {accts} accounts | no new emails | {errs} errors",
                accts=total_accounts, errs=errors,
            )

    # ── Seed (first run) ────────────────────────────────────────────

    async def _seed_accounts(self) -> None:
        """First-run: fetch real Message-ID headers of all current UNSEEN
        emails and mark them as seen so the first real cycle doesn't flood
        Telegram with old notifications."""
        try:
            accounts = load_accounts(self._config.accounts_config_path)
        except Exception:
            accounts = self._config.accounts

        if not accounts:
            return

        total = await self._db.get_total_count()
        if total > 0:
            logger.info("Database already seeded ({n} records) — skipping seed", n=total)
            return

        logger.info("First run detected — seeding {n} account(s) with real Message-IDs", n=len(accounts))

        total_seeded = 0
        for acct in accounts:
            try:
                count = await self._monitor.seed_existing_emails(acct)
                if count:
                    logger.info("Seeded {count} real Message-IDs for {email}", count=count, email=acct.email)
                    total_seeded += count
                else:
                    logger.info("No UNSEEN emails to seed for {email}", email=acct.email)
            except Exception as exc:
                logger.warning("Seed failed for {email}: {err}", email=acct.email, err=exc)

        logger.info("Seed complete — {n} real Message-IDs recorded", n=total_seeded)

    # ── Cleanup ─────────────────────────────────────────────────────

    async def _maybe_cleanup(self) -> None:
        elapsed = time.monotonic() - self._last_cleanup
        if elapsed >= CLEANUP_INTERVAL_HOURS * 3600:
            try:
                await self._db.cleanup_old(days=30)
            except Exception as exc:
                logger.error("Database cleanup failed: {err}", err=exc)
            self._last_cleanup = time.monotonic()

    def _handle_signal(self) -> None:
        logger.info("Shutdown signal received — stopping gracefully")
        self._running = False

    # ── Main entry point ────────────────────────────────────────────

    async def run(self) -> None:
        """Initialize resources, seed DB, start bot, then loop forever."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_signal)
            except NotImplementedError:
                pass

        await self._db.initialize()
        await self._seed_accounts()

        # Validate Telegram bot
        bot_ok = await self._notifier.validate()
        if not bot_ok:
            logger.error("Telegram bot validation failed — exiting")
            await self._db.close()
            return

        # Force-clear any stale webhook before starting polling
        try:
            import telegram as tg
            temp_bot = tg.Bot(token=self._config.telegram.bot_token)
            await temp_bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass

        # Build the bot application
        app = Application.builder().token(self._config.telegram.bot_token).build()
        self._bot_handlers.register(app)

        await app.initialize()
        await self._bot_handlers.setup_commands(app)
        await app.start()

        # Start polling with conflict handling
        try:
            await app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram bot polling started")
        except Exception as exc:
            logger.warning("Bot polling conflict (another instance?): {err}", err=exc)
            logger.warning("Bot commands will NOT work until the other instance is stopped")

        # Send startup notification
        account_count = len(self._config.accounts)
        await self._notifier.send_raw(
            f"✅ <b>Inbox Bridge is now online</b>\n\n"
            f"📧 Monitoring <b>{account_count}</b> account(s)\n"
            f"⏰ Check interval: <b>{self._config.monitor.check_interval}s</b>\n\n"
            f"Tap /start to open the menu."
        )

        logger.info(
            "Monitor running — {n} accounts, interval {s}s, concurrency {c}",
            n=account_count, s=self._config.monitor.check_interval, c=self._config.monitor.max_concurrent,
        )

        try:
            while self._running:
                cycle_start = time.monotonic()
                await self._run_cycle()
                self._bot_handlers.increment_cycles()
                await self._maybe_cleanup()

                elapsed = time.monotonic() - cycle_start
                wait = max(0, self._config.monitor.check_interval - elapsed)
                if wait > 0 and self._running:
                    await asyncio.sleep(wait)
        finally:
            logger.info("Shutting down — closing resources")
            try:
                await self._notifier.send_raw("⛔ <b>Inbox Bridge stopped</b>")
            except Exception:
                pass
            try:
                if app.updater and app.updater.running:
                    await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception:
                pass
            await self._db.close()
