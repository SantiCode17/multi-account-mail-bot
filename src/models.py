from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmailAccount:
    """Represents a single email account to monitor."""
    email: str
    password: str
    imap_server: str
    imap_port: int = 993
    use_ssl: bool = True


@dataclass(frozen=True)
class EmailMessage:
    """Represents a parsed email message ready for notification."""
    message_id: str
    account_email: str
    sender: str
    subject: str
    date: str
    body_preview: str


@dataclass(frozen=True)
class MonitorConfig:
    """Runtime configuration for the monitoring engine."""
    check_interval: int = 60
    max_concurrent: int = 20
    batch_size: int = 50
    preview_length: int = 500


@dataclass(frozen=True)
class TelegramConfig:
    """Configuration for the Telegram notification service."""
    bot_token: str
    chat_id: str


@dataclass(frozen=True)
class SecurityConfig:
    """Bot access-control configuration."""
    username: str
    password: str
    max_login_attempts: int = 5
    lockout_seconds: int = 300  # 5 minutes
    session_timeout_hours: int = 0  # 0 = never expire


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration container."""
    monitor: MonitorConfig
    telegram: TelegramConfig
    security: SecurityConfig = field(default_factory=lambda: SecurityConfig(username="", password=""))
    accounts: list[EmailAccount] = field(default_factory=list)
    database_path: str = "data/seen_emails.db"
    log_level: str = "INFO"
    log_file_path: str = "logs/email_monitor.log"
    accounts_config_path: str = "config/accounts.json"
