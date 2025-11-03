#!/usr/bin/env python3
"""
Test calendar import with a small sample

This script tests the calendar import functionality with a limited number of events
"""

import sys
import os
from pathlib import Path

# Add src and scripts to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'scripts'))

from import_calendar_events import CalendarEventImporter
from extractors.gcal_extractor import GoogleCalendarExtractor
from utils.logger import get_logger
import sqlite3

logger = get_logger('test_calendar')

def test_import(db_path: str, max_events: int = 5):
    """Test importing a small number of calendar events"""
    print("=" * 60)
    print("Testing Calendar Event Import")
    print("=" * 60)
    
    # Check if credentials exist
    if not os.path.exists('credentials.json'):
        print("\n⚠ Google Calendar credentials not found.")
        print("   Skipping live extraction test.")
        print("   Testing database import logic only...\n")
        test_database_logic(db_path)
        return
    
    print("\n1. Initializing calendar extractor...")
    try:
        extractor = GoogleCalendarExtractor(use_llm=False)  # Faster without LLM for testing
        print("   ✓ Extractor initialized")
    except Exception as e:
        print(f"   ✗ Failed to initialize: {e}")
        return
    
    print(f"\n2. Extracting up to {max_events} calendar events...")
    try:
        ledger = extractor.extract_all(max_results=max_events)
        print(f"   ✓ Extracted {len(ledger.messages)} events")
        
        if not ledger.messages:
            print("   ⚠ No events found to import")
            return
        
        # Show sample events
        print("\n   Sample events:")
        for i, msg in enumerate(ledger.messages[:3], 1):
            print(f"   {i}. {msg.subject}")
            print(f"      Start: {msg.event_start}")
            print(f"      Organizer: {msg.sender.email}")
            print(f"      Recipients: {len(msg.recipients)}")
        
    except Exception as e:
        print(f"   ✗ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\n3. Importing into database: {db_path}")
    importer = CalendarEventImporter(db_path=db_path)
    
    try:
        importer.connect()
        
        # Check count before
        conn = importer.conn
        cursor = conn.execute("SELECT COUNT(*) FROM calendar_events")
        count_before = cursor.fetchone()[0]
        print(f"   Current calendar_events count: {count_before}")
        
        # Import
        imported = importer.import_events(extractor)
        
        # Check count after
        cursor = conn.execute("SELECT COUNT(*) FROM calendar_events")
        count_after = cursor.fetchone()[0]
        
        print(f"   ✓ Imported {imported} new events")
        print(f"   Total calendar_events: {count_before} → {count_after}")
        
        # Verify a sample
        cursor = conn.execute("""
            SELECT ce.event_id, ce.event_start, ce.event_location, ce.calendar_name,
                   m.subject, m.platform_message_id
            FROM calendar_events ce
            JOIN messages m ON ce.message_id = m.message_id
            ORDER BY ce.created_at DESC
            LIMIT 3
        """)
        
        rows = cursor.fetchall()
        if rows:
            print("\n   Latest imported events:")
            for row in rows:
                print(f"   - {row[4]} ({row[1]})")
        
        importer.close()
        print("\n✓ Test completed successfully!")
        
    except Exception as e:
        print(f"   ✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        if importer.conn:
            importer.close()

def test_database_logic(db_path: str):
    """Test database import logic without actual extraction"""
    print("\nTesting database schema and import logic...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check schema
        cursor.execute("PRAGMA table_info(calendar_events)")
        cols = [row[1] for row in cursor.fetchall()]
        
        required_cols = [
            'event_id', 'message_id', 'event_start', 'event_end',
            'event_timezone', 'calendar_name', 'organizer_email',
            'attendee_count', 'has_video_conference'
        ]
        
        missing = [c for c in required_cols if c not in cols]
        if missing:
            print(f"   ✗ Missing columns: {missing}")
            print("   Run: python3 scripts/migrate_calendar_schema.py")
        else:
            print(f"   ✓ Schema is complete ({len(cols)} columns)")
        
        # Check indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='calendar_events'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"   ✓ Found {len(indexes)} indexes")
        
        conn.close()
        print("\n✓ Database schema test passed!")
        
    except Exception as e:
        print(f"   ✗ Database test failed: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test calendar import")
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    parser.add_argument('--max-events', type=int, default=5,
                       help='Maximum number of events to test with')
    
    args = parser.parse_args()
    
    test_import(args.db_path, args.max_events)

