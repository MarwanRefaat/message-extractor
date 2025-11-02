"""
WhatsApp extraction module
Extracts messages from WhatsApp SQLite database (iOS or Android backup)
"""
import sqlite3
import os
from datetime import datetime
from typing import List, Optional
import json

from schema import Message, Contact, UnifiedLedger

# Filter start date: January 1, 2024 (in milliseconds since Unix epoch)
FILTER_START_TIMESTAMP_MS = int(datetime(2024, 1, 1).timestamp() * 1000)


class WhatsAppExtractor:
    """Extract messages from WhatsApp database"""
    
    def __init__(self, db_path: str):
        """
        Initialize extractor with path to WhatsApp database
        
        iOS: SQLite backup or from devices
        Android: Located in /data/data/com.whatsapp/databases/msgstore.db
        """
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"WhatsApp database not found at: {self.db_path}")
    
    def extract_all(self) -> UnifiedLedger:
        """Extract all messages from WhatsApp"""
        ledger = UnifiedLedger()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # WhatsApp uses different table structures depending on version
        # Try to detect which tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'message' in tables:
            # Modern WhatsApp structure (filtered to 2024 onwards)
            query = """
            SELECT 
                m._id,
                m.key_id,
                m.key_remote_jid,
                m.data,
                m.timestamp,
                m.remote_resource,
                m.received_timestamp,
                m.receipt_server_timestamp,
                m.read_receipts,
                m.media_wa_type,
                m.media_name,
                j.raw_string_jid as jid_display_name
            FROM message m
            LEFT JOIN jid j ON m.key_remote_jid = j.raw_string_jid
            WHERE m.timestamp >= ?
            ORDER BY m.timestamp
            """
            cursor.execute(query, (FILTER_START_TIMESTAMP_MS,))
        elif 'messages' in tables:
            # Older WhatsApp structure (filtered to 2024 onwards)
            query = """
            SELECT 
                _id,
                key_remote_jid,
                data,
                timestamp,
                receipt_timestamp
            FROM messages
            WHERE timestamp >= ?
            ORDER BY timestamp
            """
            cursor.execute(query, (FILTER_START_TIMESTAMP_MS,))
        else:
            conn.close()
            raise ValueError("Could not find recognized WhatsApp message tables")
        rows = cursor.fetchall()
        
        for row in rows:
            try:
                message = self._row_to_message(row, cursor)
                ledger.add_message(message)
            except Exception as e:
                print(f"Error processing WhatsApp row {row.get('_id', 'unknown')}: {e}")
                continue
        
        conn.close()
        return ledger
    
    def _row_to_message(self, row: sqlite3.Row, cursor: sqlite3.Cursor) -> Message:
        """Convert database row to Message object"""
        # Parse timestamp (WhatsApp uses milliseconds since Unix epoch)
        timestamp_ms = row.get('timestamp') or row.get('receipt_timestamp', 0)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
        
        # Parse JID (WhatsApp ID format: phone_number@s.whatsapp.net or group_id@g.us)
        jid = row.get('key_remote_jid') or row.get('remote_resource', '')
        
        if '@s.whatsapp.net' in jid:
            # Individual chat
            phone = jid.split('@')[0]
            is_group = False
        elif '@g.us' in jid:
            # Group chat
            phone = jid
            is_group = True
        else:
            phone = jid
            is_group = False
        
        # Get display name
        display_name = row.get('jid_display_name') or phone
        
        # Extract text data
        data = row.get('data') or row.get('message_text', '')
        
        # Determine sender
        # WhatsApp stores messages you sent differently from received
        # This is a simplified approach - you may need to check additional fields
        is_from_me = row.get('key_from_me', False)
        
        if is_from_me:
            sender = Contact(
                name="Me",
                email=None,
                phone=None,
                platform_id="me",
                platform="whatsapp"
            )
            recipient = Contact(
                name=display_name,
                email=None,
                phone=phone,
                platform_id=jid,
                platform="whatsapp"
            )
            recipients = [recipient]
        else:
            sender = Contact(
                name=display_name,
                email=None,
                phone=phone,
                platform_id=jid,
                platform="whatsapp"
            )
            recipients = [Contact(
                name="Me",
                email=None,
                phone=None,
                platform_id="me",
                platform="whatsapp"
            )]
        
        participants = [sender] + recipients
        
        # Check for media attachments
        attachments = []
        if row.get('media_name'):
            attachments.append(row['media_name'])
        
        message = Message(
            message_id=f"whatsapp:{row.get('key_id') or row.get('_id')}",
            platform="whatsapp",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=None,
            body=data,
            attachments=attachments,
            thread_id=None,
            is_read=row.get('read_receipts') is not None if 'read_receipts' in row else None,
            is_starred=False,
            is_reply=None,
            original_message_id=None,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data=dict(row)
        )
        
        return message
    
    def export_raw(self, output_dir: str):
        """Export raw WhatsApp data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "whatsapp_raw.jsonl")
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all messages
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'message' in tables:
            query = "SELECT * FROM message"
        elif 'messages' in tables:
            query = "SELECT * FROM messages"
        else:
            conn.close()
            return
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        with open(output_path, 'w') as f:
            for row in rows:
                data = {k: row[k] for k in row.keys()}
                f.write(json.dumps(data) + '\n')
        
        conn.close()
        print(f"Exported {len(rows)} raw WhatsApp records to {output_path}")

