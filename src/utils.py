import html as html_module
import re
from email.utils import parsedate_to_datetime

_EXCESS_NEWLINES = re.compile(r"\n{3,}")
_EXCESS_SPACES = re.compile(r"[^\S\n]+")


def sanitize_html(text: str) -> str:
    """Escape HTML special characters so the string is safe for Telegram."""
    return html_module.escape(text)


def truncate_text(text: str, max_length: int) -> str:
    """Truncate *text* at a word boundary and append '...' if shortened."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated.rstrip() + "..."


def clean_whitespace(text: str) -> str:
    """Normalize whitespace: collapse runs of spaces and blank lines."""
    text = _EXCESS_SPACES.sub(" ", text)
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    return text.strip()


def format_date(date_str: str) -> str:
    """Parse an RFC-2822 date string and return a human-readable format."""
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%d %B %Y, %H:%M")
    except Exception:
        return date_str.strip()
