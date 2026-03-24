"""Build and send emails via the Gmail API."""

import base64
import re
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from jinja2 import Environment, BaseLoader, StrictUndefined, UndefinedError


def _html_to_plain(html: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    # Replace block-level tags with newlines before stripping
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse excess blank lines (more than two in a row)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _make_jinja_env() -> Environment:
    """Return a Jinja2 env that uses {{var}} / {% %} delimiters."""
    return Environment(
        loader=BaseLoader(),
        undefined=StrictUndefined,
        autoescape=False,
    )


def render_template(template_str: str, row: dict) -> str:
    """Render *template_str* with *row* data, raising on unknown placeholders."""
    env = _make_jinja_env()
    try:
        return env.from_string(template_str).render(**row)
    except UndefinedError as exc:
        raise ValueError(
            f"Template placeholder not found in sheet columns: {exc}"
        ) from exc


def build_message(
    sender: str,
    recipient: str,
    subject: str,
    body_html: str,
) -> dict:
    """Return a Gmail API-ready message dict as plain text (no formatting)."""
    msg = MIMEText(body_html, "plain")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(service, message_dict: dict) -> dict:
    """Send a pre-built message dict via the Gmail API."""
    return service.users().messages().send(userId="me", body=message_dict).execute()


def create_draft(service, message_dict: dict) -> dict:
    """Save a pre-built message dict as a Gmail draft."""
    return service.users().drafts().create(userId="me", body={"message": message_dict}).execute()


def get_gmail_service(creds):
    return build("gmail", "v1", credentials=creds)


def get_sender_address(service) -> str:
    """Look up the authenticated user's email address."""
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]
