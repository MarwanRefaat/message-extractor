# Message Extractor 🚀

Extract and unify all your messages from **iMessage**, **WhatsApp**, **Gmail**, and **Google Calendar** into one timeline.

## Quick Start

```bash
# 1. Clone and enter
git clone <your-repo-url>
cd message-extractor

# 2. Install (one command!)
./install.sh

# 3. Extract messages
./run.sh --extract-all
```

**Done!** Your messages are in `output/unified/`

## What It Does

- 📱 **iMessage** - Extract all your iMessages
- 💬 **WhatsApp** - Extract WhatsApp messages  
- 📧 **Gmail** - Extract emails
- 📅 **Google Calendar** - Extract events
- 🔗 **Cross-link** - See all conversations with each person
- 📊 **Timeline** - One chronological view of everything

Only extracts messages from **2024 onwards** for privacy and speed.

## Usage

```bash
# Extract from all platforms
./run.sh --extract-all

# Just iMessage
./run.sh --extract-imessage

# Gmail + Calendar
./run.sh --extract-gmail --extract-gcal

# WhatsApp (needs database path)
./run.sh --extract-whatsapp --whatsapp-db /path/to/msgstore.db
```

## Setup Required

### iMessage (macOS)
- Nothing! Just run it.
- Close Messages app first if you get lock errors.

### Gmail / Google Calendar
1. Download `credentials.json` from [Google Cloud Console](https://console.cloud.google.com/)
2. Place it in this folder
3. Run: `./run.sh --extract-gmail`

### WhatsApp
- Extract database from device backup
- Run with `--whatsapp-db /path/to/database`

## Output

```
output/
├── raw/                    # Original data from each platform
└── unified/                # Combined everything
    ├── unified_ledger.json # Full data
    └── unified_timeline.txt# Human-readable timeline
```

## Requirements

- Python 3.8+
- macOS (for iMessage)
- Gmail/Calendar credentials (optional)

## License

MIT License - Use freely!

## Support

Open an issue on GitHub for help.
