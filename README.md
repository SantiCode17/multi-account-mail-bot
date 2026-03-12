# UNICEDU Inbox Bridge

Automated multi-email monitoring system with Telegram notifications for **UNICEDU (Poland Study)**.

Monitors **200+ email accounts** via IMAP and sends instant Telegram notifications when new emails arrive.

## Architecture

```
┌─────────────────┐
│   Scheduler      │  Triggers monitoring cycles every N seconds
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Email Monitor   │  Connects to IMAP servers (async, concurrent)
│  (imaplib +      │  Fetches UNSEEN messages
│   asyncio)       │  Deduplicates via SQLite database
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Email Parser    │  Extracts sender, subject, date, body preview
│  (email + bs4)   │  Handles MIME, HTML, encoding edge cases
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Notifier│  Formats and sends notifications
│ (python-telegram │  Rate-limited with retry logic
│  -bot)           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Chat    │  Receives formatted alerts
└─────────────────┘
```

## Prerequisites

- **Python 3.11+**
- A **Telegram Bot** (created via @BotFather)
- Email accounts with **IMAP enabled**
- For Gmail: App Passwords (if 2FA is on)

## Installation

```bash
git clone https://github.com/SantiCode17/multi-account-mail-bot.git
cd multi-account-mail-bot

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Configuration

### 1. Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Target chat/group ID |
| `CHECK_INTERVAL_SECONDS` | Seconds between monitoring cycles (default: 60) |
| `MAX_CONCURRENT_CONNECTIONS` | Max simultaneous IMAP connections (default: 20) |
| `BATCH_SIZE` | Accounts per batch (default: 50) |
| `EMAIL_BODY_PREVIEW_LENGTH` | Max body preview chars (default: 500) |

### 2. Email Accounts

Edit `config/accounts.json`:

```json
{
  "accounts": [
    {
      "email": "user@gmail.com",
      "password": "abcd efgh ijkl mnop",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    },
    {
      "email": "user@outlook.com",
      "password": "your_password",
      "imap_server": "outlook.office365.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

## Running

```bash
python run.py
```

The system will:
1. Validate the Telegram bot connection
2. Send a startup notification to your chat
3. Begin monitoring all accounts on the configured interval
4. Send Telegram notifications for every new email detected

Press `Ctrl+C` to stop gracefully.

## Deployment as a System Service (Linux)

```bash
sudo cp deployment/email-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-monitor
sudo systemctl start email-monitor
sudo journalctl -u email-monitor -f
```

## Deployment with Docker

```bash
docker compose up -d
docker compose logs -f
```

## Adding New Email Accounts

1. Edit `config/accounts.json` and add the new account entry
2. The system will pick up changes on the next monitoring cycle (hot-reload)
3. No restart required

## Troubleshooting

| Issue | Solution |
|---|---|
| `Authentication failed` | Check password / App Password. For Gmail, enable IMAP and use an App Password. |
| `Connection timeout` | Verify IMAP server address and port. Check firewall. |
| `Telegram not sending` | Verify bot token and chat ID. Ensure bot is added to the chat. |
| `No new emails detected` | Check that emails are marked as UNSEEN on the server. |
| `Import errors` | Ensure you activated the venv and ran `pip install -r requirements.txt`. |

## Logs

Logs are written to:
- **Console**: INFO level with colors
- **File**: `logs/email_monitor.log` — DEBUG level, rotated at 10 MB, retained 7 days

## License

Internal tool — UNICEDU (Poland Study).
