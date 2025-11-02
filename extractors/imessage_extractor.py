"""
iMessage extraction module
Extracts messages from macOS iMessage database
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from schema import Message, Contact, UnifiedLedger

# iMessage epoch: January 1, 2001
IMESSAGE_EPOCH = datetime(2001, 1, 1)
# Filter start date: January 1, 2024
FILTER_START_DATE = datetime(2024, 1, 1)
# Calculate nanoseconds since iMessage epoch for 2024-01-01
FILTER_START_TIMESTAMP_NS = int((FILTER_START_DATE - IMESSAGE_EPOCH).total_seconds() * 1e9)


class iMessageExtractor:
    """Extract messages from iMessage database"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize extractor with path to iMessage database
        
        Default path: ~/Library/Messages/chat.db
        """
        if db_path is None:
            home = os.path.expanduser("~")
            self.db_path = os.path.join(home, "Library/Messages/chat.db")
        else:
            self.db_path = db_path
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"iMessage database not found at: {self.db_path}")
    
    def extract_all(self) -> UnifiedLedger:
        """Extract all messages from iMessage"""
        ledger = UnifiedLedger()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get messages with contact information (filtered to 2024 onwards)
        query = """
        SELECT 
            m.rowid,
            m.guid,
            m.text,
            m.date,
            m.date_read,
            m.is_read,
            m.is_from_me,
            m.cache_has_attachments,
            h.id as handle_id,
            h.uncanonicalized_id as phone_email,
            c.display_name,
            c.service as service_name
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.rowid
        LEFT JOIN chat_message_join cm ON m.rowid = cm.message_id
        LEFT JOIN chat ch ON cm.chat_id = ch.rowid
        LEFT JOIN chat_handle_join chj ON ch.rowid = chj.chat_id
        LEFT JOIN handle h2 ON chj.handle_id = h2.rowid
        LEFT JOIN contact c ON h.uncanonicalized_id = c.service || ":" || h.uncanonicalized_id
        WHERE m.date >= ?
        ORDER BY m.date
        """
        
        cursor.execute(query, (FILTER_START_TIMESTAMP_NS,))
        rows = cursor.fetchall()
        
        # Get attachment information
        attachment_query = """
        SELECT attachment_id, filename, mime_type
        FROM message_attachment_join maj
        JOIN attachment a ON maj.attachment_id = a.rowid
        WHERE maj.message_id = ?
        """
        
        for row in rows:
            try:
                message = self._row_to_message(row, cursor, attachment_query)
                ledger.add_message(message)
            except Exception as e:
                print(f"Error processing iMessage row {row['rowid']}: {e}")
                continue
        
        conn.close()
        return ledger
    
    def _row_to_message(self, row: sqlite3.Row, cursor: sqlite3.Cursor, attachment_query: str) -> Message:
        """Convert database row to Message object"""
        # Get attachments
        cursor.execute(attachment_query, (row['rowid'],))
        attachments = cursor.fetchall()
        attachment_list = [att['filename'] for att in attachments if att['filename']]
        
        # Parse timestamp (iMessage stores as nanoseconds since 2001-01-01)
        timestamp_ns = row['date']
        timestamp = datetime(2001, 1, 1) + timedelta(seconds=timestamp_ns / 1e9)
        
        # Determine sender and recipients
        if row['is_from_me']:
            # Message sent by us
            sender = Contact(
                name="Me",
                email=None,
                phone=None,
                platform_id="me",
                platform="imessage"
            )
            # Get recipients from the chat
            recipient = Contact(
                name=row['display_name'],
                email=row['phone_email'] if '@' in str(row['phone_email']) else None,
                phone=row['phone_email'] if '@' not in str(row['phone_email']) else None,
                platform_id=str(row['phone_email']),
                platform="imessage"
            )
            recipients = [recipient]
        else:
            # Message received
            sender = Contact(
                name=row['display_name'],
                email=row['phone_email'] if '@' in str(row['phone_email']) else None,
                phone=row['phone_email'] if '@' not in str(row['phone_email']) else None,
                platform_id=str(row['phone_email']),
                platform="imessage"
            )
            recipients = [Contact(
                name="Me",
                email=None,
                phone=None,
                platform_id="me",
                platform="imessage"
            )]
        
        participants = [sender] + recipients
        
        message = Message(
            message_id=f"imessage:{row['guid']}",
            platform="imessage",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=None,
            body=row['text'] or "",
            attachments=attachment_list,
            thread_id=None,
            is_read=bool(row['is_read']),
            is_starred=False,
            is_reply=None,
            original_message_id=None,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data={
                'guid': row['guid'],
                'rowid': row['rowid'],
                'is_from_me': row['is_from_me'],
                'cache_has_attachments': row['cache_has_attachments'],
                'service': row['service_name']
            }
        )
        
        return message
    
    def export_raw(self, output_dir: str):
        """Export raw iMessage data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "imessage_raw.jsonl")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
        SELECT * FROM message
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        import json
        with open(output_path, 'w') as f:
            for row in rows:
                data = {k: row[k] for k in row.keys()}
                f.write(json.dumps(data) + '\n')
        
        conn.close()
        print(f"Exported {len(rows)} raw iMessage records to {output_path}")

