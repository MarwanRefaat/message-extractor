#!/usr/bin/env python3
"""
Full calendar import workflow

This script:
1. Verifies database schema is up to date
2. Tests extraction with small sample
3. Imports all calendar events to database
4. Generates import report
"""

import sys
import os
from pathlib import Path

# Add paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
sys.path.insert(0, str(project_root / 'scripts'))

from extractors.gcal_extractor import GoogleCalendarExtractor
from import_calendar_events import CalendarEventImporter
from migrate_calendar_schema import migrate_calendar_schema
from optimize_calendar_schema import optimize_schema
from utils.logger import get_logger
import sqlite3

logger = get_logger('full_calendar_import')


def verify_setup():
    """Verify prerequisites"""
    print("=" * 80)
    print("Calendar Import - Setup Verification")
    print("=" * 80)
    
    # Check credentials
    creds_path = project_root / 'credentials.json'
    if not creds_path.exists():
        print("\n✗ credentials.json not found!")
        print("  Please download from Google Cloud Console and place in project root")
        return False
    print(f"✓ Found credentials.json")
    
    # Check database
    db_path = project_root / 'data' / 'database' / 'chats.db'
    if not db_path.exists():
        print(f"\n⚠ Database not found: {db_path}")
        print("  Will create new database")
    else:
        print(f"✓ Found database: {db_path}")
    
    return True


def test_small_sample(db_path: str):
    """Test with a small sample first"""
    print("\n" + "=" * 80)
    print("Testing with small sample (3 events)...")
    print("=" * 80)
    
    try:
        extractor = GoogleCalendarExtractor(use_llm=True)
        ledger = extractor.extract_all(max_results=3)
        
        print(f"\n✓ Extracted {len(ledger.messages)} events")
        
        if ledger.messages:
            print("\nSample events:")
            for i, msg in enumerate(ledger.messages, 1):
                print(f"\n{i}. {msg.subject}")
                print(f"   Start: {msg.event_start}")
                print(f"   Organizer: {msg.sender.email}")
                print(f"   Recipients: {len(msg.recipients)}")
                print(f"   Location: {msg.event_location or 'N/A'}")
            
            # Test import
            print("\n\nTesting database import...")
            importer = CalendarEventImporter(db_path=str(db_path))
            imported = importer.import_events(extractor)
            importer.close()
            
            print(f"✓ Successfully imported {imported} events to database!")
            return True
        else:
            print("\n⚠ No events found (may be filtered out)")
            print("  This could mean:")
            print("  - No events where you're invited")
            print("  - All events filtered as holidays")
            print("  - Email/phone filters not matching")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def full_import(db_path: str):
    """Import all calendar events"""
    print("\n" + "=" * 80)
    print("Full Calendar Import")
    print("=" * 80)
    
    try:
        extractor = GoogleCalendarExtractor(use_llm=True)
        
        # Extract all events
        print("\n1. Extracting calendar events...")
        ledger = extractor.extract_all()
        print(f"   ✓ Found {len(ledger.messages)} events matching criteria")
        
        if not ledger.messages:
            print("\n⚠ No events to import")
            return 0
        
        # Import to database
        print("\n2. Importing to database...")
        importer = CalendarEventImporter(db_path=str(db_path))
        imported = importer.import_events(extractor)
        importer.close()
        
        print(f"   ✓ Imported {imported} events")
        
        # Generate report
        print("\n3. Generating import report...")
        generate_report(db_path)
        
        return imported
        
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def generate_report(db_path: str):
    """Generate import report"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("SELECT COUNT(*) FROM calendar_events")
    total_events = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calendar_events WHERE event_start > datetime('now')")
    upcoming = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calendar_events WHERE has_video_conference = 1")
    video_meetings = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM calendar_events WHERE is_recurring = 1")
    recurring = cursor.fetchone()[0]
    
    # Calendar breakdown
    cursor.execute("SELECT calendar_name, COUNT(*) FROM calendar_events GROUP BY calendar_name ORDER BY COUNT(*) DESC LIMIT 5")
    calendars = cursor.fetchall()
    
    # Status breakdown
    cursor.execute("SELECT event_status, COUNT(*) FROM calendar_events GROUP BY event_status")
    statuses = cursor.fetchall()
    
    print("\n" + "-" * 80)
    print("IMPORT REPORT")
    print("-" * 80)
    print(f"\nTotal Events:     {total_events:,}")
    print(f"Upcoming:         {upcoming:,}")
    print(f"Video Meetings:   {video_meetings:,}")
    print(f"Recurring:        {recurring:,}")
    
    if calendars:
        print(f"\nTop Calendars:")
        for name, count in calendars:
            print(f"  {name or 'Unknown'}: {count:,}")
    
    if statuses:
        print(f"\nStatus Breakdown:")
        for status, count in statuses:
            print(f"  {status or 'Unknown'}: {count:,}")
    
    print("\n" + "-" * 80)
    conn.close()


def main():
    """Main workflow"""
    db_path = project_root / 'data' / 'database' / 'chats.db'
    
    # Verify setup
    if not verify_setup():
        sys.exit(1)
    
    # Ensure schema is up to date
    print("\n" + "=" * 80)
    print("Updating Database Schema")
    print("=" * 80)
    migrate_calendar_schema(str(db_path))
    optimize_schema(str(db_path))
    
    # Test with small sample
    if not test_small_sample(db_path):
        print("\n⚠ Small sample test had issues. Continue with full import? (y/n)")
        response = input().strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)
    
    # Full import
    imported = full_import(db_path)
    
    if imported > 0:
        print("\n" + "=" * 80)
        print(f"✓ Successfully imported {imported} calendar events!")
        print("=" * 80)
    else:
        print("\n⚠ No events were imported. Check filtering criteria.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

