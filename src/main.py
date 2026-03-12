import os
import sys
from pathlib import Path

from loguru import logger

from src.config import load_config
from src.scheduler import MonitorScheduler

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _mask_token(token: str) -> str:
    """Show only the first 5 and last 4 characters of a token."""
    if len(token) <= 12:
        return "***"
    return token[:5] + "..." + token[-4:]


def _resolve_path(relative: str) -> str:
    """Resolve a path relative to the project root directory."""
    p = Path(relative)
    if p.is_absolute():
        return str(p)
    return str(PROJECT_ROOT / p)


def setup_logging(log_level: str, log_file_path: str) -> None:
    """Configure loguru with console and file sinks."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    resolved_log = _resolve_path(log_file_path)
    os.makedirs(os.path.dirname(resolved_log) or ".", exist_ok=True)
    logger.add(
        resolved_log,
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{module}:{function}:{line} | {message}"
        ),
        rotation="10 MB",
        retention="7 days",
        encoding="utf-8",
    )


async def main() -> None:
    """Application entry point."""
    setup_logging("INFO", "logs/email_monitor.log")

    try:
        config = load_config()
    except Exception as exc:
        logger.error("Configuration error: {err}", err=exc)
        sys.exit(1)

    setup_logging(config.log_level, config.log_file_path)

    logger.info(
        "Starting Inbox Bridge — {n} accounts | token {t}",
        n=len(config.accounts),
        t=_mask_token(config.telegram.bot_token),
    )

    scheduler = MonitorScheduler(config)
    await scheduler.run()
