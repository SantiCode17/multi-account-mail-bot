#!/usr/bin/env python3
"""One-time OAuth2 token generator for Gmail accounts.

Reads config/accounts.json, filters Gmail accounts, and runs the
browser-based OAuth2 consent flow for each one.

Usage:
    python auth_setup.py
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from src import oauth_manager

load_dotenv()


def main() -> None:
    accounts_file = Path("config/accounts.json")
    if not accounts_file.exists():
        print("❌ config/accounts.json not found.")
        sys.exit(1)

    with open(accounts_file) as f:
        data = json.load(f)

    gmail_accounts = [
        a["email"]
        for a in data.get("accounts", [])
        if "gmail" in a.get("imap_server", "").lower()
    ]

    if not gmail_accounts:
        print("No Gmail accounts found in accounts.json.")
        return

    print(f"\n{'='*60}")
    print(f"  Gmail OAuth2 Setup — {len(gmail_accounts)} accounts")
    print(f"{'='*60}\n")

    # Show which already have tokens
    pending = []
    for em in gmail_accounts:
        if oauth_manager.has_token(em):
            print(f"  ✅ {em}  (already authorised)")
        else:
            pending.append(em)
            print(f"  ⏳ {em}  (needs authorisation)")

    if not pending:
        print("\n✅ All Gmail accounts already have tokens. Nothing to do.\n")
        return

    print(f"\n{len(pending)} account(s) need authorisation.\n")
    input("Press ENTER to start (a browser window will open for each account)...")

    success = 0
    for i, em in enumerate(pending, 1):
        print(f"\n── [{i}/{len(pending)}] {em} ──")
        try:
            oauth_manager.authorize_account(em)
            print(f"  ✅ Token saved for {em}")
            success += 1
        except Exception as e:
            print(f"  ❌ Failed: {e}")

    print(f"\n{'='*60}")
    print(f"  Done — {success}/{len(pending)} accounts authorised")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
