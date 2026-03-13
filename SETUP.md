# 📬 Inbox Bridge — Setup Guide

---

## 1. Create a Telegram Bot

1. Open **[@BotFather](https://t.me/BotFather)** in Telegram
2. Send `/newbot` → choose a name → choose a username (must end in `bot`)
3. **Copy the token** it gives you (e.g. `8641449158:AAH-gzI76Kz...`)

## 2. Get Your Chat ID

1. Open **[@userinfobot](https://t.me/userinfobot)** in Telegram
2. Send `/start`
3. **Copy the number** next to `Id` (e.g. `1792370231`)

## 3. Configure `.env`

Edit the `.env` file in the project root with your data:

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
CHECK_INTERVAL_SECONDS=10
```

## 4. Configure Email Accounts

Edit `config/accounts.json`. Each account requires an **app password** (not your regular password).

### Structure

```json
{
  "accounts": [
    {
      "email": "your_email@gmail.com",
      "password": "your app password",
      "imap_server": "imap.gmail.com",
      "imap_port": 993,
      "use_ssl": true
    }
  ]
}
```

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

## 6. Run

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

## 7. Useful Commands

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
