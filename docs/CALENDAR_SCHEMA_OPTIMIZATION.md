# Calendar Events Schema Optimization

## Overview

The calendar events schema has been designed for robustness, performance, and elegance. This document describes the optimized schema and design decisions.

## Schema Design Principles

### 1. Normalization
- ✅ Calendar events linked to messages via `message_id` (1:1 relationship)
- ✅ Avoids data duplication
- ✅ Maintains referential integrity

### 2. Rich Metadata
The schema captures:
- **Temporal**: start, end, duration, timezone
- **Location**: physical and virtual (video links)
- **People**: organizer, attendee count
- **Recurrence**: patterns and flags
- **Status**: confirmed, tentative, cancelled
- **Source**: calendar name for multi-calendar support

### 3. Performance Optimizations

#### Indexes
- **Primary queries**: `event_start DESC` for chronological access
- **Status filtering**: `event_status` index
- **Location search**: Partial index on `event_location` (only non-null)
- **Recurring events**: Partial index on `is_recurring = 1`
- **Composite indexes**: 
  - `(event_start, event_status)` for filtered chronological queries
  - `(calendar_name, event_start)` for calendar-specific timelines
  - `organizer_email` for organizer-based queries

#### Views
- **upcoming_calendar_events**: Pre-joined, filtered view of future events
- **calendar_statistics**: Aggregated stats per calendar
- **calendar_events_by_month**: Monthly analytics

### 4. Data Integrity

#### Constraints
- `UNIQUE(message_id)`: One calendar event per message
- Trigger validation: `event_end >= event_start`
- Foreign key to `messages` table
- Default values for safety (status = 'confirmed', counts = 0)

#### Triggers
- Auto-update `updated_at` timestamp
- Validate time ranges
- Cascade consistency

## Schema Structure

```sql
calendar_events (
    event_id                 INTEGER PRIMARY KEY,
    message_id               INTEGER NOT NULL UNIQUE,
    event_start              TIMESTAMP NOT NULL,
    event_end                TIMESTAMP,
    event_duration_seconds   INTEGER,
    event_location           TEXT,
    event_status             TEXT DEFAULT 'confirmed',
    event_timezone           TEXT,
    is_recurring             BOOLEAN DEFAULT 0,
    recurrence_pattern       TEXT,
    calendar_name            TEXT,
    organizer_email          TEXT,
    attendee_count           INTEGER DEFAULT 0,
    has_video_conference     BOOLEAN DEFAULT 0,
    video_conference_url     TEXT,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(message_id) REFERENCES messages(message_id),
    CHECK(event_end >= event_start)  -- via trigger
)
```

## Query Patterns Optimized

### 1. Upcoming Events
```sql
SELECT * FROM upcoming_calendar_events 
WHERE event_start > datetime('now')
ORDER BY event_start ASC;
```
→ Uses `idx_calendar_events_start` index

### 2. Events by Calendar
```sql
SELECT * FROM calendar_events 
WHERE calendar_name = 'Work'
ORDER BY event_start DESC;
```
→ Uses `idx_calendar_events_calendar_start` composite index

### 3. Video Meetings
```sql
SELECT * FROM calendar_events 
WHERE has_video_conference = 1
AND event_start > datetime('now');
```
→ Uses `idx_calendar_events_start` + boolean filter

### 4. Recurring Events
```sql
SELECT * FROM calendar_events 
WHERE is_recurring = 1;
```
→ Uses partial index `idx_calendar_events_recurring`

### 5. Organizer Queries
```sql
SELECT * FROM calendar_events 
WHERE organizer_email = 'someone@example.com'
ORDER BY event_start DESC;
```
→ Uses `idx_calendar_events_organizer` index

## Design Decisions

### Why 1:1 with Messages?
- Calendar events ARE messages (invitations, updates)
- Allows unified querying across all platforms
- Maintains conversation threading
- Enables cross-platform contact linking

### Why Store Duration?
- Calculated field (`event_end - event_start`)
- Stored for performance (no repeated calculations)
- Useful for analytics and filtering

### Why Separate Video Conference Fields?
- `has_video_conference`: Fast boolean filtering
- `video_conference_url`: Actual link (extracted from description)
- Enables quick "show all video meetings" queries

### Why Partial Indexes?
- Reduces index size
- Improves write performance
- Only indexes non-null/true values where queries filter
- SQLite supports partial indexes efficiently

### Why Views?
- Pre-joined common queries
- Simplified access patterns
- Consistent filtering logic
- Performance optimization through query planning

## Migration Path

1. **Initial Schema**: Basic calendar_events table
2. **Enhanced Schema**: Add metadata fields (timezone, calendar_name, etc.)
3. **Optimized Schema**: Add indexes and views
4. **Future Extensions**: Can add event_attendees junction table if needed

## Extensibility

The schema can be extended with:
- `event_attendees` table (many-to-many) if detailed attendee info needed
- `event_reminders` table for reminder tracking
- `event_attachments` table for event files
- `event_categories` or tags for categorization

Current design keeps it simple while allowing future expansion.

## Performance Characteristics

- **Insert**: O(1) with indexes (indexes updated after insert)
- **Select by time**: O(log n) with B-tree index
- **Select by calendar**: O(log n) with composite index
- **Select upcoming**: O(1) with view and index
- **Aggregations**: O(n) but optimized with views

## Best Practices

1. **Always use views** for common queries (they're optimized)
2. **Filter on indexed columns** (event_start, event_status, calendar_name)
3. **Use partial indexes** when filtering nulls
4. **Leverage composite indexes** for multi-column queries
5. **Query through messages table** for cross-platform joins

## Summary

The calendar events schema is:
- ✅ **Normalized**: No data duplication
- ✅ **Indexed**: All common queries optimized
- ✅ **Validated**: Data integrity enforced
- ✅ **Documented**: Views provide clear access patterns
- ✅ **Extensible**: Can grow with future needs
- ✅ **Performant**: Optimized for real-world query patterns

