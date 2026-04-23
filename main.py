#!/usr/bin/env python3
"""
Gmail Mail Merge
================
Reads rows from a Google Sheet and sends a personalised email to each recipient.

Usage:
    python main.py --sheet-id <SPREADSHEET_ID> \
                   --template email_template.html \
                   --subject "Hello, {{first_name}}!" \
                   [--range "Sheet1!A:Z"] \
                   [--dry-run]

Sheet format
------------
Row 1  : Column headers  →  become template placeholder names
Column : email           →  recipient address (required)
Other  : any name        →  available as {{column_name}} in the subject / body

Example columns:
    email | first_name | company | order_id
"""

import argparse
import re
import sys
import time

from sheets import get_credentials, read_sheet
from gmail_sender import (
    get_gmail_service,
    get_sender_address,
    render_template,
    build_message,
    create_draft,
    send_email,
    _html_to_plain,
)


EMAIL_COLUMN = "email"  # Name of the column that holds the recipient address


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Send personalised Gmail messages from a Google Sheet."
    )
    p.add_argument(
        "--sheet-id",
        required=True,
        metavar="SPREADSHEET_ID",
        help="The ID from your Google Sheet URL "
             "(the long string between /d/ and /edit).",
    )
    p.add_argument(
        "--template",
        default="email_template.html",
        metavar="FILE",
        help="Path to the HTML email template (default: email_template.html).",
    )
    p.add_argument(
        "--subject",
        required=True,
        metavar="SUBJECT_TEMPLATE",
        help='Subject line with {{placeholders}}, e.g. "Hi {{first_name}}!"',
    )
    p.add_argument(
        "--range",
        default="Sheet1!A:Z",
        metavar="A1_RANGE",
        help="Sheet range to read (default: Sheet1!A:Z).",
    )
    p.add_argument(
        "--send",
        action="store_true",
        help="Send emails immediately instead of saving as drafts.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview rendered emails without sending them.",
    )
    p.add_argument(
        "--credentials",
        default="credentials.json",
        metavar="FILE",
        help="Path to your OAuth2 credentials file (default: credentials.json).",
    )
    p.add_argument(
        "--token",
        default="token.json",
        metavar="FILE",
        help="Path where the OAuth token is cached (default: token.json).",
    )
    return p.parse_args(argv)


def load_template(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        sys.exit(f"Error: template file '{path}' not found.")


def main(argv=None):
    args = parse_args(argv)

    body_template = load_template(args.template)

    print("Authenticating with Google…")
    creds = get_credentials(
        token_path=args.token,
        credentials_path=args.credentials,
    )

    print(f"Reading sheet {args.sheet_id} (range: {args.range})…")
    rows = read_sheet(args.sheet_id, args.range, creds)

    if not rows:
        sys.exit("No data rows found in the sheet.")

    if EMAIL_COLUMN not in rows[0]:
        sys.exit(
            f"Error: sheet must have a column named '{EMAIL_COLUMN}'. "
            f"Found columns: {list(rows[0].keys())}"
        )

    gmail = get_gmail_service(creds)
    sender = get_sender_address(gmail)
    mode = "Sending" if args.send else "Saving drafts"
    print(f"{mode} as: {sender}")

    saved = 0
    errors = 0

    for i, row in enumerate(rows, start=1):
        recipient = row.get(EMAIL_COLUMN, "").strip()
        if not recipient:
            print(f"  Row {i}: skipping — no email address.")
            continue

        try:
            subject = render_template(args.subject, row)
            recall = row.get("recall", "").strip()
            year_match = re.search(r"(2021|2022|2023|2024)", recall)
            if year_match:
                subject = f"{row.get('company', '')} since {year_match.group(1)}"
            elif recall:
                subject = subject.replace("round", "update")
            body = _html_to_plain(render_template(body_template, row))
        except ValueError as exc:
            print(f"  Row {i} ({recipient}): template error — {exc}")
            errors += 1
            continue

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  To     : {recipient}")
            print(f"  Subject: {subject}")
            print(f"  Body preview (first 300 chars):")
            print(f"  {body[:300].replace(chr(10), chr(10)+'  ')}")
            print(f"{'='*60}")
        else:
            try:
                msg = build_message(sender, recipient, subject, body)
                if args.send:
                    send_email(gmail, msg)
                    print(f"  Row {i}: sent → {recipient}")
                    if i < len(rows):
                        time.sleep(30)
                else:
                    create_draft(gmail, msg)
                    print(f"  Row {i}: draft saved → {recipient}")
                saved += 1
            except Exception as exc:
                action = "send" if args.send else "draft"
                print(f"  Row {i} ({recipient}): {action} failed — {exc}")
                errors += 1

    print()
    if args.dry_run:
        print(f"Dry run complete. Would have {'sent' if args.send else 'saved'} {len(rows)} email(s).")
    else:
        action = "Sent" if args.send else "Drafts saved"
        print(f"Done. {action}: {saved}  |  Errors: {errors}")


if __name__ == "__main__":
    main()
