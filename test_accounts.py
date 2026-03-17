#!/usr/bin/env python3
"""Diagnostic tool to test email account authentication.

Checks which accounts can be authenticated and reports issues.

Usage:
    python test_accounts.py          # Test all accounts
    python test_accounts.py gmail    # Test only Gmail accounts
    python test_accounts.py outlook  # Test only Outlook accounts
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger

from src.models import EmailAccount
from src.email_monitor import EmailMonitor
from src.database import Database
from src.oauth_manager import OAuthTokenManager


def load_accounts() -> list[EmailAccount]:
    """Load accounts from config/accounts.json."""
    config_path = Path("config/accounts.json")
    if not config_path.exists():
        logger.error("config/accounts.json not found")
        sys.exit(1)

    try:
        with open(config_path) as f:
            config = json.load(f)
        accounts = [
            EmailAccount(**acc) for acc in config.get("accounts", [])
        ]
        return accounts
    except Exception as e:
        logger.error("Error loading accounts: {e}", e=e)
        sys.exit(1)


def test_account(account: EmailAccount) -> tuple[bool, str]:
    """Test if an account can be authenticated.
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Check for OAuth2 token
        oauth_token = OAuthTokenManager.load_token(account.email)
        auth_method = "OAuth2" if oauth_token else "Password"

        # Try to connect
        conn = EmailMonitor._connect_imap(account)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, "UNSEEN")
        conn.logout()

        if status == "OK":
            unseen_count = len(data[0].split()) if data[0] else 0
            return True, f"✓ {auth_method} | {unseen_count} unseen emails"
        else:
            return False, f"✗ IMAP search failed"

    except ValueError as e:
        # OAuth2 or login error
        return False, f"✗ Auth failed: {str(e)[:50]}"
    except Exception as e:
        # Other errors
        return False, f"✗ Connection error: {str(e)[:50]}"


async def test_all_accounts(filter_type: Optional[str] = None) -> None:
    """Test all accounts concurrently."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    accounts = load_accounts()

    # Filter by type if specified
    if filter_type:
        if filter_type.lower() == "gmail":
            accounts = [a for a in accounts if "gmail" in a.email.lower()]
        elif filter_type.lower() == "outlook":
            accounts = [a for a in accounts if "outlook" in a.email.lower() or "hotmail" in a.email.lower()]

    if not accounts:
        logger.info("No accounts to test")
        return

    print("\n" + "=" * 100)
    print(f"Testing {len(accounts)} email accounts")
    print("=" * 100 + "\n")

    passed = 0
    failed = 0
    results = []

    for i, account in enumerate(accounts, 1):
        success, message = test_account(account)
        if success:
            passed += 1
            status = "✅"
        else:
            failed += 1
            status = "❌"

        results.append((account.email, status, message))
        print(f"[{i:3}/{len(accounts)}] {status} {account.email:45} {message}")

    print("\n" + "=" * 100)
    print(f"Results: {passed} passed ✅ | {failed} failed ❌")
    print("=" * 100)

    # Show failed accounts
    if failed > 0:
        print("\n🔴 FAILED ACCOUNTS:")
        for email, status, message in results:
            if status == "❌":
                print(f"  {email:45} {message}")

        print("\n💡 Solutions:")
        print("  1. For Gmail with 2FA: Run `python auth_setup.py`")
        print("  2. For Gmail without 2FA: Enable IMAP in Gmail Settings")
        print("  3. For Outlook/Hotmail: Use correct password")

    # Show OAuth2 status
    oauth_dir = Path("config/.oauth_tokens")
    if oauth_dir.exists():
        oauth_count = len(list(oauth_dir.glob("*.json")))
        print(f"\n🔐 OAuth2 Tokens: {oauth_count} saved")


def main():
    """Main entry point."""
    filter_type = None
    if len(sys.argv) > 1:
        filter_type = sys.argv[1]

    asyncio.run(test_all_accounts(filter_type))


if __name__ == "__main__":
    main()
