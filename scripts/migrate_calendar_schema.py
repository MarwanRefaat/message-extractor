#!/usr/bin/env python3
"""
Migrate calendar_events table to add enhanced columns

This script safely adds new columns to the existing calendar_events table
without losing any data.
"""

import sqlite3
import sys
from pathlib import Path

def migrate_calendar_schema(db_path: str):
    """Add new columns to calendar_events table"""
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(calendar_events)")
    existing_cols = {col[1]: col for col in cursor.fetchall()}
    
    print(f"\nCurrent columns: {list(existing_cols.keys())}")
    
    # New columns to add
    new_columns = {
        'event_timezone': 'TEXT',
        'calendar_name': 'TEXT',
        'organizer_email': 'TEXT',
        'attendee_count': 'INTEGER DEFAULT 0',
        'has_video_conference': 'BOOLEAN DEFAULT 0',
        'video_conference_url': 'TEXT',
        'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
        'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
    }
    
    # Add missing columns
    added = []
    for col_name, col_type in new_columns.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE calendar_events ADD COLUMN {col_name} {col_type}")
                added.append(col_name)
                print(f"✓ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ Error adding {col_name}: {e}")
        else:
            print(f"- Column {col_name} already exists")
    
    # Add indexes if they don't exist
    indexes = [
        ("idx_calendar_events_start", "CREATE INDEX idx_calendar_events_start ON calendar_events(event_start DESC)"),
        ("idx_calendar_events_status", "CREATE INDEX idx_calendar_events_status ON calendar_events(event_status)"),
        ("idx_calendar_events_location", "CREATE INDEX idx_calendar_events_location ON calendar_events(event_location) WHERE event_location IS NOT NULL"),
        ("idx_calendar_events_recurring", "CREATE INDEX idx_calendar_events_recurring ON calendar_events(is_recurring) WHERE is_recurring = 1")
    ]
    
    # Check existing indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='calendar_events'")
    existing_indexes = {row[0] for row in cursor.fetchall()}
    
    print("\nAdding indexes...")
    for idx_name, idx_sql in indexes:
        if idx_name not in existing_indexes:
            try:
                cursor.execute(idx_sql)
                print(f"✓ Added index: {idx_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ Error adding index {idx_name}: {e}")
        else:
            print(f"- Index {idx_name} already exists")
    
    conn.commit()
    
    # Verify final schema
    cursor.execute("PRAGMA table_info(calendar_events)")
    final_cols = [col[1] for col in cursor.fetchall()]
    
    print(f"\n✓ Migration complete!")
    print(f"Final columns ({len(final_cols)}): {', '.join(final_cols)}")
    
    if added:
        print(f"\nAdded {len(added)} new columns: {', '.join(added)}")
    
    conn.close()
    return len(added) > 0

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Migrate calendar_events table schema")
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)
    
    try:
        changed = migrate_calendar_schema(str(db_path))
        if changed:
            print("\n✓ Schema migration successful!")
        else:
            print("\n✓ Schema already up to date!")
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

