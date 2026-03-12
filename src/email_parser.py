import email
import email.header
import email.policy
import email.utils
import hashlib
from typing import Optional

from bs4 import BeautifulSoup

from src.models import EmailMessage
from src.utils import clean_whitespace, format_date, truncate_text


class EmailParser:
    """Extracts structured data from raw RFC-822 email bytes."""

    def __init__(self, preview_length: int = 500) -> None:
        self._preview_length = preview_length

    @staticmethod
    def _decode_header(raw: Optional[str]) -> str:
        """Decode an RFC-2047 encoded header value into a plain string."""
        if not raw:
            return ""
        parts: list[str] = []
        for fragment, charset in email.header.decode_header(raw):
            if isinstance(fragment, bytes):
                encoding = charset or "utf-8"
                try:
                    parts.append(fragment.decode(encoding, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    parts.append(fragment.decode("utf-8", errors="replace"))
            else:
                parts.append(fragment)
        return " ".join(parts)

    def parse_sender(self, msg: email.message.Message) -> str:
        return self._decode_header(msg.get("From", ""))

    def parse_subject(self, msg: email.message.Message) -> str:
        return self._decode_header(msg.get("Subject", ""))

    def parse_date(self, msg: email.message.Message) -> str:
        raw_date = msg.get("Date", "")
        return format_date(raw_date)

    def parse_message_id(
        self, msg: email.message.Message, account_email: str
    ) -> str:
        """Return the Message-ID header, or generate a fallback hash."""
        mid = msg.get("Message-ID", "").strip()
        if mid:
            return mid

        subject = msg.get("Subject", "")
        date = msg.get("Date", "")
        sender = msg.get("From", "")
        composite = f"{account_email}|{sender}|{subject}|{date}"
        return hashlib.sha256(composite.encode()).hexdigest()

    def _extract_text_plain(self, part: email.message.Message) -> str:
        """Decode a text/plain MIME part."""
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")

    def _extract_text_html(self, part: email.message.Message) -> str:
        """Decode an HTML part and strip tags, preserving line breaks."""
        payload = part.get_payload(decode=True)
        if payload is None:
            return ""
        charset = part.get_content_charset() or "utf-8"
        try:
            html_str = payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html_str = payload.decode("utf-8", errors="replace")

        soup = BeautifulSoup(html_str, "html.parser")
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for tag in soup.find_all(["p", "div", "tr"]):
            tag.insert_before("\n")
            tag.insert_after("\n")
        return soup.get_text()

    def parse_body(self, msg: email.message.Message) -> str:
        """Extract the best plain-text representation of the email body."""
        if not msg.is_multipart():
            ctype = msg.get_content_type()
            if ctype == "text/plain":
                raw = self._extract_text_plain(msg)
            elif ctype == "text/html":
                raw = self._extract_text_html(msg)
            else:
                raw = ""
            return truncate_text(clean_whitespace(raw), self._preview_length)

        plain_parts: list[str] = []
        html_parts: list[str] = []

        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if ctype == "text/plain":
                plain_parts.append(self._extract_text_plain(part))
            elif ctype == "text/html":
                html_parts.append(self._extract_text_html(part))

        if plain_parts:
            raw = "\n".join(plain_parts)
        elif html_parts:
            raw = "\n".join(html_parts)
        else:
            raw = ""

        return truncate_text(clean_whitespace(raw), self._preview_length)

    def parse_email(
        self, raw_bytes: bytes, account_email: str
    ) -> EmailMessage:
        """Parse raw email bytes into a structured EmailMessage."""
        msg = email.message_from_bytes(raw_bytes, policy=email.policy.compat32)

        return EmailMessage(
            message_id=self.parse_message_id(msg, account_email),
            account_email=account_email,
            sender=self.parse_sender(msg),
            subject=self.parse_subject(msg) or "(no subject)",
            date=self.parse_date(msg),
            body_preview=self.parse_body(msg),
        )
