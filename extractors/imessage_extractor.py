"""
iMessage extraction module
Extracts messages from macOS iMessage database
"""
import sqlite3
import os
import json
import base64
from datetime import datetime, timedelta
from typing import Optional

from schema import Message, Contact, UnifiedLedger
from constants import IMESSAGE_FILTER_TIMESTAMP_NS, IMESSAGE_EPOCH
from utils.logger import get_logger
from utils.contacts import get_contact_name, get_email_contact_name
from .ocr_extractor import extract_from_attachment_path

logger = get_logger(__name__)


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
        # Simplified query - contact table may not exist in all iMessage versions
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
            m.item_type,
            m.associated_message_type,
            m.associated_message_emoji,
            m.associated_message_guid,
            h.id as handle_id,
            COALESCE(h.uncanonicalized_id, h.id) as phone_email
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.rowid
        WHERE m.date >= ?
        ORDER BY m.date
        """
        
        cursor.execute(query, (IMESSAGE_FILTER_TIMESTAMP_NS,))
        rows = cursor.fetchall()
        
        # Get attachment information
        attachment_query = """
        SELECT attachment_id, a.filename, a.mime_type
        FROM message_attachment_join maj
        JOIN attachment a ON maj.attachment_id = a.rowid
        WHERE maj.message_id = ?
        """
        
        # Get chat participant lookup for messages with handle_id = 0
        chat_participant_query = """
        SELECT h.id as handle_id,
               COALESCE(h.uncanonicalized_id, h.id) as phone_email
        FROM chat_message_join cmj
        JOIN chat_handle_join chj ON cmj.chat_id = chj.chat_id
        JOIN handle h ON chj.handle_id = h.rowid
        WHERE cmj.message_id = ?
        LIMIT 1
        """
        
        for row in rows:
            try:
                message = self._row_to_message(row, cursor, attachment_query, chat_participant_query)
                
                # Skip truly empty messages that are not tapbacks and have no attachments
                # These appear to be iOS system messages or artifacts
                is_tapback = message.body and '[Tapback' in message.body
                if (not message.body or len(message.body.strip()) == 0) and \
                   not message.attachments and \
                   not is_tapback:
                    continue
                
                ledger.add_message(message)
            except Exception as e:
                logger.warning(f"Error processing iMessage row {row['rowid']}: {e}")
                continue
        
        conn.close()
        return ledger
    
    def _row_to_message(self, row: sqlite3.Row, cursor: sqlite3.Cursor, attachment_query: str, chat_participant_query: str) -> Message:
        """Convert database row to Message object"""
        # Get attachments
        cursor.execute(attachment_query, (row['rowid'],))
        attachments = cursor.fetchall()
        attachment_list = [att['filename'] for att in attachments if att['filename']]
        
        # Parse timestamp (iMessage stores as nanoseconds since 2001-01-01)
        timestamp_ns = row['date']
        timestamp = IMESSAGE_EPOCH + timedelta(seconds=timestamp_ns / 1e9)
        
        # Determine message body - handle Tapbacks and media-only messages
        body = row['text'] if row['text'] else ""
        # Treat whitespace-only strings as empty
        if body and not body.strip():
            body = ""
        
        # Check if this is a tapback - the definitive marker is associated_message_guid
        # NOT item_type, because iOS misuses item_type
        is_tapback = 'associated_message_guid' in row.keys() and row['associated_message_guid'] is not None
        
        if is_tapback:
            # This is a real tapback - check associated_message_type for specific tapback type
            tapback_type = row['associated_message_type'] if 'associated_message_type' in row.keys() else 0
            tapback_emoji = row['associated_message_emoji'] if 'associated_message_emoji' in row.keys() else None
            
            tapback_map = {
                2000: "Liked",
                2001: "Disliked",
                2002: "Loved",
                2003: "Laughed At",
                2004: "Emphasized",
                2005: "Questioned",
                2006: "Custom Emoji",  # Custom emoji tapback
                3000: "Interacted with Shake"
            }
            if tapback_type in tapback_map:
                # For custom emojis (type 2006), include the emoji
                if tapback_type == 2006 and tapback_emoji:
                    body = f"[Tapback: {tapback_emoji}]"
                else:
                    body = f"[Tapback: {tapback_map[tapback_type]}]"
            else:
                body = "[Tapback/Reaction]"
        elif not body and 'item_type' in row.keys():
            # This is NOT a tapback, but has no text - check other item_types
            item_type = row['item_type']
            if attachment_list:
                # If there are attachments, it's an attachment message
                body = "[Attachment]"
                # Try to extract OCR text from first attachment for context
                if attachment_list:
                    ocr_text = extract_from_attachment_path(attachment_list[0], max_length=300)
                    if ocr_text:
                        body = f"[Attachment]\nOCR: {ocr_text}"
            elif item_type == 2:
                body = "[Apple Pay Payment]"
            elif item_type == 3:
                body = "[Sticker]"
            elif item_type == 4:
                body = "[App Share]"
            elif item_type == 5:
                body = "[Location]"
            elif item_type == 6:
                body = "[Collaboration]"
            elif item_type is not None and item_type != 0:
                body = f"[Message Type {item_type}]"
        
        # Determine sender and recipients
        # First try to get phone_email from row, if None try chat participant lookup
        phone_email = row['phone_email'] if 'phone_email' in row.keys() else None
        
        # If phone_email is None, try to get it from chat participants (for messages with handle_id=0)
        if phone_email is None:
            cursor.execute(chat_participant_query, (row['rowid'],))
            chat_result = cursor.fetchone()
            if chat_result:
                phone_email = chat_result['phone_email']
        
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
            # Determine if phone_email is email or phone based on format
            email_val = None
            phone_val = None
            contact_name = None
            if phone_email:
                phone_email_str = str(phone_email)
                if '@' in phone_email_str:
                    email_val = phone_email_str
                    # Try to get contact name from Contacts app
                    contact_name = get_email_contact_name(email_val)
                else:
                    # Only set as phone if it looks like a phone number, not a URN or other ID
                    if phone_email_str.startswith('+') or phone_email_str.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                        phone_val = phone_email_str
                        # Try to get contact name from Contacts app
                        contact_name = get_contact_name(phone_val)
            
            recipient = Contact(
                name=contact_name,
                email=email_val,
                phone=phone_val,
                platform_id=str(phone_email) if phone_email else "unknown",
                platform="imessage"
            )
            recipients = [recipient]
        else:
            # Message received
            # Determine if phone_email is email or phone based on format
            email_val = None
            phone_val = None
            contact_name = None
            if phone_email:
                phone_email_str = str(phone_email)
                if '@' in phone_email_str:
                    email_val = phone_email_str
                    # Try to get contact name from Contacts app
                    contact_name = get_email_contact_name(email_val)
                else:
                    # Only set as phone if it looks like a phone number, not a URN or other ID
                    if phone_email_str.startswith('+') or phone_email_str.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                        phone_val = phone_email_str
                        # Try to get contact name from Contacts app
                        contact_name = get_contact_name(phone_val)
            
            sender = Contact(
                name=contact_name,
                email=email_val,
                phone=phone_val,
                platform_id=str(phone_email) if phone_email else "unknown",
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
            body=body,
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
                'phone_email': row['phone_email'] if 'phone_email' in row.keys() else None
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
        
        with open(output_path, 'w') as f:
            for row in rows:
                data = {}
                for k in row.keys():
                    try:
                        value = row[k]
                        # Convert bytes to base64 for JSON serialization
                        if isinstance(value, bytes):
                            data[k] = base64.b64encode(value).decode('utf-8')
                        else:
                            data[k] = value
                    except Exception:
                        data[k] = None
                f.write(json.dumps(data) + '\n')
        
        conn.close()
        logger.info(f"Exported {len(rows)} raw iMessage records to {output_path}")

