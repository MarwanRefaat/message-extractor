# Project Overview

## Architecture

Message Extractor follows a modular, extensible architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Orchestrator                     │
│                         (main.py)                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼────────┐ ┌───▼────┐ ┌────────▼────────┐
    │  iMessage        │ │Gmail   │ │ Google Calendar │
    │  Extractor       │ │Extractor│ │ Extractor       │
    └─────────┬────────┘ └───┬────┘ └────────┬────────┘
              │               │               │
    ┌─────────▼────────┐ ┌───▼────┐ ┌────────▼────────┐
    │   WhatsApp       │ │        │ │                 │
    │   Extractor      │ │        │ │                 │
    └─────────┬────────┘ └────────┘ └─────────────────┘
              │
              │
    ┌─────────▼──────────────────────────────────────────┐
    │         Standardized Schema                         │
    │         (Contact, Message, UnifiedLedger)           │
    └─────────┬──────────────────────────────────────────┘
              │
    ┌─────────▼──────────────────────────────────────────┐
    │         Unified Output                              │
    │  • Raw data (JSONL per platform)                   │
    │  • Unified ledger (JSON)                           │
    │  • Timeline (human-readable)                       │
    └─────────────────────────────────────────────────────┘
```

## Core Components

### 1. Schema (`schema.py`)

Defines the standardized data models:

- **Contact**: Unified representation of people across platforms
- **Message**: MECE-format transaction/message object
- **UnifiedLedger**: Central registry with cross-linking capabilities

Key features:
- Platform-agnostic data model
- Automatic contact deduplication
- Rich metadata preservation
- JSON serialization support

### 2. Extractors (`extractors/`)

Platform-specific extraction modules:

#### iMessageExtractor
- Source: macOS `~/Library/Messages/chat.db`
- Technology: SQLite
- Challenges: Database locking, timestamp conversion

#### WhatsAppExtractor
- Source: WhatsApp SQLite database
- Technology: SQLite
- Challenges: Encryption, varying schemas by version

#### GmailExtractor
- Source: Gmail API
- Technology: Google Gmail API
- Challenges: Rate limits, OAuth authentication

#### GoogleCalendarExtractor
- Source: Google Calendar API
- Technology: Google Calendar API
- Challenges: Rate limits, OAuth authentication

Each extractor implements:
- `extract_all()`: Extract into UnifiedLedger
- `export_raw()`: Export raw platform data

### 3. Main Orchestrator (`main.py`)

Command-line interface that:
- Coordinates multi-platform extraction
- Manages output directories
- Handles user options
- Generates unified outputs

### 4. Utilities

- `example_usage.py`: API usage examples
- Documentation: README, SETUP_GUIDE, QUICKSTART

## Data Flow

```
┌──────────────┐
│  Platform    │
│  Database    │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│  Platform        │
│  Extractor       │
│  (Raw SQL/API)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Schema          │
│  Conversion      │
│  (Contact/Message)│
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  UnifiedLedger   │
│  (Cross-link)    │
└──────┬───────────┘
       │
       ├─────────────► unified_ledger.json
       ├─────────────► unified_timeline.txt
       └─────────────► raw/*.jsonl (preserved)
```

## Design Principles

### MECE (Mutually Exclusive, Collectively Exhaustive)

Each message/transaction is:
- **Complete**: All available information captured
- **Non-overlapping**: Clear boundaries between fields
- **Standardized**: Same schema across all platforms

### Cross-Platform Linking

Contacts are linked by:
- Email addresses
- Phone numbers
- Platform-specific IDs

Enables queries like: "All interactions with john@example.com across iMessage, Gmail, and Calendar"

### Extensibility

Adding new platforms is straightforward:
1. Create new extractor class
2. Implement `extract_all()` and `export_raw()`
3. Use existing schema
4. Register in `__init__.py` and `main.py`

### Data Preservation

Three-tier output:
1. **Raw**: Original platform data (JSONL)
2. **Unified JSON**: Structured with full metadata
3. **Timeline**: Human-readable chronological view

## Use Cases

### Personal Knowledge Base
Extract your entire communications history for:
- Search and discovery
- Memory assistance
- Personal analytics

### Contact Management
Unified contact registry showing:
- All interactions per contact
- Communication patterns
- Cross-platform relationships

### Data Portability
Export from proprietary platforms:
- iMessage → Standard format
- WhatsApp → Standard format
- Gmail → Standard format

### Life Analytics
Analyze communication patterns:
- Frequency over time
- Key relationships
- Activity patterns

## Technical Considerations

### Privacy & Security
- All processing local
- No cloud upload
- OAuth for Google APIs only
- Credentials never committed

### Performance
- Streaming JSONL output
- Lazy loading for large datasets
- Pagination support
- Error recovery

### Compatibility
- Python 3.8+
- Platform-specific requirements
- Graceful degradation
- Clear error messages

### Limitations
- WhatsApp encryption challenges
- iMessage database locking
- Google API rate limits
- Varying data availability

## Future Enhancements

Potential additions:
- More platforms (Telegram, Signal, Slack)
- Export to standard formats (mbox, ICS)
- Search interface
- Analytics dashboard
- Incremental updates
- GUI application

## Contributing

Areas for contribution:
- Additional platform support
- Better error handling
- Performance optimizations
- Documentation improvements
- UI/UX enhancements

See `README.md` for contribution guidelines.

## License

MIT License - Free for personal and commercial use

## Acknowledgments

Built with:
- Python
- Google APIs
- SQLite
- Open-source libraries

Thanks to all contributors!

