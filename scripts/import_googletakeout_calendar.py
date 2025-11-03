#!/usr/bin/env python3
"""
Import Google Takeout Calendar events into the SQLite database

This script:
1. Reads googletakeoutcal_raw.jsonl from data/raw/
2. Filters for events where user is invited
3. Imports into messages and calendar_events tables
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.logger import get_logger

logger = get_logger('takeout_calendar_importer')


class GoogleTakeoutCalendarImporter:
    """Import Google Takeout calendar events into SQLite database"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self, db_path: str, raw_jsonl_path: str = "data/raw/googletakeoutcal_raw.jsonl"):
        """
        Initialize importer
        
        Args:
            db_path: Path to SQLite database file
            raw_jsonl_path: Path to raw Google Takeout JSONL file
        """
        self.db_path = db_path
        self.raw_jsonl_path = raw_jsonl_path
        self.conn = None
        
    def connect(self):
        """Connect to database"""
        logger.info(f"Connecting to database: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def import_events(self):
        """Import all events from JSONL file"""
        if not self.conn:
            self.connect()
        
        # Check if raw file exists
        if not os.path.exists(self.raw_jsonl_path):
            logger.error(f"Raw file not found: {self.raw_jsonl_path}")
            return 0
        
        logger.info(f"Reading events from {self.raw_jsonl_path}")
        
        imported_count = 0
        skipped_count = 0
        filtered_count = 0
        
        with open(self.raw_jsonl_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                    
                    # Filter for events where user is invited
                    if not self._should_include_event(event):
                        filtered_count += 1
                        continue
                    
                    if self._import_calendar_event(event):
                        imported_count += 1
                    else:
                        skipped_count += 1
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Error parsing JSON on line {line_num}: {e}")
                    skipped_count += 1
                except Exception as e:
                    logger.error(f"Error importing event on line {line_num}: {e}")
                    skipped_count += 1
                    continue
        
        self.conn.commit()
        logger.info(f"Import complete: {imported_count} imported, {skipped_count} skipped, {filtered_count} filtered")
        return imported_count
    
    def _should_include_event(self, event: dict) -> bool:
        """Determine if event should be included based on filtering criteria"""
        # Check if user's email is in attendees or organizer
        attendees_list = event.get('attendees', [])
        organizer = event.get('organizer', '')
        
        # Check organizer
        if organizer and organizer in self.TARGET_EMAILS:
            return True
        
        # Check attendees
        for attendee_email in attendees_list:
            if attendee_email in self.TARGET_EMAILS:
                return True
        
        return False
    
    def _import_calendar_event(self, event: dict) -> bool:
        """
        Import a single calendar event as both a message and calendar_event
        
        Returns:
            True if imported, False if skipped (duplicate)
        """
        # Parse event data
        uid = event.get('uid', 'unknown')
        platform_msg_id = f"googletakeoutcal_{uid}"
        
        # Check if message already exists
        cursor = self.conn.execute("""
            SELECT message_id FROM messages 
            WHERE platform = ? AND platform_message_id = ?
        """, ('googletakeoutcal', platform_msg_id))
        
        existing = cursor.fetchone()
        if existing:
            logger.debug(f"Event {uid} already exists, skipping")
            return False
        
        # Get or create conversation for calendar events
        conv_id = self._get_or_create_calendar_conversation(event)
        
        # Get or create organizer contact (sender)
        organizer_email = event.get('organizer', '')
        sender_id = self._get_or_create_contact(organizer_email or 'system@googletakeout.com')
        
        # Parse timestamps
        start_str = event.get('start')
        end_str = event.get('end')
        
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if start_str else None
        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else None
        
        # Use start time as message timestamp
        timestamp = start_dt if start_dt else datetime.now()
        
        # Prepare subject and body
        subject = event.get('summary', 'Untitled Event')
        body = event.get('description', '') or event.get('summary', '') or '[Calendar Event]'
        
        # Insert message
        try:
            cursor = self.conn.execute("""
                INSERT INTO messages (
                    platform, platform_message_id, conversation_id, sender_id,
                    timestamp, timezone, body, subject,
                    is_read, is_starred, is_sent, is_reply,
                    raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                'googletakeoutcal',
                platform_msg_id,
                conv_id,
                sender_id,
                timestamp.isoformat(),
                None,
                body,
                subject,
                True,
                False,
                True,
                False,
                json.dumps(event, default=str)
            ))
            
            message_db_id = cursor.lastrowid
            
            # Insert calendar event details
            if start_dt:
                # Calculate duration
                duration_seconds = None
                if end_dt:
                    duration = end_dt - start_dt
                    duration_seconds = int(duration.total_seconds())
                
                # Insert calendar event
                self.conn.execute("""
                    INSERT INTO calendar_events (
                        message_id, event_start, event_end,
                        event_duration_seconds, event_location,
                        event_status, is_recurring, recurrence_pattern
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_db_id,
                    start_dt.isoformat() if start_dt else None,
                    end_dt.isoformat() if end_dt else None,
                    duration_seconds,
                    event.get('location', ''),
                    event.get('status', 'confirmed'),
                    False,
                    None
                ))
            
            # Import attendees as conversation participants
            for attendee_email in event.get('attendees', []):
                attendee_id = self._get_or_create_contact(attendee_email)
                self.conn.execute("""
                    INSERT OR IGNORE INTO conversation_participants 
                    (conversation_id, contact_id, role)
                    VALUES (?, ?, ?)
                """, (conv_id, attendee_id, 'member'))
            
            return True
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity error importing {uid}: {e}")
            return False
    
    def _get_or_create_calendar_conversation(self, event: dict) -> int:
        """Get or create a conversation for calendar events"""
        uid = event.get('uid', 'unknown')
        thread_id = f"googletakeoutcal:{uid}"
        
        cursor = self.conn.execute("""
            SELECT conversation_id FROM conversations 
            WHERE platform = ? AND thread_id = ?
        """, ('googletakeoutcal', thread_id))
        
        row = cursor.fetchone()
        if row:
            return row['conversation_id']
        
        # Create new conversation
        subject = event.get('summary', 'Calendar Event')
        start_dt = datetime.fromisoformat(event.get('start').replace('Z', '+00:00')) if event.get('start') else datetime.now()
        
        cursor = self.conn.execute("""
            INSERT INTO conversations (
                conversation_name, platform, thread_id,
                first_message_at, last_message_at,
                is_group, participant_count, message_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subject,
            'googletakeoutcal',
            thread_id,
            start_dt.isoformat(),
            start_dt.isoformat(),
            len(event.get('attendees', [])) > 1,
            len(event.get('attendees', [])),
            1
        ))
        
        return cursor.lastrowid
    
    def _get_or_create_contact(self, email: str) -> int:
        """Get or create contact, return contact_id"""
        # Try to find existing contact by email
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE email = ? COLLATE NOCASE
        """, (email,))
        
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        # Try to find by platform_id across platforms
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = ? AND platform_id = ?
        """, ('googletakeoutcal', email))
        
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        # Create new contact
        cursor = self.conn.execute("""
            INSERT INTO contacts (display_name, email, platform, platform_id)
            VALUES (?, ?, ?, ?)
        """, (email.split('@')[0], email, 'googletakeoutcal', email))
        
        return cursor.lastrowid


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import Google Takeout calendar events into database")
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    parser.add_argument('--raw-jsonl', default='data/raw/googletakeoutcal_raw.jsonl',
                       help='Path to raw Google Takeout JSONL file')
    
    args = parser.parse_args()
    
    logger.info("Starting Google Takeout calendar import...")
    
    # Create importer
    importer = GoogleTakeoutCalendarImporter(
        db_path=args.db_path,
        raw_jsonl_path=args.raw_jsonl
    )
    
    try:
        # Import events
        count = importer.import_events()
        
        logger.info(f"Successfully imported {count} calendar events!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
    finally:
        importer.close()


if __name__ == '__main__':
    main()

