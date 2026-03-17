#!/usr/bin/env python3
"""Interactive OAuth2 token generator for Gmail accounts with 2FA.

This script helps you generate OAuth2 tokens for all Gmail accounts
without changing account settings or using app passwords.

Usage:
    python auth_setup.py
"""

import json
import sys
from pathlib import Path

from loguru import logger

from src.oauth_manager import GmailOAuthClient, OAuthTokenManager


def load_config() -> tuple[str, str]:
    """Load OAuth2 client credentials from .env or config."""
    try:
        # Try to load from environment
        import os
        from dotenv import load_dotenv

        load_dotenv()

        client_id = os.getenv("GMAIL_CLIENT_ID")
        client_secret = os.getenv("GMAIL_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise ValueError("GMAIL_CLIENT_ID or GMAIL_CLIENT_SECRET not found in .env")

        return client_id, client_secret
    except Exception as e:
        logger.error(
            "Could not load OAuth credentials. Please add to .env:\n"
            "GMAIL_CLIENT_ID=your_client_id\n"
            "GMAIL_CLIENT_SECRET=your_client_secret\n"
            "Error: {e}",
            e=e,
        )
        sys.exit(1)


def authenticate_gmail_account(email: str, client_id: str, client_secret: str) -> bool:
    """Interactive authentication flow for a single Gmail account."""
    logger.info("Starting OAuth2 authentication for {email}", email=email)

    # Generate authorization URL
    auth_url = GmailOAuthClient.get_authorization_url(client_id, client_secret)
    if not auth_url:
        logger.error("Failed to generate authorization URL")
        return False

    print("\n" + "=" * 80)
    print(f"Authenticating: {email}")
    print("=" * 80)
    print("\n1. Click this link in your browser:")
    print(f"   {auth_url}\n")
    print("2. Sign in with the Gmail account")
    print("3. Grant permission to 'inbox-bridge'")
    print("4. Copy the authorization code from the page\n")

    auth_code = input("Enter authorization code: ").strip()
    if not auth_code:
        logger.warning("No authorization code provided for {email}", email=email)
        return False

    # Exchange code for token
    token_data = GmailOAuthClient.exchange_code_for_token(
        client_id, client_secret, auth_code
    )
    if not token_data:
        logger.error("Failed to exchange authorization code for token")
        return False

    # Save token
    OAuthTokenManager.save_token(email, token_data)
    logger.info(
        "Successfully authenticated {email}. Token saved.",
        email=email,
    )
    return True


def main():
    """Main authentication setup flow."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO",
    )

    print("\n" + "=" * 80)
    print("INBOX BRIDGE - Gmail OAuth2 Authentication Setup")
    print("=" * 80)
    print("\nThis script will help you authenticate Gmail accounts with 2FA")
    print("without changing account settings or using app passwords.\n")

    # Load credentials
    client_id, client_secret = load_config()
    logger.info("Loaded OAuth2 credentials")

    # Load accounts from config
    accounts_file = Path("config/accounts.json")
    if not accounts_file.exists():
        logger.error("config/accounts.json not found")
        sys.exit(1)

    try:
        with open(accounts_file) as f:
            accounts_config = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config/accounts.json: {e}", e=e)
        sys.exit(1)

    accounts = accounts_config.get("accounts", [])
    gmail_accounts = [
        acc for acc in accounts if "@gmail.com" in acc.get("email", "").lower()
    ]

    if not gmail_accounts:
        logger.warning("No Gmail accounts found in config/accounts.json")
        sys.exit(0)

    print(f"\nFound {len(gmail_accounts)} Gmail accounts to authenticate:\n")
    for i, acc in enumerate(gmail_accounts, 1):
        email = acc.get("email", "unknown")
        token_file = OAuthTokenManager.get_token_file(email)
        has_token = token_file.exists()
        status = "✓ Token exists" if has_token else "✗ Token needed"
        print(f"  {i}. {email:40} [{status}]")

    print("\nOptions:")
    print("  1. Authenticate all accounts")
    print("  2. Authenticate only accounts without tokens")
    print("  3. Re-authenticate specific account")
    print("  4. Exit")

    choice = input("\nSelect option (1-4): ").strip()

    if choice == "1":
        # Authenticate all
        authenticated = 0
        for acc in gmail_accounts:
            email = acc.get("email")
            if authenticate_gmail_account(email, client_id, client_secret):
                authenticated += 1
        logger.info(
            "Authentication complete: {n}/{total} accounts",
            n=authenticated,
            total=len(gmail_accounts),
        )

    elif choice == "2":
        # Authenticate only without tokens
        authenticated = 0
        for acc in gmail_accounts:
            email = acc.get("email")
            token_file = OAuthTokenManager.get_token_file(email)
            if not token_file.exists():
                if authenticate_gmail_account(email, client_id, client_secret):
                    authenticated += 1
        logger.info(
            "Authentication complete: {n} new accounts authenticated",
            n=authenticated,
        )

    elif choice == "3":
        # Re-authenticate specific
        print("\nEnter email address to re-authenticate:")
        email = input("Email: ").strip()
        if authenticate_gmail_account(email, client_id, client_secret):
            logger.info("Re-authentication successful")
        else:
            logger.error("Re-authentication failed")

    elif choice == "4":
        logger.info("Exiting")
        sys.exit(0)

    else:
        logger.error("Invalid option")
        sys.exit(1)

    print("\n" + "=" * 80)
    logger.info("Setup complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
