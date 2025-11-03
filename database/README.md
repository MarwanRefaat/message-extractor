# Database Workspace 🗄️

Unified SQLite database containing all your messages from iMessage, WhatsApp, Gmail, and Google Calendar.

## Quick Access

```bash
# Open in DB Browser (visual interface)
open database/chats.db

# Query via command line
sqlite3 database/chats.db

# Quick stats
sqlite3 database/chats.db "SELECT * FROM platform_summary;"
```

## Current Statistics

**Total Messages**: 7,448
- WhatsApp: 6,631 messages
- iMessage: 817 messages

**Total Conversations**: 1,029
- WhatsApp: 842 conversations
- iMessage: 187 conversations

**Total Contacts**: 743
- WhatsApp: 706 contacts
- iMessage: 37 contacts

## Schema Overview

### Core Tables
1. **contacts** - All unique contacts across platforms
2. **conversations** - Message threads with metadata
3. **messages** - Individual messages with content
4. **conversation_participants** - Many-to-many relationships
5. **calendar_events** - Calendar-specific data
6. **message_tags** - Custom categorization

### Views
- **recent_conversations** - Most active chats
- **contact_statistics** - Per-contact analytics
- **platform_summary** - High-level stats per platform

See `database/database_erd.md` for complete ERD diagram.

## Import System

### Standard Import
```bash
# WhatsApp import
python3 import_whatsapp_to_database.py --db database/chats.db

# Or use robust import with checkpoints
python3 scripts/robust_import.py --db database/chats.db --batch-size 50
```

### Robust Import Features
✅ **Checkpoints** - Saves progress every N records  
✅ **Resume capability** - Picks up where it left off  
✅ **LLM fallback** - Graceful degradation if LLM fails  
✅ **Batch processing** - Small chunks for efficiency  
✅ **Better logging** - Detailed logs in `logs/` directory  

### With Supabase Upload
```bash
# Set credentials
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"

# Import with real-time upload
python3 scripts/robust_import.py --supabase --batch-size 100
```

## Query Examples

### Platform Summary
```sql
SELECT * FROM platform_summary;
```

### Top Conversations
```sql
SELECT * FROM recent_conversations 
ORDER BY message_count DESC 
LIMIT 20;
```

### Search Messages
```sql
SELECT conversation_name, body, timestamp 
FROM messages m
JOIN conversations c ON m.conversation_id = c.conversation_id
WHERE body LIKE '%keyword%'
ORDER BY timestamp DESC;
```

### Cross-Platform Contact
```sql
SELECT DISTINCT c.conversation_name, c.platform, c.message_count
FROM conversations c
JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
JOIN contacts ct ON cp.contact_id = ct.contact_id
WHERE ct.phone = '+1234567890'
ORDER BY c.last_message_at DESC;
```

## Supabase Migration

Ready to migrate to cloud? Use the migration script:

```bash
# Apply to Supabase
psql -U postgres -d your_database < database/supabase_migration.sql
```

See `database/supabase_migration.sql` for complete PostgreSQL schema.

## File Structure

```
database/
├── chats.db           # Main SQLite database (12 MB)
├── README.md          # This file
├── database_erd.md    # Mermaid visual ERD
└── .gitignore        # Ignore personal data
```

## Documentation

- **Schema**: See `database/database_erd.md` for complete ERD
- **Migration**: See `database/supabase_migration.sql` for PostgreSQL
- **Import**: See `scripts/robust_import.py` for checkpoint system
- **Logs**: Check `logs/` directory for import logs

