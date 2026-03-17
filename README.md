# 📬 Inbox Bridge

**Automated multi-email monitoring system with Telegram notifications.**

Monitors **200+ email accounts** simultaneously via IMAP and sends instant Telegram alerts when new messages arrive.

## How It Works

1. The system connects to all configured email accounts via IMAP
2. Every 10 seconds (configurable), it checks each account for new unread emails
3. Gmail accounts with 2FA use **OAuth2** automatically; all others use password login
4. When a new email is found, it sends a formatted Telegram notification instantly
5. A SQLite database prevents duplicate notifications — even across restarts
6. The Telegram bot also responds to interactive commands (`/status`, `/history`, etc.)

## Quick Start (One Command)

```bash
git clone https://github.com/SantiCode17/multi-account-mail-bot.git
cd multi-account-mail-bot
```

Then configure your settings (see [Configuration](#configuration) below) and run:

```bash
./start.sh
```

That's it. The `start.sh` script automatically:
- Detects your Python installation
- Creates a virtual environment
- Installs all dependencies
- Validates your configuration
- Starts the monitor

> **Works on any machine** — Linux, macOS, or WSL. No hardcoded paths.

## Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.10 or higher |
| **Telegram Bot** | Created via [@BotFather](https://t.me/BotFather) |
| **Email accounts** | With IMAP enabled (Gmail, Outlook, custom domains) |

## Configuration

### Step 1 — Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | *(required)* |
| `TELEGRAM_CHAT_ID` | Chat or group ID to receive notifications | *(required)* |
| `CHECK_INTERVAL_SECONDS` | Seconds between monitoring cycles | `10` |
| `MAX_CONCURRENT_CONNECTIONS` | Simultaneous IMAP connections | `20` |
| `BATCH_SIZE` | Accounts processed per batch | `50` |
| `EMAIL_BODY_PREVIEW_LENGTH` | Max characters in body preview | `500` |
| `LOG_LEVEL` | Logging verbosity (DEBUG, INFO, WARNING) | `INFO` |

### Step 2 — Add email accounts

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
    },
    {
      "email": "user@customdomain.com",
      "password": "your_password",
      "imap_server": "mail.customdomain.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

**Provider-specific notes:**

| Provider | IMAP Server | Password |
|---|---|---|
| **Gmail** | `imap.gmail.com` | OAuth2 for 2FA (run `python auth_setup.py`) or regular password |
| **Outlook / Hotmail** | `outlook.office365.com` | Your regular password |
| **Yahoo** | `imap.mail.yahoo.com` | [App Password](https://login.yahoo.com/account/security) |
| **Custom domain** | Ask your hosting provider | Your email password |

### Step 3 — How to get your Telegram Chat ID

**Option A — Private chat:**
1. Send any message to your bot on Telegram
2. Open in browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Look for `"chat":{"id": 123456789}` — that number is your Chat ID

**Option B — Group chat:**
1. Create a Telegram group and add your bot
2. Send a message in the group
3. Open the same URL above
4. Group IDs start with `-` (e.g., `-1001234567890`)

## Running

### Option A — Using start.sh (recommended)

```bash
./start.sh
```

### Option B — Manual

```bash
python3 -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows
pip install -r requirements.txt
python run.py
```

### Option C — Docker

```bash
docker compose up -d
docker compose logs -f
```

## Bot Commands

Once running, the Telegram bot responds to these commands:

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/status` | Uptime, accounts monitored, cycles completed, notifications sent |
| `/accounts` | List all monitored email accounts with per-account stats |
| `/history` | Last 10 detected emails |
| `/help` | Show available commands |

## Notification Format

Each notification looks like this:

```
❗ You've received a new message at user@example.com

From: sender@example.com
Subject: Your application update

Email body preview text here...

📅 12 March 2026, 14:30
```

## Architecture

```
┌──────────────────────────────────────────┐
│              Scheduler                    │
│  Triggers cycles · Controls concurrency  │
└──────────┬───────────────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────────┐
│  Email   │ │ Telegram Bot │
│ Monitor  │ │  (commands)  │
│ (IMAP)   │ │ /status etc  │
└────┬─────┘ └──────────────┘
     │
     ▼
┌──────────┐     ┌──────────┐     ┌──────────────┐
│  Email   │────▶│ Database │────▶│   Telegram   │
│  Parser  │     │ (SQLite) │     │  Notifier    │
└──────────┘     └──────────┘     └──────────────┘
```

## Project Structure

```
inbox-bridge/
├── src/
│   ├── main.py              # Application entry point
│   ├── config.py            # Configuration loader (.env + JSON)
│   ├── models.py            # Data models (dataclasses)
│   ├── email_monitor.py     # IMAP monitoring engine
│   ├── email_parser.py      # Email content extraction
│   ├── telegram_notifier.py # Telegram notification service
│   ├── bot_handlers.py      # Interactive bot commands
│   ├── database.py          # SQLite for deduplication
│   ├── scheduler.py         # Orchestrator
│   ├── oauth_manager.py     # Gmail OAuth2 token management
│   └── utils.py             # Text utilities
├── config/
│   └── accounts.json        # Email accounts list
├── deployment/
│   └── email-monitor.service # Systemd unit file
├── auth_setup.py            # One-time OAuth2 token generator
├── .env.example             # Environment template
├── start.sh                 # One-command launcher
├── run.py                   # Python entry point
├── requirements.txt         # Dependencies
├── Dockerfile               # Docker image
├── docker-compose.yml       # Docker Compose
├── SETUP.md                 # Full setup guide
└── README.md                # This file
```

## Deployment on a Server

### Using systemd (Linux VPS)

```bash
sudo cp deployment/email-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-monitor
sudo systemctl start email-monitor
sudo journalctl -u email-monitor -f
```

### Using Docker

```bash
docker compose up -d
```

## Adding New Email Accounts

1. Edit `config/accounts.json` and add the new entry
2. The system reloads the file automatically on the next cycle
3. **No restart required**

## Troubleshooting

| Problem | Solution |
|---|---|
| `PermissionError` on logs | Delete `logs/` and `data/` folders, let the app recreate them |
| `Authentication failed` | Gmail 2FA → run `python auth_setup.py`. Others → check password. |
| `Connection timeout` | Verify IMAP server and port. Check your firewall. |
| `Telegram not sending` | Verify bot token and chat ID. Make sure the bot is in the chat. |
| `No new emails` | Emails must be UNSEEN on the server. Already-read emails are skipped. |
| `ModuleNotFoundError` | Activate the venv: `source venv/bin/activate` then `pip install -r requirements.txt` |
| Bot not responding to commands | Make sure only one instance is running. Stop duplicates. |

## Logs

- **Console**: Colored output at INFO level
- **File**: `logs/email_monitor.log` — DEBUG level, rotated at 10 MB, retained 7 days

## License

Internal tool — Private use only.
