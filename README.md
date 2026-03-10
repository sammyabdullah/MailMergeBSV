# Gmail Mail Merge

Send personalised HTML emails from a **Google Sheet** using the Gmail API.

---

## Features

- Reads any number of columns from a Google Sheet — every column header becomes a `{{placeholder}}`
- Customise both the **subject line** and the **email body** with placeholders
- Sends HTML emails with an automatic plain-text fallback
- `--dry-run` mode lets you preview rendered emails before sending
- OAuth2 login — no passwords stored, uses your own Google account

---

## Quick Start

### 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### 2 — Enable Google APIs & download credentials

1. Go to <https://console.cloud.google.com/>
2. Create a project (or select an existing one)
3. Enable these two APIs:
   - **Gmail API**
   - **Google Sheets API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
5. Download the JSON file and save it as **`credentials.json`** in this folder

### 3 — Set up your Google Sheet

Your sheet must have a **header row** in row 1. Column names become placeholder names.

**Required column:** `email` — the recipient's address.

Example layout:

| email              | first_name | company   | order_id |
|--------------------|------------|-----------|----------|
| alice@example.com  | Alice      | ACME Corp | 1001     |
| bob@example.com    | Bob        | Globex    | 1002     |

Get your **Spreadsheet ID** from the URL:
```
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
```

### 4 — Create your email template

Edit `email_template.html` (or create a new `.html` file). Use `{{column_name}}` anywhere you want to insert sheet data.

```html
<p>Hi {{first_name}},</p>
<p>Your order #{{order_id}} from {{company}} is ready!</p>
```

### 5 — Send!

```bash
# Preview without sending
python main.py \
  --sheet-id YOUR_SPREADSHEET_ID \
  --subject "Hi {{first_name}}, your order #{{order_id}} is ready!" \
  --template email_template.html \
  --dry-run

# Save as drafts (default)
python main.py \
  --sheet-id YOUR_SPREADSHEET_ID \
  --subject "Hi {{first_name}}, your order #{{order_id}} is ready!" \
  --template email_template.html

# Send immediately
python main.py \
  --sheet-id YOUR_SPREADSHEET_ID \
  --subject "Hi {{first_name}}, your order #{{order_id}} is ready!" \
  --template email_template.html \
  --send
```

The first run will open a browser window for you to authorise access. A `token.json` file is saved so you won't need to log in again.

---

## Command Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--sheet-id` | *(required)* | Spreadsheet ID from the Google Sheet URL |
| `--subject` | *(required)* | Subject line with `{{placeholders}}` |
| `--template` | `email_template.html` | Path to your HTML template file |
| `--range` | `Sheet1!A:Z` | A1 notation range to read from the sheet |
| `--send` | off | Send emails immediately (default: save as drafts) |
| `--dry-run` | off | Preview emails without sending or drafting |
| `--credentials` | `credentials.json` | Path to your OAuth2 credentials file |
| `--token` | `token.json` | Path where the OAuth token is cached |

---

## Security Notes

- `credentials.json` and `token.json` are listed in `.gitignore` — **never commit them**
- The app only requests `gmail.send` (send-only) and `spreadsheets.readonly` scopes
- Tokens are stored locally on your machine only
