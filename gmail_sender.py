"""Build and send emails via the Gmail API."""

import base64
import re
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from jinja2 import Environment, BaseLoader, StrictUndefined, UndefinedError


def _html_to_plain(html: str) -> str:
    """Convert HTML to plain text, preserving paragraph breaks."""
    # Paragraph-ending tags → blank line separator
    text = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n\n", text, flags=re.IGNORECASE)
    # Line-break tags → single newline
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Strip leading/trailing whitespace from each line
    text = "\n".join(line.strip() for line in text.splitlines())
    # Collapse 3+ newlines to exactly two (one blank line between paragraphs)
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


def _plain_to_gmail_html(text: str) -> str:
    """Convert plain text to Gmail's native div-based HTML format.

    This matches exactly what Gmail creates when you type an email manually,
    so drafts send identically from laptop (web) and phone (app).
    """
    parts = []
    for line in text.split("\n"):
        if line:
            escaped = (
                line.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
            )
            parts.append(f"<div>{escaped}</div>")
        else:
            parts.append("<div><br></div>")
    return '<div dir="ltr">' + "".join(parts) + "</div>"


def build_message(
    sender: str,
    recipient: str,
    subject: str,
    body_html: str,
) -> dict:
    """Return a Gmail API-ready message dict in Gmail's native HTML format."""
    msg = MIMEText(_plain_to_gmail_html(body_html), "html")
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
