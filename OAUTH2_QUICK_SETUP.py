#!/usr/bin/env python3
"""
INBOX BRIDGE - OAuth2 Setup Instructions
=========================================

Your Gmail accounts have 2FA enabled. The system now uses OAuth2
to authenticate WITHOUT requiring app passwords or account changes.

QUICK START (5 minutes)
======================

1. Get OAuth2 credentials from Google:
   - Go to https://console.cloud.google.com/
   - Create a new project (or use existing)
   - Enable "Gmail API" (search in APIs & Services)
   - Create OAuth 2.0 credentials (Desktop app)
   - Download JSON and copy: client_id and client_secret

2. Add credentials to .env:
   GMAIL_CLIENT_ID=your_client_id
   GMAIL_CLIENT_SECRET=your_client_secret

3. Run authentication setup (first time only):
   ./quickstart.sh
   Select option 2: "Setup Gmail OAuth2"

4. Authorize accounts in browser (one-time only)
   - System will open browser for each Gmail account
   - Click "Allow" to authorize
   - Tokens saved automatically

5. Start monitoring:
   ./quickstart.sh
   Select option 3: "Start monitoring"

WHAT HAPPENS UNDER THE HOOD
============================

✓ No app passwords needed
✓ No account changes required  
✓ No account recovery codes needed
✓ Secure tokens stored locally (gitignored)
✓ Tokens auto-refresh when expired
✓ Falls back to password if OAuth2 fails
✓ Outlook/Hotmail accounts use password directly

FILE STRUCTURE
==============

config/
├── accounts.json              ← Your email accounts (gitignored for security)
└── .oauth_tokens/             ← OAuth2 tokens (auto-generated, gitignored)
    ├── account_at_gmail_com.json
    ├── another_at_gmail_com.json
    └── ...

SCRIPTS PROVIDED
================

./quickstart.sh              - Interactive menu for all operations
python auth_setup.py        - Generate/refresh OAuth2 tokens
python test_accounts.py     - Test which accounts are working
python run.py              - Start the email monitor

TROUBLESHOOTING
===============

Q: "IMAP login failed" error
A: Run: python auth_setup.py

Q: "Token expired" error  
A: Run: python auth_setup.py and select "Re-authenticate"

Q: I don't have OAuth2 credentials
A: Create them at https://console.cloud.google.com/ (5 minutes)

Q: Can I use app passwords instead?
A: Yes, just update accounts.json with app password and remove GMAIL_CLIENT_ID/SECRET from .env

Q: Does this work with non-Gmail accounts?
A: Yes! Outlook, Hotmail, Yahoo, etc. use password directly (no OAuth2 needed)

GITHUB SECURITY
===============

✓ config/accounts.json is in .gitignore (passwords never pushed)
✓ config/.oauth_tokens/ is in .gitignore (tokens never pushed)
✓ Safe to run: git push

VERIFICATION
============

Check if OAuth2 is working:
  python test_accounts.py gmail

See which tokens are saved:
  ls -la config/.oauth_tokens/

View recent logs:
  tail -50 logs/email_monitor.log

NEXT STEPS
==========

1. Run: ./quickstart.sh
2. Follow the interactive menu
3. For detailed info: see OAUTH2_README.md

Questions? Check SETUP.md section 4.1 for complete OAuth2 documentation.
"""

if __name__ == "__main__":
    print(__doc__)
