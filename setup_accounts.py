#!/usr/bin/env python3
"""
Authenticate multiple Google accounts for multi-account mail merge.

Run this once before using --num-accounts. A browser window will open
for each account so you can log in. Token files are saved as
token1.json, token2.json, etc.

Usage:
    python setup_accounts.py        # set up 5 accounts (default)
    python setup_accounts.py 3      # set up 3 accounts
"""

import sys
from sheets import get_credentials
from gmail_sender import get_gmail_service, get_sender_address


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"Setting up {n} accounts.")
    print("A browser window will open for each one — make sure to log into the right account each time.\n")

    for i in range(1, n + 1):
        token_path = f"token{i}.json"
        print(f"Account {i} of {n}: opening browser for login…")
        creds = get_credentials(token_path=token_path, credentials_path="credentials.json")
        gmail = get_gmail_service(creds)
        email = get_sender_address(gmail)
        print(f"  Authenticated as: {email}")
        print(f"  Saved to: {token_path}\n")

    print(f"All {n} accounts are set up!")
    print(f"You can now run the mail merge with:  --num-accounts {n}")


if __name__ == "__main__":
    main()
