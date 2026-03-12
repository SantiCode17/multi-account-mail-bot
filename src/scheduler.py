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

    async def _check_account(self, account: EmailAccount) -> list[EmailMessage]:
        """Check a single account, guarded by the concurrency semaphore."""
        async with self._semaphore:
            try:
                return await self._monitor.fetch_new_emails(account)
            except Exception as exc:
                logger.error(
                    "Unhandled error checking {email}: {err}",
                    email=account.email,
                    err=exc,
                )
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
            tasks = [
                asyncio.create_task(self._check_account(acct))
                for acct in batch
            ]
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
                "Cycle complete: {accts} accounts | {new} new emails | "
                "{sent} notifications sent | {errs} errors",
                accts=total_accounts,
                new=len(all_new),
                sent=sent,
                errs=errors,
            )
        else:
            logger.info(
                "Cycle complete: {accts} accounts checked | no new emails | "
                "{errs} errors",
                accts=total_accounts,
                errs=errors,
            )

    async def _maybe_cleanup(self) -> None:
        """Run DB cleanup once every CLEANUP_INTERVAL_HOURS."""
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

    async def run(self) -> None:
        """Main entry point: initialize resources then loop forever."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_signal)
            except NotImplementedError:
                pass

        await self._db.initialize()

        bot_ok = await self._notifier.validate()
        if not bot_ok:
            logger.error("Telegram bot validation failed — exiting")
            await self._db.close()
            return

        app = Application.builder().token(self._config.telegram.bot_token).build()
        self._bot_handlers.register(app)

        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot polling started")

        account_count = len(self._config.accounts)
        await self._notifier.send_raw(
            f"✅ <b>Inbox Bridge started</b>\n"
            f"Monitoring <b>{account_count}</b> accounts every "
            f"<b>{self._config.monitor.check_interval}s</b>\n\n"
            f"Send /help to see available commands."
        )

        logger.info(
            "Monitor running — {n} accounts, interval {s}s, "
            "concurrency {c}",
            n=account_count,
            s=self._config.monitor.check_interval,
            c=self._config.monitor.max_concurrent,
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
            await self._notifier.send_raw("⛔ <b>Inbox Bridge stopped</b>")
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
            await self._db.close()
