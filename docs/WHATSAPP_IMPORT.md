# WhatsApp Import Guide

This guide explains how to import WhatsApp messages into the existing chat database using the WhatsApp Chat Exporter.

## Overview

The import process uses the [WhatsApp Chat Exporter](https://github.com/KnugiHK/Whatsapp-Chat-Exporter) library to parse WhatsApp data and then imports it into the unified database structure.

## Prerequisites

1. **WhatsApp Database Files**: You need access to your WhatsApp database
   - **Android**: `msgstore.db` and optionally `wa.db` (contacts)
   - **iOS**: Message database from iOS backup

2. **Python Dependencies**: Install WhatsApp Chat Exporter
   ```bash
   pip install whatsapp-chat-exporter
   ```

## Importing WhatsApp Messages

### For Android Users

1. Extract your WhatsApp backup from your Android device
2. Locate the following files:
   - `msgstore.db` - Contains all messages
   - `wa.db` - Contains contacts (optional)

3. Run the import:
   ```bash
   python3 import_whatsapp_to_database.py \
     --android \
     --db chats.db \
     --msg-db /path/to/msgstore.db \
     --contacts-db /path/to/wa.db \
     --media /path/to/WhatsApp
   ```

### For iOS Users

1. Extract your iOS backup using iTunes or Finder
2. Locate the WhatsApp databases in your backup
3. Run the import:
   ```bash
   python3 import_whatsapp_to_database.py \
     --ios \
     --db chats.db \
     --msg-db /path/to/message.db \
     --contacts-db /path/to/ContactsV2.sqlite \
     --media /path/to/WhatsApp/Media
   ```

## Command Line Options

| Option | Description | Required |
|--------|-------------|----------|
| `--db` | Path to SQLite database | No (default: chats.db) |
| `--msg-db` | Path to WhatsApp message database | Yes |
| `--contacts-db` | Path to contacts database | No |
| `--media` | Path to WhatsApp media folder | No |
| `--ios` | Use iOS database format | If not Android |
| `--android` | Use Android database format | If not iOS |

## How It Works

1. **Parsing**: The script uses WhatsApp Chat Exporter to parse your WhatsApp databases
   - Extracts conversations
   - Extracts messages with timestamps
   - Extracts media references
   - Extracts contact information

2. **Import**: Data is imported into the unified database structure
   - Creates or updates contacts
   - Creates conversations
   - Imports messages
   - Links participants to conversations

3. **Normalization**: The database automatically:
   - Links duplicate contacts across platforms
   - Updates conversation statistics
   - Maintains referential integrity

## Database Structure

WhatsApp messages are imported into the same structure as iMessage:

### Contacts Table
- Stores all WhatsApp contacts
- Links to iMessage contacts if phone numbers match
- Platform: `whatsapp`
- Platform IDs: WhatsApp JIDs (e.g., `+1234567890@s.whatsapp.net`)

### Conversations Table
- One row per chat/group
- Links participants
- Platform: `whatsapp`
- Supports both individual and group chats

### Messages Table
- All WhatsApp messages
- Includes timestamps, senders, recipients
- Preserves media references
- Raw data stored in JSON

## Querying WhatsApp Data

### All WhatsApp Messages
```sql
SELECT * FROM messages WHERE platform = 'whatsapp';
```

### Conversations with WhatsApp Messages
```sql
SELECT * FROM conversations WHERE platform = 'whatsapp';
```

### Unread WhatsApp Messages
```sql
SELECT COUNT(*) FROM messages 
WHERE platform = 'whatsapp' AND is_read = 0;
```

### Cross-Platform Contact Lookup
Find all conversations with a specific phone number across platforms:
```sql
SELECT DISTINCT c.conversation_name, c.platform, c.message_count
FROM conversations c
JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
JOIN contacts ct ON cp.contact_id = ct.contact_id
WHERE ct.phone = '+1234567890'
ORDER BY c.platform, c.last_message_at DESC;
```

## Troubleshooting

### "Could not determine sender for message"
- Some group messages may not have clear sender information
- The script will skip these messages and log a warning
- Check that your contacts database is properly linked

### "Conversation already exists"
- The import skips duplicate conversations automatically
- This is normal if re-importing
- Check conversation_id to verify it's the same conversation

### "Database lock errors"
- Close any applications using the database
- Wait for previous imports to complete
- Check file permissions

## Example Output

After import, you should see:
```
Connecting to database: chats.db
Starting WhatsApp import...
Processing 25 conversations
Progress: 10/25 conversations
Progress: 20/25 conversations
WhatsApp import complete!
Database connection closed
```

Check your database:
```bash
sqlite3 chats.db "SELECT platform, COUNT(*) FROM messages GROUP BY platform;"
```

Should show:
```
imessage  817
whatsapp  1234
```

## Next Steps

1. Generate a report:
   ```bash
   python3 create_chat_database.py --generate-report
   ```

2. Query your data:
   ```bash
   sqlite3 chats.db
   ```

3. Export to JSON if needed:
   ```bash
   python3 export_database.py --format json --output combined_chats.json
   ```

## Notes

- WhatsApp timestamps are converted to UTC
- Media files are not copied, only references are stored
- Group chat participants are extracted when available
- Deleted messages may or may not be included depending on database state
- Call logs are not currently imported

## Support

For issues with:
- **WhatsApp parsing**: See [WhatsApp Chat Exporter documentation](https://github.com/KnugiHK/Whatsapp-Chat-Exporter)
- **Database issues**: Check SQLite documentation
- **Import errors**: Check logs for specific error messages

