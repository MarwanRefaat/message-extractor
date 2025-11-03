# Supabase Upload Guide 🚀

Complete guide for uploading the message-extractor database to Supabase.

## Overview

This guide walks you through uploading your local SQLite database to Supabase (PostgreSQL), including:
- ✅ Schema creation with all tables, indexes, triggers, and views
- ✅ Complete data migration with referential integrity
- ✅ Comprehensive testing and verification
- ✅ Production-ready database setup

## Prerequisites

1. **Supabase Account**
   - Sign up at https://supabase.com
   - **Note**: If you see a Vercel integration dialog:
     - Click **"Visit Vercel to create a project"**
     - Create a new project on Vercel named: **`message-extractor`**
     - Return to Supabase and continue with project creation
   - Create a new project (name it `message-extractor`)
   - Note your project reference ID and database password

2. **Python Dependencies**
   ```bash
   pip install psycopg2-binary
   ```

3. **Local Database**
   - Ensure `data/database/chats.db` exists with your data

## Quick Start

### Option 1: Automated Upload (Recommended)

```bash
# Using project reference and password
python scripts/upload_to_supabase.py \
  --project-ref YOUR_PROJECT_REF \
  --password YOUR_DATABASE_PASSWORD

# Or using full connection string
python scripts/upload_to_supabase.py \
  --connection-string "postgresql://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"
```

### Option 2: Manual Setup via Supabase Dashboard

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor**
3. Open `data/database/supabase_migration.sql`
4. Copy the entire file contents
5. Paste into SQL Editor and click **Run**

Then run the data migration:

```bash
python scripts/upload_to_supabase.py \
  --project-ref YOUR_PROJECT_REF \
  --password YOUR_DATABASE_PASSWORD \
  --skip-schema  # Schema already created
```

## Finding Your Connection Details

### Project Reference
1. Go to Supabase Dashboard → Settings → General
2. Find **Reference ID** (e.g., `xyzabc123`)

### Database Password
1. Go to Settings → Database
2. Under **Connection string**, click **Show password**
3. Copy the password

### Connection String Format
```
postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

## Script Options

```bash
python scripts/upload_to_supabase.py --help
```

### Required Arguments
- `--connection-string` OR `--project-ref`: Connection details
- If using `--project-ref`, also provide `--password`

### Optional Arguments
- `--sqlite-db PATH`: Path to SQLite database (default: `data/database/chats.db`)
- `--migration-sql PATH`: Path to migration SQL file
- `--batch-size N`: Batch size for inserts (default: 100)
- `--skip-schema`: Skip schema creation (use if already created)
- `--skip-verification`: Skip verification steps

## What Gets Uploaded

### Schema Components
- ✅ 6 core tables (contacts, conversations, messages, etc.)
- ✅ All indexes for optimal performance
- ✅ Triggers for automatic data maintenance
- ✅ Views for common queries
- ✅ Foreign key constraints for integrity

### Data
- ✅ All contacts (202+ expected)
- ✅ All conversations (187+ expected)
- ✅ All messages (817+ expected)
- ✅ All conversation participants (454+ expected)
- ✅ Calendar events (if any)
- ✅ Message tags (if any)

## Verification

The script automatically verifies:
1. **Schema**: Checks all tables exist
2. **Data Counts**: Compares SQLite vs Supabase row counts
3. **Test Queries**: Runs sample queries to ensure functionality
4. **Views**: Tests all pre-computed views

## Database Schema

### Core Tables

1. **contacts**
   - All unique contacts across platforms
   - Unique constraint: (platform, platform_id)
   - Auto-tracks statistics (first_seen, last_seen, message_count)

2. **conversations**
   - Message threads/conversations
   - Supports 1-on-1 and group chats
   - Auto-updates message counts and timestamps

3. **messages**
   - All messages from all platforms
   - Supports replies, attachments, raw_data (JSONB)
   - Comprehensive indexing

4. **conversation_participants**
   - Many-to-many relationship
   - Tracks who's in each conversation

5. **calendar_events**
   - Calendar-specific event data
   - Linked to messages

6. **message_tags**
   - Custom categorization tags

### Views

- **recent_conversations**: Most active conversations with participants
- **contact_statistics**: Per-contact messaging stats
- **platform_summary**: High-level stats per platform

## Example Queries

Once uploaded, you can query your data:

```sql
-- Recent conversations
SELECT * FROM recent_conversations LIMIT 10;

-- Contact statistics
SELECT * FROM contact_statistics ORDER BY total_messages DESC LIMIT 20;

-- Platform summary
SELECT * FROM platform_summary;

-- Messages with contact info
SELECT 
    m.timestamp,
    m.body,
    c.display_name,
    conv.conversation_name
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
JOIN conversations conv ON m.conversation_id = conv.conversation_id
ORDER BY m.timestamp DESC
LIMIT 50;
```

## Troubleshooting

### Connection Errors

**Error: Connection refused**
- Check your IP isn't blocked in Supabase Settings → Database → Connection Pooling
- Verify project reference ID is correct
- Ensure database password is correct

**Error: Authentication failed**
- Double-check database password
- Try resetting password in Supabase dashboard

### Migration Errors

**Error: Relation already exists**
- Tables already exist - use `--skip-schema` flag
- Or drop tables first (be careful!)

**Error: Foreign key constraint violation**
- Data migration order issue - run full script again
- Check that contacts/conversations exist before messages

**Error: Duplicate key violation**
- Data already migrated - script uses `ON CONFLICT DO NOTHING`
- Safe to re-run

### Performance Issues

**Slow migration**
- Reduce batch size: `--batch-size 50`
- Check Supabase project isn't paused (free tier pauses after inactivity)

**Timeout errors**
- Increase batch size: `--batch-size 200`
- Migrate in chunks (modify script for large datasets)

## Environment Variables

You can use environment variables instead of command-line args:

```bash
export SUPABASE_CONNECTION="postgresql://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"
python scripts/upload_to_supabase.py --connection-string "$SUPABASE_CONNECTION"
```

Or:

```bash
export SUPABASE_PROJECT_REF="xyzabc123"
export SUPABASE_PASSWORD="your_password"
python scripts/upload_to_supabase.py --project-ref "$SUPABASE_PROJECT_REF" --password "$SUPABASE_PASSWORD"
```

## Post-Upload Steps

1. **Verify Data**
   ```bash
   # The script does this automatically, but you can verify manually:
   psql "postgresql://..." -c "SELECT COUNT(*) FROM messages;"
   ```

2. **Set Up API Access (Optional)**
   - Go to Supabase Dashboard → API
   - Note your API keys and URL
   - Use REST API or PostgREST for programmatic access

3. **Enable Row Level Security (Optional)**
   - If you want user-based access control
   - See `data/database/supabase_migration.sql` for RLS setup

4. **Backup Strategy**
   - Supabase provides automatic backups
   - Consider setting up custom backup schedule
   - Export data periodically for extra safety

## Database Naming Convention

- **Project Name**: `message-extractor` (with dash, for display)
- **Database Name**: `message_extractor` (with underscore, SQL convention)
- **Tables**: Use underscores (e.g., `conversation_participants`)

## Best Practices

1. **Always verify** after migration
2. **Keep SQLite backup** until you're confident in Supabase
3. **Monitor usage** in Supabase dashboard (free tier has limits)
4. **Use indexes** - all common queries are indexed
5. **Test queries** before building applications

## Support

- **Documentation**: See `docs/SUPABASE_SETUP.md` for detailed setup
- **Schema Details**: See `data/database/schema_diagram.md`
- **Migration SQL**: See `data/database/supabase_migration.sql`

## Next Steps

After successful upload:
- ✅ Test queries using Supabase SQL Editor
- ✅ Explore data using views (recent_conversations, etc.)
- ✅ Set up API access if needed
- ✅ Build applications on top of your database!

---

**Project**: message_extractor  
**Email**: marwan@marwanrefaat.com  
**Database**: PostgreSQL (Supabase)  
**Status**: Production-ready ✨

