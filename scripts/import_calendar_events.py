#!/usr/bin/env python3
"""
Import calendar events into the SQLite database

This script:
1. Extracts calendar events using GoogleCalendarExtractor
2. Filters for events where user was invited (by email/phone)
3. Excludes generic holidays
4. Imports into messages and calendar_events tables
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

from extractors.gcal_extractor import GoogleCalendarExtractor
from schema import Message, Contact
from utils.logger import get_logger

logger = get_logger('calendar_importer')


class CalendarEventImporter:
    """Import calendar events into SQLite database"""
    
    def __init__(self, db_path: str):
        """
        Initialize importer
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
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
    
    def import_events(self, extractor: Optional[GoogleCalendarExtractor] = None):
        """
        Extract and import calendar events
        
        Args:
            extractor: Optional GoogleCalendarExtractor instance (will create if None)
        """
        if not self.conn:
            self.connect()
        
        # Create extractor if not provided
        if extractor is None:
            logger.info("Initializing Google Calendar extractor...")
            extractor = GoogleCalendarExtractor(use_llm=True)
        
        # Extract events
        logger.info("Extracting calendar events...")
        ledger = extractor.extract_all()
        
        logger.info(f"Found {len(ledger.messages)} calendar events to import")
        
        imported_count = 0
        skipped_count = 0
        
        for message in ledger.messages:
            try:
                if self._import_calendar_message(message):
                    imported_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Error importing event {message.message_id}: {e}")
                skipped_count += 1
                continue
        
        self.conn.commit()
        logger.info(f"Import complete: {imported_count} imported, {skipped_count} skipped")
        return imported_count
    
    def _import_calendar_message(self, message: Message) -> bool:
        """
        Import a single calendar event as both a message and calendar_event
        
        Returns:
            True if imported, False if skipped (duplicate)
        """
        # Check if message already exists
        cursor = self.conn.execute("""
            SELECT message_id FROM messages 
            WHERE platform = ? AND platform_message_id = ?
        """, (message.platform, message.message_id.split(':')[1] if ':' in message.message_id else message.message_id))
        
        existing = cursor.fetchone()
        if existing:
            logger.debug(f"Event {message.message_id} already exists, skipping")
            return False
        
        # Get or create conversation for calendar events
        conv_id = self._get_or_create_calendar_conversation(message)
        
        # Get or create sender contact
        sender_id = self._get_or_create_contact(message.sender)
        
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
                message.platform,
                message.message_id.split(':')[1] if ':' in message.message_id else message.message_id,
                conv_id,
                sender_id,
                message.timestamp.isoformat(),
                message.timezone,
                message.body,
                message.subject,
                message.is_read,
                message.is_starred,
                True,  # Calendar events are "sent" (created)
                message.is_reply or False,
                json.dumps(message.raw_data, default=str)
            ))
            
            message_db_id = cursor.lastrowid
            
            # Insert calendar event details
            if message.event_start:
                # Calculate duration
                duration_seconds = None
                if message.event_end:
                    duration = message.event_end - message.event_start
                    duration_seconds = int(duration.total_seconds())
                
                # Parse recurrence
                is_recurring = message.raw_data.get('is_recurring', False)
                recurrence_pattern = message.raw_data.get('recurrence_pattern')
                
                # Extract additional calendar metadata
                calendar_name = message.raw_data.get('calendar_name')
                organizer_email = message.sender.email
                attendee_count = len(message.recipients)
                
                # Check for video conference links
                has_video = False
                video_url = None
                if message.body:
                    # Look for common video conference URLs
                    import re
                    video_patterns = [
                        r'https?://(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com)/[^\s<>"]+',
                        r'zoom\.us/j/\d+',
                        r'meet\.google\.com/[a-z]+-[a-z]+-[a-z]+'
                    ]
                    for pattern in video_patterns:
                        match = re.search(pattern, message.body, re.IGNORECASE)
                        if match:
                            has_video = True
                            video_url = match.group(0)
                            break
                
                self.conn.execute("""
                    INSERT INTO calendar_events (
                        message_id, event_start, event_end,
                        event_duration_seconds, event_location,
                        event_status, event_timezone, is_recurring, recurrence_pattern,
                        calendar_name, organizer_email, attendee_count,
                        has_video_conference, video_conference_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_db_id,
                    message.event_start.isoformat() if message.event_start else None,
                    message.event_end.isoformat() if message.event_end else None,
                    duration_seconds,
                    message.event_location,
                    message.event_status or 'confirmed',
                    message.timezone,
                    is_recurring,
                    recurrence_pattern,
                    calendar_name,
                    organizer_email,
                    attendee_count,
                    has_video,
                    video_url
                ))
            
            # Import recipients as conversation participants
            for recipient in message.recipients:
                recipient_id = self._get_or_create_contact(recipient)
                self.conn.execute("""
                    INSERT OR IGNORE INTO conversation_participants 
                    (conversation_id, contact_id, role)
                    VALUES (?, ?, ?)
                """, (conv_id, recipient_id, 'member'))
            
            return True
            
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity error importing {message.message_id}: {e}")
            return False
    
    def _get_or_create_calendar_conversation(self, message: Message) -> int:
        """Get or create a conversation for calendar events"""
        # Use a single conversation for all calendar events, or one per event
        # For now, let's use one conversation per event (thread_id = event_id)
        thread_id = f"gcal:{message.message_id.split(':')[1] if ':' in message.message_id else message.message_id}"
        
        cursor = self.conn.execute("""
            SELECT conversation_id FROM conversations 
            WHERE platform = ? AND thread_id = ?
        """, ('gcal', thread_id))
        
        row = cursor.fetchone()
        if row:
            return row['conversation_id']
        
        # Create new conversation
        subject = message.subject or 'Calendar Event'
        cursor = self.conn.execute("""
            INSERT INTO conversations (
                conversation_name, platform, thread_id,
                first_message_at, last_message_at,
                is_group, participant_count, message_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            subject,
            'gcal',
            thread_id,
            message.timestamp.isoformat(),
            message.timestamp.isoformat(),
            len(message.recipients) > 1,  # Group if multiple recipients
            len(message.participants),
            1
        ))
        
        return cursor.lastrowid
    
    def _get_or_create_contact(self, contact: Contact) -> int:
        """Get or create contact, return contact_id"""
        # Try to find existing contact by platform_id
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = ? AND platform_id = ?
        """, (contact.platform, contact.platform_id))
        
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        # Try to find by email or phone across platforms
        if contact.email:
            cursor = self.conn.execute("""
                SELECT contact_id FROM contacts 
                WHERE email = ? COLLATE NOCASE
            """, (contact.email,))
            row = cursor.fetchone()
            if row:
                return row['contact_id']
        
        if contact.phone:
            cursor = self.conn.execute("""
                SELECT contact_id FROM contacts 
                WHERE phone = ?
            """, (contact.phone,))
            row = cursor.fetchone()
            if row:
                return row['contact_id']
        
        # Create new contact
        cursor = self.conn.execute("""
            INSERT INTO contacts (
                display_name, email, phone, platform, platform_id
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            contact.name,
            contact.email,
            contact.phone,
            contact.platform,
            contact.platform_id
        ))
        
        return cursor.lastrowid


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import calendar events into database")
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    parser.add_argument('--credentials', default='credentials.json',
                       help='Path to Google Calendar credentials.json')
    parser.add_argument('--token', default='token.json',
                       help='Path to Google Calendar token.json')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM-based filtering (use rule-based only)')
    
    args = parser.parse_args()
    
    logger.info("Starting calendar event import...")
    
    # Create importer
    importer = CalendarEventImporter(db_path=args.db_path)
    
    try:
        # Create extractor
        extractor = GoogleCalendarExtractor(
            credentials_path=args.credentials,
            token_path=args.token,
            use_llm=not args.no_llm
        )
        
        # Import events
        count = importer.import_events(extractor)
        
        logger.info(f"Successfully imported {count} calendar events!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
    finally:
        importer.close()


if __name__ == '__main__':
    main()

