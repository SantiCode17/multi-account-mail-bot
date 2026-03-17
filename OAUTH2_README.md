## ⚠️ IMPORTANT: OAuth2 Setup for Gmail 2FA Accounts

Your accounts have **2FA enabled**. The system now **automatically** uses **OAuth2** authentication for Gmail accounts without requiring app passwords or account changes.

### 🚀 Quick Start

#### Option A: If you have Gmail OAuth2 credentials (recommended)

1. **Get OAuth2 credentials** from Google Cloud Console:
   - Go to https://console.cloud.google.com/
   - Create a new project
   - Enable Gmail API
   - Create OAuth 2.0 Desktop credentials
   - Download the JSON and get: `client_id` and `client_secret`

2. **Add to `.env`**:
   ```env
   GMAIL_CLIENT_ID=your_client_id_here
   GMAIL_CLIENT_SECRET=your_client_secret_here
   ```

3. **Run authentication setup**:
   ```bash
   source venv/bin/activate
   python auth_setup.py
   ```
   
4. **Follow the browser prompts** for each Gmail account
   - System will save tokens automatically (one-time setup)

5. **Start the monitor**:
   ```bash
   python run.py
   ```

---

#### Option B: If you prefer app passwords (simpler, but requires account changes)

For each Gmail account:

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Windows/Linux"  
3. Generate 16-character app password
4. Update `config/accounts.json` with that password
5. Remove the `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` from `.env`
6. Start normally: `python run.py`

---

### 🔑 How OAuth2 Works (Technical)

- **No account changes needed**: Your regular password stays the same
- **No app password required**: Gmail OAuth2 token handles authentication  
- **Secure**: Tokens stored in `config/.oauth_tokens/` (gitignored)
- **One-time setup**: OAuth2 tokens are refreshed automatically
- **Fallback to password**: If OAuth2 fails, system tries password auth

---

### ✅ Verification

To check if OAuth2 is working:

```bash
source venv/bin/activate
python -c "from src.oauth_manager import OAuthTokenManager; import pathlib; tokens = list(pathlib.Path('config/.oauth_tokens/').glob('*.json')); print(f'OAuth tokens found: {len(tokens)}')"
```

---

### ❓ Troubleshooting

**"IMAP login failed" error**:
- Gmail with 2FA: Run `python auth_setup.py` again
- Gmail without 2FA: Ensure IMAP is enabled in Gmail Settings
- Outlook/Hotmail: Use your regular password

**"Token expired" error**:
- Run `python auth_setup.py` and select "Re-authenticate specific account"

**Which should I use?**:
- OAuth2 (Option A): ✅ Recommended - more secure, no account changes
- App Passwords (Option B): Works fine, but requires updating 135+ passwords

---

See `SETUP.md` section 4 for complete detailed instructions.
