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
import os
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
    p.add_argument(
        "--num-accounts",
        type=int,
        default=1,
        metavar="N",
        help="Split emails equally across N accounts (uses token1.json through tokenN.json). "
             "Run setup_accounts.py first to authenticate each account.",
    )
    return p.parse_args(argv)


def load_template(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        sys.exit(f"Error: template file '{path}' not found.")


def split_rows(rows, n):
    """Split rows into n roughly-equal chunks."""
    k, rem = divmod(len(rows), n)
    chunks, start = [], 0
    for i in range(n):
        size = k + (1 if i < rem else 0)
        chunks.append(rows[start:start + size])
        start += size
    return [c for c in chunks if c]


def build_subject(subject_template, row):
    subject = render_template(subject_template, row)
    recall = row.get("recall", "").strip()
    year_match = re.search(r"(2021|2022|2023|2024)", recall)
    if year_match:
        subject = f"{row.get('company', '')} since {year_match.group(1)}"
    elif recall:
        subject = subject.replace("round", "update")
    return subject


def process_chunk(chunk, gmail, sender, body_template, args, acct_label=""):
    saved = errors = 0
    for idx, row in enumerate(chunk):
        recipient = row.get(EMAIL_COLUMN, "").strip()
        if not recipient:
            print(f"  {acct_label}Row {idx+1}: skipping — no email address.")
            continue

        try:
            subject = build_subject(args.subject, row)
            body = _html_to_plain(render_template(body_template, row))
        except ValueError as exc:
            print(f"  {acct_label}Row {idx+1} ({recipient}): template error — {exc}")
            errors += 1
            continue

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  From   : {sender}")
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
                    print(f"  {acct_label}Row {idx+1}: sent → {recipient}")
                    if idx < len(chunk) - 1:
                        time.sleep(30)
                else:
                    create_draft(gmail, msg)
                    print(f"  {acct_label}Row {idx+1}: draft saved → {recipient}")
                saved += 1
            except Exception as exc:
                action = "send" if args.send else "draft"
                print(f"  {acct_label}Row {idx+1} ({recipient}): {action} failed — {exc}")
                errors += 1
    return saved, errors


def main(argv=None):
    args = parse_args(argv)
    body_template = load_template(args.template)

    # For multi-account mode, use token1.json to read the sheet
    sheet_token = "token1.json" if args.num_accounts > 1 else args.token

    print("Authenticating with Google…")
    creds = get_credentials(token_path=sheet_token, credentials_path=args.credentials)

    print(f"Reading sheet {args.sheet_id} (range: {args.range})…")
    rows = read_sheet(args.sheet_id, args.range, creds)

    if not rows:
        sys.exit("No data rows found in the sheet.")

    if EMAIL_COLUMN not in rows[0]:
        sys.exit(
            f"Error: sheet must have a column named '{EMAIL_COLUMN}'. "
            f"Found columns: {list(rows[0].keys())}"
        )

    total_saved = total_errors = 0

    if args.num_accounts == 1:
        gmail = get_gmail_service(creds)
        sender = get_sender_address(gmail)
        mode = "Sending" if args.send else "Saving drafts"
        print(f"{mode} as: {sender}")
        total_saved, total_errors = process_chunk(rows, gmail, sender, body_template, args)

    else:
        n = args.num_accounts
        chunks = split_rows(rows, n)
        print(f"Splitting {len(rows)} row(s) across {n} accounts…\n")

        for i in range(n):
            token_path = f"token{i+1}.json"
            if not os.path.exists(token_path):
                sys.exit(
                    f"Error: {token_path} not found.\n"
                    f"Run this first to set up your accounts:\n"
                    f"  python setup_accounts.py {n}"
                )
            chunk = chunks[i] if i < len(chunks) else []
            if not chunk:
                print(f"Account {i+1}: no rows assigned, skipping.")
                continue

            print(f"Authenticating account {i+1}…")
            acct_creds = get_credentials(token_path=token_path, credentials_path=args.credentials)
            gmail = get_gmail_service(acct_creds)
            sender = get_sender_address(gmail)
            mode = "Sending" if args.send else "Saving drafts"
            print(f"Account {i+1} ({sender}): {mode} {len(chunk)} email(s)")

            s, e = process_chunk(chunk, gmail, sender, body_template, args, acct_label=f"[Acct {i+1}] ")
            total_saved += s
            total_errors += e
            print()

    print()
    if args.dry_run:
        print(f"Dry run complete. Would have {'sent' if args.send else 'saved'} {len(rows)} email(s).")
    else:
        action = "Sent" if args.send else "Drafts saved"
        print(f"Done. {action}: {total_saved}  |  Errors: {total_errors}")


if __name__ == "__main__":
    main()
