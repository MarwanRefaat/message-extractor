#!/usr/bin/env python3
"""
Optimize calendar events schema with additional enhancements

This adds:
- Calendar-specific views
- Additional indexes for common queries
- Constraints for data integrity
- Helper functions via views
"""

import sqlite3
import sys
from pathlib import Path

def optimize_schema(db_path: str):
    """Add optimizations to calendar_events schema"""
    print(f"Optimizing calendar schema in: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Add check constraints for data integrity
    print("\n1. Adding check constraints...")
    try:
        # Check that event_end is after event_start (if both exist)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS check_event_times
            BEFORE INSERT ON calendar_events
            WHEN NEW.event_end IS NOT NULL AND NEW.event_start IS NOT NULL 
                AND NEW.event_end < NEW.event_start
            BEGIN
                SELECT RAISE(ABORT, 'event_end must be after event_start');
            END
        """)
        print("   ✓ Added event time validation trigger")
    except sqlite3.OperationalError as e:
        if "already exists" not in str(e):
            print(f"   ⚠ Could not add time check: {e}")
    
    # 2. Create calendar-specific views
    print("\n2. Creating calendar views...")
    
    # Upcoming events view
    try:
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS upcoming_calendar_events AS
            SELECT 
                ce.event_id,
                ce.event_start,
                ce.event_end,
                ce.event_duration_seconds,
                ce.event_location,
                ce.event_status,
                ce.calendar_name,
                ce.organizer_email,
                ce.attendee_count,
                ce.has_video_conference,
                ce.video_conference_url,
                m.subject,
                m.body,
                m.timestamp,
                c.display_name as organizer_name,
                c.email as organizer_email_full
            FROM calendar_events ce
            JOIN messages m ON ce.message_id = m.message_id
            LEFT JOIN contacts c ON ce.organizer_email = c.email
            WHERE ce.event_start > datetime('now')
                AND ce.event_status != 'cancelled'
            ORDER BY ce.event_start ASC
        """)
        print("   ✓ Created upcoming_calendar_events view")
    except sqlite3.OperationalError as e:
        print(f"   - View already exists or error: {e}")
    
    # Calendar statistics view
    try:
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS calendar_statistics AS
            SELECT 
                calendar_name,
                COUNT(*) as total_events,
                SUM(CASE WHEN event_status = 'confirmed' THEN 1 ELSE 0 END) as confirmed_count,
                SUM(CASE WHEN event_status = 'cancelled' THEN 1 ELSE 0 END) as cancelled_count,
                SUM(CASE WHEN is_recurring = 1 THEN 1 ELSE 0 END) as recurring_count,
                SUM(CASE WHEN has_video_conference = 1 THEN 1 ELSE 0 END) as video_conference_count,
                COUNT(DISTINCT organizer_email) as unique_organizers,
                AVG(attendee_count) as avg_attendees,
                MIN(event_start) as first_event,
                MAX(event_start) as last_event
            FROM calendar_events
            GROUP BY calendar_name
            ORDER BY total_events DESC
        """)
        print("   ✓ Created calendar_statistics view")
    except sqlite3.OperationalError as e:
        print(f"   - View already exists or error: {e}")
    
    # Events by month view (for analytics)
    try:
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS calendar_events_by_month AS
            SELECT 
                strftime('%Y-%m', event_start) as month,
                calendar_name,
                COUNT(*) as event_count,
                SUM(CASE WHEN has_video_conference = 1 THEN 1 ELSE 0 END) as video_meetings,
                AVG(event_duration_seconds / 3600.0) as avg_hours
            FROM calendar_events
            WHERE event_start IS NOT NULL
            GROUP BY month, calendar_name
            ORDER BY month DESC, event_count DESC
        """)
        print("   ✓ Created calendar_events_by_month view")
    except sqlite3.OperationalError as e:
        print(f"   - View already exists or error: {e}")
    
    # 3. Add composite indexes for common query patterns
    print("\n3. Adding composite indexes...")
    
    indexes = [
        ("idx_calendar_events_start_status", 
         "CREATE INDEX IF NOT EXISTS idx_calendar_events_start_status ON calendar_events(event_start DESC, event_status)"),
        ("idx_calendar_events_calendar_start",
         "CREATE INDEX IF NOT EXISTS idx_calendar_events_calendar_start ON calendar_events(calendar_name, event_start DESC) WHERE calendar_name IS NOT NULL"),
        ("idx_calendar_events_organizer",
         "CREATE INDEX IF NOT EXISTS idx_calendar_events_organizer ON calendar_events(organizer_email) WHERE organizer_email IS NOT NULL"),
    ]
    
    for idx_name, idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            print(f"   ✓ Added index: {idx_name}")
        except sqlite3.OperationalError as e:
            print(f"   - Index {idx_name} already exists or error: {e}")
    
    # 4. Add function to automatically update updated_at
    print("\n4. Adding update timestamp trigger...")
    try:
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS update_calendar_events_timestamp
            AFTER UPDATE ON calendar_events
            BEGIN
                UPDATE calendar_events 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE event_id = NEW.event_id;
            END
        """)
        print("   ✓ Added auto-update timestamp trigger")
    except sqlite3.OperationalError as e:
        if "already exists" not in str(e):
            print(f"   ⚠ Could not add timestamp trigger: {e}")
    
    conn.commit()
    
    # Verify optimizations
    print("\n5. Verifying optimizations...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name LIKE 'calendar%'")
    views = [row[0] for row in cursor.fetchall()]
    print(f"   ✓ Calendar views: {len(views)} ({', '.join(views)})")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='calendar_events'")
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"   ✓ Calendar indexes: {len(indexes)} total")
    
    conn.close()
    print("\n✓ Schema optimization complete!")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Optimize calendar events schema")
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)
    
    try:
        optimize_schema(str(db_path))
    except Exception as e:
        print(f"\n✗ Optimization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

