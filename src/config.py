import json
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.models import (
    AppConfig,
    EmailAccount,
    MonitorConfig,
    SecurityConfig,
    TelegramConfig,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(relative: str) -> str:
    """Resolve a path relative to the project root directory."""
    p = Path(relative)
    if p.is_absolute():
        return str(p)
    return str(PROJECT_ROOT / p)


def _require_env(name: str) -> str:
    """Return an environment variable or raise with a clear message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _env_int(name: str, default: int) -> int:
    """Return an environment variable as int, or the default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "Invalid integer for {name}, using default {default}",
            name=name,
            default=default,
        )
        return default


def load_accounts(path: str) -> list[EmailAccount]:
    """Load and validate email accounts from a JSON configuration file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Accounts config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    raw_accounts = data.get("accounts", [])
    if not isinstance(raw_accounts, list):
        raise ValueError("'accounts' key must be a list in the config file")

    required_fields = {"email", "password", "imap_server", "imap_port"}
    accounts: list[EmailAccount] = []

    for idx, entry in enumerate(raw_accounts):
        missing = required_fields - set(entry.keys())
        if missing:
            raise ValueError(
                f"Account at index {idx} is missing fields: {missing}"
            )
        accounts.append(
            EmailAccount(
                email=str(entry["email"]).strip(),
                password=str(entry["password"]).strip(),
                imap_server=str(entry["imap_server"]).strip(),
                imap_port=int(entry["imap_port"]),
                use_ssl=bool(entry.get("use_ssl", True)),
            )
        )

    return accounts


def load_config() -> AppConfig:
    """Load the full application configuration from .env and accounts.json."""
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path)

    bot_token = _require_env("TELEGRAM_BOT_TOKEN")
    chat_id = _require_env("TELEGRAM_CHAT_ID")

    check_interval = _env_int("CHECK_INTERVAL_SECONDS", 60)
    max_concurrent = _env_int("MAX_CONCURRENT_CONNECTIONS", 20)
    batch_size = _env_int("BATCH_SIZE", 50)
    preview_length = _env_int("EMAIL_BODY_PREVIEW_LENGTH", 500)

    database_path = _resolve_path(
        os.getenv("DATABASE_PATH", "data/seen_emails.db").strip()
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").strip()
    log_file_path = _resolve_path(
        os.getenv("LOG_FILE_PATH", "logs/email_monitor.log").strip()
    )
    accounts_config_path = _resolve_path(
        os.getenv("ACCOUNTS_CONFIG_PATH", "config/accounts.json").strip()
    )

    accounts = load_accounts(accounts_config_path)

    # ── Security ────────────────────────────────────────────────────
    bot_username = os.getenv("BOT_USERNAME", "").strip()
    bot_password = os.getenv("BOT_PASSWORD", "").strip()
    if not bot_username or not bot_password:
        logger.warning(
            "BOT_USERNAME / BOT_PASSWORD not set — the bot will be OPEN to everyone!"
        )

    max_login_attempts = _env_int("MAX_LOGIN_ATTEMPTS", 5)
    lockout_seconds = _env_int("LOCKOUT_SECONDS", 300)
    session_timeout = _env_int("SESSION_TIMEOUT_HOURS", 0)

    security = SecurityConfig(
        username=bot_username,
        password=bot_password,
        max_login_attempts=max_login_attempts,
        lockout_seconds=lockout_seconds,
        session_timeout_hours=session_timeout,
    )

    return AppConfig(
        monitor=MonitorConfig(
            check_interval=check_interval,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
            preview_length=preview_length,
        ),
        telegram=TelegramConfig(bot_token=bot_token, chat_id=chat_id),
        security=security,
        accounts=accounts,
        database_path=database_path,
        log_level=log_level,
        log_file_path=log_file_path,
        accounts_config_path=accounts_config_path,
    )
