# Chat Database 📊

Unified SQLite database containing all your messages from iMessage, WhatsApp, Gmail, and Google Calendar.

## Quick Start

```bash
# Open with DB Browser for SQLite (recommended)
open database/chats.db

# Or use command line
sqlite3 database/chats.db

# Query examples
sqlite3 database/chats.db "SELECT * FROM platform_summary;"
```

## Database Statistics

- **Total Messages**: 817
- **Total Conversations**: 187
- **Total Contacts**: 202
- **Platform**: iMessage (WhatsApp support added)
- **Size**: 7.3 MB

## Schema Overview

The database uses a normalized relational structure with 6 core tables:

### Core Tables

1. **contacts** - All unique contacts across platforms
2. **conversations** - Message threads with metadata
3. **messages** - Individual messages with content
4. **conversation_participants** - Many-to-many relationships
5. **calendar_events** - Calendar-specific data
6. **message_tags** - Custom categorization

### Views

- **recent_conversations** - Most active chats sorted by last message
- **contact_statistics** - Per-contact analytics and messaging stats
- **platform_summary** - High-level stats per platform

See [docs/SQL_SCHEMA.md](../docs/SQL_SCHEMA.md) for complete schema documentation.

## Usage Examples

### View platform summary
```sql
SELECT * FROM platform_summary;
```

### Top 20 conversations
```sql
SELECT * FROM recent_conversations 
ORDER BY message_count DESC 
LIMIT 20;
```

### Search messages
```sql
SELECT * FROM messages 
WHERE body LIKE '%keyword%' 
ORDER BY timestamp DESC;
```

### Contact statistics
```sql
SELECT * FROM contact_statistics 
ORDER BY total_messages DESC 
LIMIT 20;
```

### Cross-platform contact lookup
```sql
SELECT DISTINCT c.conversation_name, c.platform, c.message_count
FROM conversations c
JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
JOIN contacts ct ON cp.contact_id = ct.contact_id
WHERE ct.phone = '+1234567890'
ORDER BY c.last_message_at DESC;
```

## Installation & Setup

### Recommended: DB Browser for SQLite

Install via Homebrew:
```bash
brew install --cask db-browser-for-sqlite
```

Or download from: https://sqlitebrowser.org/

### Alternative: Command Line

```bash
sqlite3 database/chats.db
```

### Web-based: sql.js

For browser-based viewing:
```bash
# Install
npm install -g sql.js

# View in browser
open database/chats.db
```

## Importing WhatsApp

```bash
python3 import_whatsapp_to_database.py \
  --android \
  --db database/chats.db \
  --msg-db /path/to/msgstore.db
```

See [docs/WHATSAPP_IMPORT.md](../docs/WHATSAPP_IMPORT.md) for details.

## Supabase Compatibility

This SQLite schema is designed to be compatible with Supabase (PostgreSQL):

### Migration Notes

- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `TEXT` → `TEXT` (same)
- `TIMESTAMP` → `TIMESTAMPTZ` (timezone-aware)
- `JSON` → `JSONB`
- `BOOLEAN` → `BOOLEAN` (same)

See [database/supabase_migration.sql](supabase_migration.sql) for PostgreSQL schema.

## Database Maintenance

### Backup
```bash
cp database/chats.db database/chats.db.backup
```

### Vacuum (optimize)
```sql
VACUUM;
```

### Analyze (update statistics)
```sql
ANALYZE;
```

### Generate Report
```bash
python3 create_chat_database.py --generate-report
```

## File Structure

```
database/
├── chats.db              # Main SQLite database
├── README.md             # This file
├── schema_diagram.svg    # Visual schema diagram
└── supabase_migration.sql # PostgreSQL migration script
```

## Documentation

- **Schema**: [docs/SQL_SCHEMA.md](../docs/SQL_SCHEMA.md)
- **Database Guide**: [docs/DATABASE_README.md](../docs/DATABASE_README.md)
- **WhatsApp Import**: [docs/WHATSAPP_IMPORT.md](../docs/WHATSAPP_IMPORT.md)
- **Summary**: [CHAT_DATABASE_SUMMARY.md](../CHAT_DATABASE_SUMMARY.md)

## License

MIT License - Use freely!

