"""OAuth2 token manager for Gmail accounts with 2FA.

Handles token storage, refresh, and authentication without requiring
users to change their account settings.
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from loguru import logger

# OAuth2 token cache file
TOKEN_CACHE_DIR = Path("config/.oauth_tokens")
TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class OAuthTokenManager:
    """Manages OAuth2 tokens for Gmail accounts."""

    @staticmethod
    def get_token_file(email: str) -> Path:
        """Get the token file path for an email."""
        safe_email = email.replace("@", "_at_").replace(".", "_")
        return TOKEN_CACHE_DIR / f"{safe_email}.json"

    @staticmethod
    def load_token(email: str) -> Optional[dict]:
        """Load cached OAuth2 token for an email."""
        token_file = OAuthTokenManager.get_token_file(email)
        if not token_file.exists():
            return None

        try:
            with open(token_file, "r") as f:
                token_data = json.load(f)
                # Check if token has expired
                if "expires_at" in token_data:
                    expires_at = datetime.fromisoformat(token_data["expires_at"])
                    if datetime.now() > expires_at:
                        logger.warning(
                            "OAuth token expired for {email}, needs refresh",
                            email=email,
                        )
                        return None
                return token_data
        except Exception as e:
            logger.error("Error loading OAuth token for {email}: {e}", email=email, e=e)
            return None

    @staticmethod
    def save_token(email: str, token_data: dict) -> None:
        """Save OAuth2 token for an email."""
        token_file = OAuthTokenManager.get_token_file(email)
        try:
            with open(token_file, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info("OAuth token saved for {email}", email=email)
        except Exception as e:
            logger.error("Error saving OAuth token for {email}: {e}", email=email, e=e)

    @staticmethod
    def delete_token(email: str) -> None:
        """Delete cached OAuth2 token for an email."""
        token_file = OAuthTokenManager.get_token_file(email)
        if token_file.exists():
            try:
                token_file.unlink()
                logger.info("OAuth token deleted for {email}", email=email)
            except Exception as e:
                logger.error(
                    "Error deleting OAuth token for {email}: {e}", email=email, e=e
                )

    @staticmethod
    def create_mock_token(email: str, password: str) -> dict:
        """Create a token structure for accounts without OAuth.
        
        This is used as a fallback for non-Gmail accounts and allows
        the system to track authentication method.
        """
        return {
            "type": "password",
            "email": email,
            "password": password,
            "auth_method": "basic",
            "created_at": datetime.now().isoformat(),
        }


class GmailOAuthClient:
    """Client for Gmail OAuth2 authentication.
    
    This class handles the OAuth2 flow for Gmail accounts with 2FA
    without requiring app passwords or account changes.
    """

    # Google OAuth2 scopes for Gmail IMAP access
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    @staticmethod
    def get_authorization_url(client_id: str, client_secret: str) -> str:
        """Generate OAuth authorization URL for user.
        
        User must visit this URL and authorize the app.
        """
        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_config(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                    }
                },
                scopes=GmailOAuthClient.SCOPES,
            )

            auth_url, _ = flow.authorization_url(prompt="consent")
            return auth_url
        except ImportError:
            logger.error(
                "google-auth-oauthlib not installed. "
                "Run: pip install google-auth-oauthlib"
            )
            return ""

    @staticmethod
    def exchange_code_for_token(
        client_id: str, client_secret: str, auth_code: str
    ) -> Optional[dict]:
        """Exchange authorization code for OAuth token."""
        try:
            from google_auth_oauthlib.flow import Flow

            flow = Flow.from_client_config(
                {
                    "installed": {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                    }
                },
                scopes=GmailOAuthClient.SCOPES,
            )

            credentials = flow.fetch_token(code=auth_code)
            token_data = {
                "access_token": credentials.get("access_token"),
                "refresh_token": credentials.get("refresh_token"),
                "token_type": credentials.get("token_type", "Bearer"),
                "expires_in": credentials.get("expires_in", 3600),
                "expires_at": (
                    datetime.now() + timedelta(seconds=credentials.get("expires_in", 3600))
                ).isoformat(),
                "scopes": credentials.get("scopes", GmailOAuthClient.SCOPES),
            }
            return token_data
        except Exception as e:
            logger.error("Error exchanging auth code for token: {e}", e=e)
            return None

    @staticmethod
    def refresh_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[dict]:
        """Refresh an expired OAuth token."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials

            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
            )

            credentials.refresh(Request())

            token_data = {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": (datetime.now() + timedelta(seconds=3600)).isoformat(),
                "scopes": GmailOAuthClient.SCOPES,
            }
            return token_data
        except Exception as e:
            logger.error("Error refreshing token: {e}", e=e)
            return None
