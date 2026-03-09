"""Read rows from a Google Sheet."""

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_credentials(token_path="token.json", credentials_path="credentials.json"):
    """Return valid OAuth2 credentials, prompting the user to log in if needed."""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"'{credentials_path}' not found. "
                    "Download it from the Google Cloud Console and place it here."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def read_sheet(spreadsheet_id: str, sheet_range: str, creds) -> list[dict]:
    """
    Read a Google Sheet and return a list of row dicts.

    The first row must be headers; they become the keys in each dict.
    Every column header is also the placeholder name you use in your
    template, e.g. {{first_name}}.
    """
    service = build("sheets", "v4", credentials=creds)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=sheet_range)
        .execute()
    )
    rows = result.get("values", [])
    if not rows:
        return []

    headers = rows[0]
    records = []
    for row in rows[1:]:
        # Pad short rows so every header has a value
        padded = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded)))

    return records
