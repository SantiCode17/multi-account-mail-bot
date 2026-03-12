import os
import sys

from loguru import logger

from src.config import load_config
from src.scheduler import MonitorScheduler


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

    os.makedirs(os.path.dirname(log_file_path) or ".", exist_ok=True)
    logger.add(
        log_file_path,
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
    try:
        config = load_config()
    except Exception as exc:
        logger.error("Configuration error: {err}", err=exc)
        sys.exit(1)

    setup_logging(config.log_level, config.log_file_path)

    logger.info(
        "Starting Inbox Bridge — {n} accounts configured",
        n=len(config.accounts),
    )

    scheduler = MonitorScheduler(config)
    await scheduler.run()
