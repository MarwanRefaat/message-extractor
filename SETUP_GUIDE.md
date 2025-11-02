# Setup Guide

This guide walks you through setting up the Message Extractor for each supported platform.

## Prerequisites

- Python 3.8 or higher
- pip package manager

## Basic Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd message-extractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Verify installation:
```bash
python main.py --help
```

## Platform-Specific Setup

### iMessage (macOS only)

**Requirements:**
- macOS with Messages app
- Terminal/IDE with Full Disk Access permissions

**Setup Steps:**

1. Grant Full Disk Access:
   - Go to System Settings → Privacy & Security → Full Disk Access
   - Add Terminal or your IDE (e.g., Cursor, VS Code)

2. Close the Messages app:
   - Quit Messages completely before running the extractor

3. Extract data:
```bash
python main.py --extract-imessage
```

**Note:** The iMessage database is locked when Messages is running. Always close the app first.

### WhatsApp

**Requirements:**
- Access to WhatsApp database file (encrypted backup may not work)
- Root access for Android, or decrypted iOS backup

**iOS Setup:**

1. Create an encrypted backup using iTunes or Finder
2. Use a tool like [iMazing](https://imazing.com/) or [iBackup Viewer](https://www.imactools.com/iphonebackupviewer/) to extract the database
3. Locate `ChatStorage.sqlite` or similar database file
4. Extract data:
```bash
python main.py --extract-whatsapp --whatsapp-db /path/to/chatstorage.sqlite
```

**Android Setup:**

1. Enable USB debugging on your Android device
2. Use ADB to pull the database:
```bash
adb pull /data/data/com.whatsapp/databases/msgstore.db
```
3. Extract data:
```bash
python main.py --extract-whatsapp --whatsapp-db ./msgstore.db
```

**Note:** WhatsApp uses encryption. You may need a decrypted backup or a specialized tool.

### Gmail / G Suite

**Requirements:**
- Google Cloud Project with Gmail API enabled
- OAuth 2.0 credentials

**Setup Steps:**

1. Create a Google Cloud Project:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. Enable the Gmail API:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Select "Desktop app"
   - Download the credentials JSON file
   - Save as `credentials.json` in the project root

4. Extract data:
```bash
python main.py --extract-gmail
```

5. First run will open a browser for authentication:
   - Sign in with your Google account
   - Grant permissions
   - Token saved locally for future runs

**Security Note:** Keep your `credentials.json` and `token.json` files private. Never commit them to version control.

### Google Calendar

**Requirements:**
- Google Cloud Project with Calendar API enabled
- OAuth 2.0 credentials (can share with Gmail)

**Setup Steps:**

1. Enable the Google Calendar API:
   - In your Google Cloud Project
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google Calendar API"
   - Click "Enable"

2. Use the same credentials.json from Gmail setup

3. Extract data:
```bash
python main.py --extract-gcal
```

4. First run will open a browser for authentication

## Full Extraction Example

To extract from all available platforms:

```bash
python main.py --extract-all
```

This will:
- Extract iMessage (if on macOS)
- Extract WhatsApp (if database path provided)
- Extract Gmail (if authenticated)
- Extract Google Calendar (if authenticated)
- Create unified ledger with cross-platform linking

## Output Structure

After extraction, you'll find:

```
output/
├── raw/                          # Original platform data
│   ├── imessage_raw.jsonl       # One JSON object per line
│   ├── whatsapp_raw.jsonl
│   ├── gmail_raw.jsonl
│   └── gcal_raw.jsonl
└── unified/                      # Standardized unified ledger
    ├── unified_ledger.json      # Full data with all metadata
    └── unified_timeline.txt     # Human-readable chronological timeline
```

## Troubleshooting

### iMessage Issues

**"Permission denied" or "Database locked":**
- Close the Messages app completely
- Grant Full Disk Access to Terminal/IDE
- Try again

**"Database not found":**
- Check path: `~/Library/Messages/chat.db`
- Ensure you're on macOS

### WhatsApp Issues

**"Could not find recognized WhatsApp message tables":**
- Database structure may have changed
- Try extracting from a different backup version
- WhatsApp encryption makes this challenging

**"No such file or directory":**
- Verify database path is correct
- Check file permissions

### Gmail/Calendar Issues

**"ModuleNotFoundError: No module named 'google'":**
```bash
pip install -r requirements.txt
```

**"Credentials not found":**
- Download `credentials.json` from Google Cloud Console
- Place in project root directory

**"Access denied":**
- Revoke access at https://myaccount.google.com/permissions
- Delete `token.json`
- Re-run to re-authenticate

**"Quota exceeded":**
- Google APIs have rate limits
- Wait and try again later
- Consider using `--max-results` to limit extraction

### General Issues

**Import errors:**
```bash
pip install --upgrade -r requirements.txt
```

**Encoding errors:**
- Some messages may have special characters
- The extractor handles errors gracefully
- Check logs for specific problematic records

## Advanced Usage

### Extract Only Raw Data

Skip unified ledger creation:
```bash
python main.py --extract-all --raw-only
```

### Limit Results

Extract only recent messages:
```bash
python main.py --extract-imessage --max-results 1000
```

### Custom Output Directory

```bash
python main.py --extract-all --output-dir /path/to/my/output
```

## Security & Privacy

- **All processing is local**: No data sent to external servers
- **Credentials stored locally**: Keep `credentials.json` and `token.json` secure
- **Original data preserved**: Raw exports for auditability
- **Access controlled**: OAuth requires your explicit permission

## Next Steps

- Review the unified ledger in `output/unified/unified_timeline.txt`
- Use the JSON export for programmatic analysis
- Explore cross-platform contact linking
- See `example_usage.py` for API usage examples

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review platform-specific logs
3. Open a GitHub issue with details

