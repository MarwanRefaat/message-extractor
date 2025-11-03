# Chat Database - Documentation

## Overview

You now have a well-structured, normalized SQLite database containing all your chat messages from multiple platforms. The database is designed for efficient querying, analytics, and long-term storage.

## Quick Start

### View the Database

The SQLite database file is `sample_chats.db`. You can explore it using:

```bash
# Interactive SQLite shell
sqlite3 sample_chats.db

# Run a quick query
sqlite3 sample_chats.db "SELECT * FROM platform_summary;"

# View the report
cat database_report.txt
```

### Python Access

```python
import sqlite3

# Connect to database
conn = sqlite3.connect('sample_chats.db')
conn.row_factory = sqlite3.Row  # Dict-like access

# Run queries
cursor = conn.execute("SELECT * FROM recent_conversations LIMIT 10")
for row in cursor:
    print(dict(row))

# Close connection
conn.close()
```

## Database Schema

### Core Tables

1. **contacts** - All unique contacts across platforms
   - Primary keys: email, phone, platform_id
   - Tracks: name, messages, first/last seen dates

2. **conversations** - Groups messages into threads
   - Tracks: participants, message counts, group vs. individual
   - Auto-updates: timestamps, participant counts

3. **messages** - All individual messages
   - Links: to conversation, sender, optional reply-to
   - Content: body, subject, timestamps
   - Metadata: read status, attachments, tapbacks

4. **conversation_participants** - Many-to-many contact-conversation mapping
   - Roles: member, admin, creator
   - Stats: per-contact message counts

5. **calendar_events** - Calendar-specific data (for GCal imports)
   - Events: start, end, location, status
   - Recurrence: patterns, durations

6. **message_tags** - User-defined categorization
   - Custom tags for organizing messages

### Views

Pre-built views for common queries:

- **recent_conversations** - Most recent chats with participants
- **contact_statistics** - Message counts per contact
- **platform_summary** - High-level stats by platform

### Triggers

Automatic updates via triggers:

- **update_conversation_timestamps** - Updates last_message_at on new message
- **update_contact_stats** - Tracks first/last seen per contact
- **detect_group_conversation** - Auto-detects groups (>2 participants)

## Example Queries

### Find Most Active Conversations

```sql
SELECT 
    conversation_name,
    message_count,
    last_message_at,
    participant_names
FROM recent_conversations
ORDER BY message_count DESC
LIMIT 20;
```

### Search Messages by Content

```sql
SELECT 
    m.timestamp,
    c.display_name,
    SUBSTR(m.body, 1, 100) AS preview,
    m.platform
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
WHERE m.body LIKE '%keyword%'
ORDER BY m.timestamp DESC
LIMIT 50;
```

### Get Messages with a Specific Contact

```sql
SELECT 
    m.timestamp,
    m.body,
    m.is_sent,
    c.display_name
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
WHERE c.phone = '+1234567890'
ORDER BY m.timestamp DESC;
```

### Platform Breakdown

```sql
SELECT * FROM platform_summary;
```

### Time-Based Analysis

```sql
-- Messages per day
SELECT 
    DATE(timestamp) AS date,
    COUNT(*) AS message_count,
    COUNT(DISTINCT conversation_id) AS conversations
FROM messages
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 30;
```

### Find Group Chats

```sql
SELECT 
    conversation_name,
    participant_count,
    message_count,
    participant_names
FROM conversations
WHERE is_group = 1
ORDER BY message_count DESC;
```

### Tapback Analysis

```sql
SELECT 
    tapback_type,
    COUNT(*) AS count
FROM messages
WHERE is_tapback = 1
GROUP BY tapback_type
ORDER BY count DESC;
```

## Data Import

### Re-import All Data

To re-run the import process:

```bash
python3 create_chat_database.py --export-dir IMESSAGE_EXPORT_TEMP --db-path sample_chats.db
```

This will:
1. Remove existing database (fresh start)
2. Parse all HTML exports
3. Extract messages using LLM
4. Import to database
5. Generate report

### Import from Unified Ledger

If you have a unified ledger JSON file:

```bash
python3 create_chat_database.py \
    --export-dir IMESSAGE_EXPORT_TEMP \
    --db-path sample_chats.db \
    --ledger output/unified/unified_ledger.json
```

## Database Statistics

As of the most recent import:

- **Total Messages**: 817
- **Total Conversations**: 187
- **Total Contacts**: 202
- **Platform**: iMessage

## Performance

### Indexes

The database includes optimized indexes for:

- Timestamp-based queries
- Conversation lookups
- Sender searches
- Platform filtering
- Full-text search capabilities

### Optimizations

- Composite indexes on frequently queried column combinations
- Trigger-based auto-updates (no manual aggregation needed)
- Normalized design (minimal duplication)

## Data Quality

### Validation

All messages:
- Have non-empty bodies
- Include valid timestamps
- Reference valid conversations and contacts
- Follow platform-specific formatting

### Common Issues

If you see data quality issues:

1. **Empty conversations** - Some HTML files had no extractable messages
2. **Duplicate contacts** - Fixed with UNIQUE constraints and INSERT OR IGNORE
3. **Missing metadata** - Some fields may be NULL for older exports

## Future Enhancements

### Planned Features

- [ ] WhatsApp import support
- [ ] Gmail threading
- [ ] Calendar event correlation
- [ ] Full-text search index (FTS5)
- [ ] Export to CSV/JSON
- [ ] Query builder GUI

### LLM Integration

The system can use GPT4All for:
- Message extraction from HTML
- Text normalization
- Sentiment analysis
- Smart categorization

Enable with: `pip install gpt4all`

## Backup

### Creating Backups

```bash
# Simple copy
cp sample_chats.db sample_chats.db.backup

# Compressed backup
sqlite3 sample_chats.db ".backup 'sample_chats.backup.db'"
gzip sample_chats.backup.db
```

### Restore from Backup

```bash
gunzip -c sample_chats.backup.db.gz > sample_chats.db
```

## Privacy & Security

- All data stored locally
- No external connections required
- No API keys needed
- LLM runs entirely offline
- SQLite file encryption available if needed

## Troubleshooting

### Database Locked

```bash
# Check for running processes
lsof sample_chats.db

# Kill if needed
kill <PID>
```

### Corrupted Database

```bash
# Check integrity
sqlite3 sample_chats.db "PRAGMA integrity_check;"

# Recover if needed
sqlite3 sample_chats.db ".recover" | sqlite3 recovered.db
```

### Out of Memory

For very large datasets (>1M messages):

1. Process in batches
2. Use WAL mode: `PRAGMA journal_mode=WAL;`
3. Increase cache: `PRAGMA cache_size=-16000;` (16GB)

## Resources

- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Schema Documentation](./SQL_SCHEMA.md)
- [LLM Extraction Guide](./LLM_EXTRACTION.md)
- [JSON Schema Reference](./JSON_SCHEMA.md)

## Support

For issues or questions:

1. Check this documentation
2. Review the schema docs
3. Inspect `database_report.txt`
4. Run integrity check

## License

Part of the message-extractor project. See main README for license details.

