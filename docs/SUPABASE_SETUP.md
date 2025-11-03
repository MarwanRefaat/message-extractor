# Supabase Setup Guide

This guide will help you set up the message-extractor database in Supabase.

## Prerequisites

1. A Supabase account (sign up at https://supabase.com)
2. Your email: **marwan@marwanrefaat.com**

## Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click **"New Project"**
3. Fill in the project details:
   - **Project Name**: `message-extractor`
   - **Database Password**: Choose a strong password (save this!)
   - **Region**: Choose the closest region to you
   - **Organization**: Select your organization or create one
4. Click **"Create new project"**
5. Wait 2-3 minutes for the project to be provisioned

## Step 2: Access Database

1. Once the project is ready, go to **Settings** → **Database**
2. Note your connection details:
   - **Host**: `db.[project-ref].supabase.co`
   - **Port**: `5432`
   - **Database**: `postgres`
   - **User**: `postgres`
   - **Password**: The password you set during project creation

## Step 3: Run Migration Script

You have two options to run the migration:

### Option A: Using Supabase SQL Editor (Recommended)

1. In your Supabase dashboard, go to **SQL Editor**
2. Click **"New Query"**
3. Copy the entire contents of `data/database/supabase_migration.sql`
4. Paste it into the SQL editor
5. Click **"Run"** (or press `Ctrl+Enter` / `Cmd+Enter`)
6. Wait for the script to complete (should take a few seconds)

### Option B: Using psql Command Line

1. Install PostgreSQL client tools (if not already installed):
   ```bash
   # macOS
   brew install postgresql

   # Or download from https://www.postgresql.org/download/
   ```

2. Connect to your Supabase database:
   ```bash
   psql "postgresql://postgres:[YOUR-PASSWORD]@db.[project-ref].supabase.co:5432/postgres"
   ```

3. Run the migration:
   ```bash
   \i data/database/supabase_migration.sql
   ```

   Or copy-paste the contents directly into the psql session.

## Step 4: Verify Installation

Run these queries in the SQL Editor to verify everything is set up correctly:

```sql
-- Check tables were created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Should return:
-- calendar_events
-- contacts
-- conversation_participants
-- conversations
-- message_tags
-- messages

-- Check views were created
SELECT table_name 
FROM information_schema.views 
WHERE table_schema = 'public'
ORDER BY table_name;

-- Should return:
-- contact_statistics
-- platform_summary
-- recent_conversations

-- Test the schema
SELECT * FROM platform_summary;
```

## Step 5: Get Connection String

For use in your application, get the connection string:

1. Go to **Settings** → **Database**
2. Scroll down to **"Connection string"**
3. Select **"URI"** or **"Connection pooling"**
4. Copy the connection string
   - Format: `postgresql://postgres:[YOUR-PASSWORD]@db.[project-ref].supabase.co:5432/postgres`
   - For connection pooling: `postgresql://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres`

## Database Schema

The database includes:

### Core Tables
- **contacts** - All unique contacts across platforms
- **conversations** - Message threads with metadata
- **messages** - Individual messages with content
- **conversation_participants** - Many-to-many relationships
- **calendar_events** - Calendar-specific data
- **message_tags** - Custom categorization

### Views
- **recent_conversations** - Most active chats sorted by last message
- **contact_statistics** - Per-contact analytics
- **platform_summary** - High-level stats per platform

### Features
- ✅ Automatic timestamp updates via triggers
- ✅ Message count aggregation
- ✅ Contact statistics tracking
- ✅ Group conversation detection
- ✅ Full-text search support (via GIN indexes on JSONB)
- ✅ Referential integrity with foreign keys

## Security (Optional)

If you want to add Row Level Security (RLS) for multi-user access:

1. Uncomment the RLS sections in the migration script
2. Create policies based on your authentication needs
3. See Supabase docs for RLS best practices

## Next Steps

1. **Import your data**: Use the migration script or import tools to populate the database
2. **Connect your app**: Use the connection string in your application code
3. **Set up API access**: Consider using Supabase REST API or PostgREST for easier access

## Troubleshooting

### Connection Issues
- Verify your password is correct
- Check that your IP isn't blocked (go to **Settings** → **Database** → **Connection Pooling**)
- Ensure you're using the correct port (5432 for direct, 6543 for pooling)

### Migration Errors
- Make sure you're running the script as the `postgres` superuser
- Check that no tables with the same names already exist
- Verify all extensions are available (uuid-ossp is pre-installed in Supabase)

### Performance
- For large datasets, consider using connection pooling
- Enable pg_stat_statements for query analysis
- Monitor your database usage in the Supabase dashboard

## Support

- Supabase Docs: https://supabase.com/docs
- Supabase Discord: https://discord.supabase.com
- Project Issues: Check the repository issues

## Migration Script Location

The complete migration script is located at:
```
data/database/supabase_migration.sql
```

