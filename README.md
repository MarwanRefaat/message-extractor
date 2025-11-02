# Message Extractor

A comprehensive tool to extract messages and transactions from iMessage, WhatsApp, Gmail, and Google Calendar into a standardized, unified ledger with cross-platform contact linking.

## Features

- **Multi-platform extraction**: Support for iMessage, WhatsApp, Gmail, and Google Calendar
- **Standardized schema**: MECE (Mutually Exclusive, Collectively Exhaustive) format for all data
- **Cross-linking**: Automatic contact deduplication and linking across platforms
- **Timeline generation**: Chronologically ordered unified ledger
- **Date filtering**: Default filter extracts only 2024 onwards
- **Raw data preservation**: Original data exported separately for reference
- **Rich metadata**: Includes attachments, read status, event details, and more

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd message-extractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google API credentials (for Gmail and Calendar):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Gmail API and Google Calendar API
   - Create OAuth 2.0 credentials
   - Download credentials JSON file and save as `credentials.json` in the project root

## Usage

### Extract from all sources
```bash
python main.py --extract-all
```

### Extract from specific sources
```bash
# iMessage only
python main.py --extract-imessage

# iMessage + Gmail
python main.py --extract-imessage --extract-gmail

# WhatsApp (requires database path)
python main.py --extract-whatsapp --whatsapp-db /path/to/whatsapp/db

# Google Calendar
python main.py --extract-gcal
```

### Options
- `--output-dir DIR`: Specify output directory (default: `./output`)
- `--max-results N`: Limit records per source (default: 10000)
- `--raw-only`: Only export raw data, skip unified ledger
- `--whatsapp-db PATH`: Path to WhatsApp database file

### Output Structure

```
output/
├── raw/                          # Raw extracted data
│   ├── imessage_raw.jsonl
│   ├── whatsapp_raw.jsonl
│   ├── gmail_raw.jsonl
│   └── gcal_raw.jsonl
└── unified/                      # Standardized unified ledger
    ├── unified_ledger.json      # Full JSON with all metadata
    └── unified_timeline.txt     # Human-readable timeline
```

## Platform-Specific Notes

### iMessage
- **Location**: `~/Library/Messages/chat.db`
- **Permissions**: May require granting Terminal/IDE full disk access on macOS
- **Note**: Database is locked when Messages app is running. Close Messages before extraction.

### WhatsApp
- **iOS**: Extract from device backup or SQLite database
- **Android**: Located in `/data/data/com.whatsapp/databases/msgstore.db` (requires root or backup)
- **Note**: WhatsApp encryption makes this challenging. May need decrypted backup.

### Gmail
- Requires OAuth 2.0 authentication
- Uses Gmail API with readonly scope
- First run will open browser for authentication
- Token saved for subsequent runs

### Google Calendar
- Requires OAuth 2.0 authentication
- Uses Google Calendar API with readonly scope
- Shares credentials with Gmail if same account

## Data Schema

Each message/transaction in the unified ledger contains:

### Core Fields
- `message_id`: Unique identifier across all platforms
- `platform`: Source platform (imessage/whatsapp/gmail/gcal)
- `timestamp`: ISO 8601 datetime
- `sender`: Contact information (name, email, phone, platform_id)
- `recipients`: List of recipient contacts
- `participants`: All unique contacts involved
- `subject`: Subject line (for emails/events)
- `body`: Message content
- `attachments`: List of attachment files

### Metadata
- `thread_id`: Conversation/thread identifier
- `is_read`: Read status
- `is_starred`: Starred/favorite status
- `is_reply`: Whether message is a reply
- `original_message_id`: Original message ID if reply

### Event-Specific (Calendar)
- `event_start`: Event start datetime
- `event_end`: Event end datetime
- `event_location`: Event location
- `event_status`: confirmed/tentative/cancelled

### Platform Raw Data
- `raw_data`: Original platform-specific data preserved

## Contact Cross-Linking

The system automatically deduplicates contacts by:
- Email addresses
- Phone numbers
- Platform-specific IDs

Use `unified_ledger.get_conversations_with_contact(email_or_phone)` to retrieve all messages with a specific contact across all platforms.

## Security & Privacy

- All data processing is local
- Google credentials stored locally only
- No data transmitted to external servers
- Raw data preserved for auditability

## Limitations

- **WhatsApp**: Requires decrypted database (encryption varies by platform/version)
- **iMessage**: Database locking when Messages app is running
- **Gmail/Calendar**: Rate limits may apply with very large mailboxes
- **Timezone**: Some platforms don't provide timezone info

## Development

### Project Structure
```
message-extractor/
├── schema.py                    # Core data schemas
├── main.py                      # Main orchestrator
├── extractors/
│   ├── __init__.py
│   ├── imessage_extractor.py
│   ├── whatsapp_extractor.py
│   ├── gmail_extractor.py
│   └── gcal_extractor.py
├── requirements.txt
└── README.md
```

## License

MIT License - See LICENSE file for details

## Contributing

Pull requests welcome! Please ensure:
- Code follows PEP 8 style guidelines
- Add tests for new extractors
- Update README for new features
- Handle errors gracefully

## Support

For issues, questions, or feature requests, please open a GitHub issue.

## Disclaimer

This tool is for personal data management and backup purposes. Ensure you comply with:
- Terms of Service for each platform
- Local privacy and data protection laws
- Institutional policies if used in professional settings

