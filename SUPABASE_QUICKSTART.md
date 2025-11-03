# Supabase Quick Start 🚀

Get your message-extractor database set up in Supabase in 5 minutes!

## Quick Setup

1. **Create Supabase Project**
   - Go to https://supabase.com/dashboard
   - Click "New Project"
   - Name: `message-extractor`
   - Email: `marwan@marwanrefaat.com`
   - Set a strong database password (save it!)

2. **Run Migration**
   - Open **SQL Editor** in Supabase dashboard
   - Click "New Query"
   - Copy entire `data/database/supabase_migration.sql` file
   - Paste and click "Run"

3. **Verify**
   ```sql
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public' 
   ORDER BY table_name;
   ```
   Should show 6 tables: contacts, conversations, messages, conversation_participants, calendar_events, message_tags

## What You Get

✅ 6 core tables with relationships  
✅ Automatic triggers for statistics  
✅ 3 helpful views for queries  
✅ Full indexes for performance  
✅ PostgreSQL 15+ compatible  

## Database Schema

```
contacts (1) ──┐
               ├──> messages (N)
conversations (1) ──┘

messages (1) ──> calendar_events (0..1)
messages (1) ──> message_tags (N)

conversations (M) <──> contacts (M) via conversation_participants
```

## Connection String

After setup, get your connection string from:
**Settings → Database → Connection string**

Format:
```
postgresql://postgres:[PASSWORD]@db.[project-ref].supabase.co:5432/postgres
```

## Full Documentation

See [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md) for detailed instructions, troubleshooting, and advanced configuration.

## Next Steps

1. Import your data using your existing import scripts
2. Query your data using the views:
   - `SELECT * FROM platform_summary;`
   - `SELECT * FROM recent_conversations LIMIT 20;`
   - `SELECT * FROM contact_statistics ORDER BY total_messages DESC LIMIT 10;`

## Support

- Migration script: `data/database/supabase_migration.sql`
- Full guide: `docs/SUPABASE_SETUP.md`
- Schema docs: `data/database/schema_diagram.md`

