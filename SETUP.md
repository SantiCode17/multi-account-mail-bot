# 📬 Inbox Bridge — Setup Guide

> Complete guide to get the project running from a fresh download.

---

## 1. Create a Telegram Bot

1. Open **[@BotFather](https://t.me/BotFather)** in Telegram
2. Send `/newbot`
3. Choose a display name (anything you want)
4. Choose a username — **must end in `bot`** (e.g. `my_mail_alerts_bot`)
5. BotFather replies with a **token** like `8641449158:AAH-gzI76KzUqFZbF9P-...`
6. **Copy and save the token** — you'll need it in step 3
7. **Open your new bot** in Telegram and press **Start** (this is required)

## 2. Get Your Chat ID

1. Open **[@userinfobot](https://t.me/userinfobot)** in Telegram
2. Send `/start`
3. Copy the number next to **Id** (e.g. `1792370231`)

## 3. Create the `.env` File

The `.env` file is **not included** in the download — you must create it.

In the **project root folder**, create a file named `.env` and paste this content:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Monitoring Configuration
CHECK_INTERVAL_SECONDS=10
MAX_CONCURRENT_CONNECTIONS=20
BATCH_SIZE=50
EMAIL_BODY_PREVIEW_LENGTH=500

# Database
DATABASE_PATH=data/seen_emails.db

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=logs/email_monitor.log

# Accounts Configuration
ACCOUNTS_CONFIG_PATH=config/accounts.json
```

Replace the two placeholder values:

| Variable | Replace with |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | The token from BotFather (step 1) |
| `TELEGRAM_CHAT_ID` | Your numeric Chat ID (step 2) |

> All other values can be left as-is.

## 4. Configure Email Accounts

Edit `config/accounts.json`. The system automatically handles authentication:

- **Gmail without 2FA**: Uses your password directly
- **Gmail with 2FA**: Uses OAuth2 tokens (see section 4.1)
- **Outlook/Hotmail**: Uses your password directly
- **Other providers**: Uses your password directly

### 4.1 Gmail OAuth2 Setup (For 2FA Accounts)

If your Gmail accounts have **2FA enabled**, the system uses **OAuth2** automatically — no app passwords or account changes needed.

#### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Name it (e.g. `inbox-bridge`) → **Create**

#### Step 2: Enable the Gmail API

1. Go to **APIs & Services** → **Library**
2. Search for **Gmail API** → Click **Enable**

#### Step 3: Configure the OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** → **Create**
3. Fill in the app name (e.g. `inbox-bridge`) and your email
4. Click through the rest (no scopes needed here) → **Save**
5. Under **Test users**, add every Gmail address you want to monitor

#### Step 4: Create OAuth2 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth 2.0 Client ID**
3. Application type: **Desktop app**
4. Name it anything → **Create**
5. Copy the **Client ID** and **Client Secret**

#### Step 5: Add Credentials to `.env`

```env
GMAIL_CLIENT_ID=your_client_id_here
GMAIL_CLIENT_SECRET=your_client_secret_here
```

#### Step 6: Generate Tokens

Run once to authorise all Gmail accounts (a browser opens for each):

```bash
source venv/bin/activate
python auth_setup.py
```

Tokens are saved in `config/credentials/` and refresh automatically.

### 4.2 Account Configuration

Edit `config/accounts.json`:

```json
{
  "accounts": [
    {
      "email": "your_email@gmail.com",
      "password": "your_password_or_app_password",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

For Gmail:
- If **2FA is disabled**: Use your regular password
- If **2FA is enabled**: Run `python auth_setup.py` (password is ignored, OAuth2 is used)

For Outlook/Hotmail/Yahoo: Use your regular password directly

### Multi-Account Example

```json
{
  "accounts": [
    {
      "email": "my_email@gmail.com",
      "password": "abcd efgh ijkl mnop",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    },
    {
      "email": "my_email@hotmail.com",
      "password": "xxxx yyyy zzzz wwww",
      "imap_server": "outlook.office365.com",
      "imap_port": 993,
      "use_ssl": true
    },
    {
      "email": "my_email@yahoo.com",
      "password": "aaaa bbbb cccc dddd",
      "imap_server": "imap.mail.yahoo.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

> ⚠️ The last account must **NOT** have a comma after its closing `}`

---

## 5. Provider Settings

### Gmail (`@gmail.com`)

| Field | Value |
|-------|-------|
| Server | `imap.gmail.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> Requires 2-Step Verification enabled first

### Outlook / Hotmail / Live (`@outlook.com`, `@hotmail.com`, `@live.com`)

| Field | Value |
|-------|-------|
| Server | `outlook.office365.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [account.live.com/proofs/AppPassword](https://account.live.com/proofs/AppPassword)

### Yahoo (`@yahoo.com`, `@yahoo.es`)

| Field | Value |
|-------|-------|
| Server | `imap.mail.yahoo.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [login.yahoo.com/account/security](https://login.yahoo.com/account/security) → Generate app password

### iCloud (`@icloud.com`, `@me.com`, `@mac.com`)

| Field | Value |
|-------|-------|
| Server | `imap.mail.me.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [appleid.apple.com](https://appleid.apple.com/account/manage) → App-Specific Passwords

### Zoho (`@zoho.com`)

| Field | Value |
|-------|-------|
| Server | `imap.zoho.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [accounts.zoho.com/home#security/app_password](https://accounts.zoho.com/home#security/app_password)

### ProtonMail (`@proton.me`, `@protonmail.com`)

| Field | Value |
|-------|-------|
| Server | `127.0.0.1` |
| Port | `1143` |
| SSL | `false` |

> Requires [Proton Mail Bridge](https://proton.me/mail/bridge) installed and running

### GMX (`@gmx.com`, `@gmx.es`)

| Field | Value |
|-------|-------|
| Server | `imap.gmx.com` |
| Port | `993` |
| SSL | `true` |

> Uses your regular password. Enable IMAP in: Settings → POP3 & IMAP

### AOL (`@aol.com`)

| Field | Value |
|-------|-------|
| Server | `imap.aol.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [login.aol.com/account/security](https://login.aol.com/account/security) → Generate app password

### Yandex (`@yandex.com`, `@ya.ru`)

| Field | Value |
|-------|-------|
| Server | `imap.yandex.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [id.yandex.com/security/app-passwords](https://id.yandex.com/security/app-passwords)

### FastMail (`@fastmail.com`)

| Field | Value |
|-------|-------|
| Server | `imap.fastmail.com` |
| Port | `993` |
| SSL | `true` |

**App password:** [fastmail.com/settings/security/devicekeys](https://www.fastmail.com/settings/security/devicekeys)

### Mail.com (`@mail.com`, `@email.com`)

| Field | Value |
|-------|-------|
| Server | `imap.mail.com` |
| Port | `993` |
| SSL | `true` |

> Uses your regular password. Enable IMAP in: Settings → POP3 & IMAP

---

# Run

```bash
# First time (install dependencies)
chmod +x start.sh
./start.sh

# Or manually
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py

# Run in background (survives terminal close)
nohup python3 run.py > /dev/null 2>&1 &

# With Docker
docker compose up -d
```

## 7. Auto-Start as a System Service (Linux only)

To run the bot **automatically at startup** and **keep it running forever** (restarts if it crashes):

### Setup (one-time)

```bash
chmod +x deployment/install-service.sh
sudo deployment/install-service.sh
```

This script will:
- ✔ Verify all configuration is correct
- ✔ Create a systemd service file
- ✔ Enable it to start on boot
- ✔ Start it immediately

### Service Commands

```bash
# Check status
systemctl status inbox-bridge-${USER}.service

# View live logs
journalctl -u inbox-bridge-${USER}.service -f

# Stop the service
systemctl stop inbox-bridge-${USER}.service

# Start the service
systemctl start inbox-bridge-${USER}.service

# Restart the service
systemctl restart inbox-bridge-${USER}.service

# Uninstall the service
sudo systemctl disable inbox-bridge-${USER}.service
sudo rm /etc/systemd/system/inbox-bridge-${USER}.service
sudo systemctl daemon-reload
```

---

## 8. Useful Commands

```bash
# Check if running
ps aux | grep run.py

# View logs
tail -f logs/email_monitor.log

# Stop the process
kill $(pgrep -f "python3 run.py")

# Reset (delete database)
rm -f data/seen_emails.db

# Docker: view logs / stop
docker compose logs -f
docker compose down
```
