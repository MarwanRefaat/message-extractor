# Calendar Events Upload Instructions

## What Was Done ✅

1. **Created importer script**: `scripts/import_googletakeout_calendar.py`
   - Imports Google Takeout calendar events from `data/raw/googletakeoutcal_raw.jsonl`
   - Filters for events where you are invited (marwan@marwanrefaat.com or marwan@fractalfund.com)
   - Successfully imported **631 calendar events** into SQLite

2. **Updated Supabase schema**: `data/database/supabase_migration.sql`
   - Added missing columns to `calendar_events` table
   - Added `updated_at` trigger for calendar_events

3. **Updated upload script**: `scripts/upload_to_supabase.py`
   - Now handles all calendar event columns

## Next Steps: Upload to Supabase

### Step 1: Update Supabase Schema

Since your Supabase project may already exist with the old schema, you need to add the missing columns.

**Option A: Via Supabase Dashboard (Recommended)**

1. Go to your Supabase project: https://supabase.com/dashboard
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `ALIGN_CALENDAR_SCHEMA.sql`
4. Click **Run**

**Option B: If Starting Fresh**

Run the entire updated schema:

1. Go to **SQL Editor**
2. Copy and paste the entire contents of `data/database/supabase_migration.sql`
3. Click **Run** (this will recreate tables with the new schema)

### Step 2: Upload Data

Run the upload script with your Supabase credentials:

```bash
# Option 1: Using project reference and password
python scripts/upload_to_supabase.py \
  --project-ref YOUR_PROJECT_REF \
  --password YOUR_DATABASE_PASSWORD

# Option 2: Using connection string
python scripts/upload_to_supabase.py \
  --connection-string "postgresql://postgres:PASSWORD@db.REF.supabase.co:5432/postgres"
```

### Getting Your Credentials

If you don't have them yet:

1. **Project Reference ID**:
   - Go to Supabase Dashboard → Settings → General
   - Copy the "Reference ID" (e.g., `xyzabc123`)

2. **Database Password**:
   - Go to Settings → Database
   - Click "Show password" to reveal it

3. **Connection String** (Alternative):
   - Go to Settings → Database
   - Under "Connection string", select "URI"
   - Copy the connection string

### What Will Be Uploaded

The script will upload:
- ✅ All 631 calendar events from SQLite
- ✅ All contact records
- ✅ All conversation records  
- ✅ All message records
- ✅ All conversation participants
- ✅ Message tags (if any)

### Verification

After upload, verify in Supabase Table Editor:

```sql
-- Count calendar events
SELECT COUNT(*) FROM calendar_events;

-- Should return: 631

-- View sample calendar events with locations
SELECT 
    event_start,
    event_location,
    event_duration_seconds
FROM calendar_events
WHERE event_location IS NOT NULL AND event_location != ''
ORDER BY event_start DESC
LIMIT 10;
```

## Troubleshooting

### "Column does not exist" Error

This means the Supabase schema wasn't updated. Make sure you ran either:
- The contents of `ALIGN_CALENDAR_SCHEMA.sql` in SQL Editor, OR
- The entire `data/database/supabase_migration.sql` if starting fresh

### Connection Errors

- Verify your project reference ID is correct
- Check your database password is correct
- Make sure your IP isn't blocked (Settings → Database → Connection Pooling)

### Data Count Mismatch

The upload script includes conflict handling (`ON CONFLICT DO NOTHING`), so:
- If you run it multiple times, duplicates are skipped
- Counts should match between SQLite and Supabase after first successful upload

## Files Reference

- **Local SQLite Database**: `data/database/chats.db` (631 calendar events imported)
- **Import Script**: `scripts/import_googletakeout_calendar.py`
- **Supabase Schema**: `data/database/supabase_migration.sql` (updated)
- **Upload Script**: `scripts/upload_to_supabase.py` (updated)
- **Schema Update SQL**: `ALIGN_CALENDAR_SCHEMA.sql` (for existing databases)

