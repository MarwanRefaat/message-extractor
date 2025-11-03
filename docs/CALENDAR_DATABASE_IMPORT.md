# Calendar Events Database Import

## Overview

The calendar extraction system intelligently filters and imports calendar events into the SQLite database. It:

- ✅ Filters for events where you were invited (by email or phone)
- ✅ Excludes generic holidays automatically
- ✅ Uses LLM-based intelligent filtering (optional)
- ✅ Stores events in both `messages` and `calendar_events` tables
- ✅ Includes rich metadata (location, video links, recurrence, etc.)

## Quick Start

### 1. Ensure Database Schema is Up to Date

```bash
# Migrate existing database to add new calendar columns
python3 scripts/migrate_calendar_schema.py --db-path data/database/chats.db
```

### 2. Extract and Import Calendar Events

```bash
# Extract calendar events AND import to database
./run.sh --extract-gcal --import-calendar-to-db

# Or with custom database path
./run.sh --extract-gcal --import-calendar-to-db --db-path data/database/chats.db
```

### 3. Standalone Import (if already extracted)

```bash
# Import calendar events directly
python3 scripts/import_calendar_events.py --db-path data/database/chats.db
```

## Configuration

### User Identifiers

The system filters for events where these identifiers appear as attendees/organizers:

- `marwan@marwanrefaat.com`
- `marwan@fractalfund.com`
- Phone: `+1 (424) 777-4242`

To change these, edit `src/extractors/gcal_extractor.py`:
```python
TARGET_EMAILS = ["your@email.com"]
TARGET_PHONE = "+1234567890"
```

### LLM Filtering

By default, the extractor uses LLM-based filtering to:
- Detect and exclude generic holidays
- Clean event descriptions (remove boilerplate)

To disable LLM (use rule-based only):
```bash
python3 scripts/import_calendar_events.py --no-llm
```

## Database Schema

### calendar_events Table

Enhanced schema with fields:

- `event_id` - Primary key
- `message_id` - Foreign key to messages table
- `event_start` / `event_end` - Event timestamps
- `event_duration_seconds` - Calculated duration
- `event_location` - Location string
- `event_status` - confirmed/tentative/cancelled
- `event_timezone` - Timezone information
- `is_recurring` - Boolean flag
- `recurrence_pattern` - Recurrence rules
- `calendar_name` - Source calendar
- `organizer_email` - Event organizer
- `attendee_count` - Number of attendees
- `has_video_conference` - Video meeting flag
- `video_conference_url` - Meeting link (if detected)
- `created_at` / `updated_at` - Timestamps

### Indexes

Optimized indexes for common queries:
- `idx_calendar_events_start` - On event_start DESC
- `idx_calendar_events_status` - On event_status
- `idx_calendar_events_location` - On event_location (where not null)
- `idx_calendar_events_recurring` - On is_recurring (where true)

## Example Queries

```sql
-- Find upcoming events
SELECT ce.event_start, m.subject, ce.event_location, ce.video_conference_url
FROM calendar_events ce
JOIN messages m ON ce.message_id = m.message_id
WHERE ce.event_start > datetime('now')
ORDER BY ce.event_start ASC
LIMIT 10;

-- Events with video conferences
SELECT m.subject, ce.event_start, ce.video_conference_url
FROM calendar_events ce
JOIN messages m ON ce.message_id = m.message_id
WHERE ce.has_video_conference = 1
ORDER BY ce.event_start DESC;

-- Recurring events
SELECT m.subject, ce.recurrence_pattern
FROM calendar_events ce
JOIN messages m ON ce.message_id = m.message_id
WHERE ce.is_recurring = 1;
```

## Testing

```bash
# Test with small sample
python3 scripts/test_calendar_import.py --max-events 5

# Test database schema
python3 scripts/test_calendar_import.py  # (no credentials needed)
```

## Troubleshooting

### "Google Calendar credentials not found"
- Download `credentials.json` from Google Cloud Console
- Place in project root

### "Schema needs to be updated"
```bash
python3 scripts/migrate_calendar_schema.py --db-path data/database/chats.db
```

### "No events found"
- Check that you're invited to events (check attendee list)
- Verify email addresses are correct in `gcal_extractor.py`
- Check date filters (default: 2024 onwards)

### Events missing
- LLM filtering might be too strict - try `--no-llm` flag
- Check logs for filtering decisions
- Verify events include your email in attendees

