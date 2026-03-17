"""Minimal OAuth2 manager for Gmail IMAP access.

Handles the full lifecycle: authorize → store → load → auto-refresh.
Tokens are persisted in ``config/credentials/`` (one JSON per account).
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

SCOPES = ["https://mail.google.com/"]
TOKEN_DIR = Path("config/credentials")
TOKEN_DIR.mkdir(parents=True, exist_ok=True)


def _token_path(email: str) -> Path:
    safe = email.replace("@", "_at_").replace(".", "_")
    return TOKEN_DIR / f"{safe}.json"


def _client_config() -> dict:
    """Build the client config dict from env vars."""
    client_id = os.getenv("GMAIL_CLIENT_ID", "")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError(
            "Missing GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET in .env — "
            "see SETUP.md section 4"
        )
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


# ── Public API ──────────────────────────────────────────────────────


def authorize_account(email: str) -> Credentials:
    """Interactive: open browser, user logs in, token saved.
    
    Called once per account from ``auth_setup.py``.
    """
    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    print(f"\n→  Authorize: {email}")
    print("   A browser window will open. Log in with THIS account.\n")
    creds = flow.run_local_server(port=0, prompt="consent")
    _save(email, creds)
    logger.info("Token saved for {e}", e=email)
    return creds


def get_access_token(email: str) -> str | None:
    """Return a valid access token for *email*, refreshing if needed.

    Returns ``None`` when no token file exists (account was never
    authorized).
    """
    path = _token_path(email)
    if not path.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    except Exception as exc:
        logger.warning("Bad token file for {e}: {x}", e=email, x=exc)
        return None

    if creds.valid:
        return creds.token

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(email, creds)
            return creds.token
        except Exception as exc:
            logger.warning("Token refresh failed for {e}: {x}", e=email, x=exc)
            return None

    return None


def has_token(email: str) -> bool:
    return _token_path(email).exists()


# ── Helpers ─────────────────────────────────────────────────────────


def _save(email: str, creds: Credentials) -> None:
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    with open(_token_path(email), "w") as f:
        json.dump(data, f, indent=2)

