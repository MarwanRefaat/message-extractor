"""
WhatsApp extraction module
Extracts messages from WhatsApp SQLite database (iOS or Android backup)
"""
import sqlite3
import os
from datetime import datetime
import json

from schema import Message, Contact, UnifiedLedger
from constants import WHATSAPP_FILTER_TIMESTAMP_MS
from utils.logger import get_logger
from .ocr_extractor import extract_from_attachment_path

logger = get_logger(__name__)


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
                m.media_hash,
                m.media_mime_type,
                j.raw_string_jid as jid_display_name
            FROM message m
            LEFT JOIN jid j ON m.key_remote_jid = j.raw_string_jid
            WHERE m.timestamp >= ?
            ORDER BY m.timestamp
            """
            cursor.execute(query, (WHATSAPP_FILTER_TIMESTAMP_MS,))
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
            cursor.execute(query, (WHATSAPP_FILTER_TIMESTAMP_MS,))
        else:
            conn.close()
            raise ValueError("Could not find recognized WhatsApp message tables")
        rows = cursor.fetchall()
        
        for row in rows:
            try:
                message = self._row_to_message(row, cursor)
                ledger.add_message(message)
            except Exception as e:
                logger.warning(f"Error processing WhatsApp row {row.get('_id', 'unknown')}: {e}")
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
        media_name = row.get('media_name')
        if media_name:
            attachments.append(media_name)
        
        # Format body with attachment info if needed (similar to iMessage for unified timeline)
        body = data if data else ""
        
        # If no text but has attachments, format attachment info
        if not body.strip() and attachments:
            attachment_info = []
            for att in attachments[:3]:  # Limit to first 3 for speed
                try:
                    # Try to get file size
                    file_size = None
                    actual_path = None
                    
                    # Expand ~ in path if present
                    expanded_att = os.path.expanduser(att) if att else None
                    
                    # Try paths in order (WhatsApp media locations vary by platform)
                    possible_paths = []
                    if expanded_att:
                        possible_paths.append(expanded_att)  # Try expanded path first
                    if att and not att.startswith('~'):
                        possible_paths.append(att)  # Try original path
                    
                    # Try common WhatsApp media locations
                    if att:
                        filename_only = os.path.basename(att)
                        # iOS WhatsApp backup locations
                        possible_paths.extend([
                            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "MobileSync", "Backup", filename_only),
                            os.path.join(os.path.expanduser("~"), "Library", "Group Containers", "group.net.whatsapp.WhatsApp.shared", "Media", filename_only),
                        ])
                        # Android WhatsApp locations (if extracted to Mac)
                        possible_paths.extend([
                            os.path.join(os.path.expanduser("~"), "WhatsApp", "Media", filename_only),
                            os.path.join(os.path.expanduser("~"), "Downloads", "WhatsApp", filename_only),
                        ])
                    
                    for path in possible_paths:
                        if path and os.path.exists(path):
                            actual_path = path
                            break
                    
                    # Get file size if we found the file
                    if actual_path:
                        try:
                            size_bytes = os.path.getsize(actual_path)
                            size_mb = size_bytes / (1024 * 1024)
                            if size_mb >= 1:
                                file_size = f"{size_mb:.1f}MB"
                            else:
                                file_size = f"{size_mb * 1024:.0f}KB"
                        except Exception:
                            pass
                    
                    # Try quick OCR (only on first attachment for speed)
                    ocr_text = None
                    if att == attachments[0] and actual_path:  # Only OCR first attachment for speed
                        ocr_text = extract_from_attachment_path(actual_path, max_length=200, max_file_size_mb=3)  # Smaller limit for speed
                    
                    # Format attachment info (same format as iMessage for unified timeline)
                    if ocr_text:
                        if file_size:
                            attachment_info.append(f"[Attachment: {ocr_text}] ({file_size})")
                        else:
                            attachment_info.append(f"[Attachment: {ocr_text}]")
                    elif file_size:
                        attachment_info.append(f"[Attachment] ({file_size})")
                    else:
                        # Show filename if we have it
                        filename = os.path.basename(att) if att else "file"
                        attachment_info.append(f"[Attachment: {filename}]")
                except Exception:
                    # Fallback to basic format
                    filename = os.path.basename(att) if att else "file"
                    attachment_info.append(f"[Attachment: {filename}]")
            
            if len(attachments) > 3:
                attachment_info.append(f"[+{len(attachments) - 3} more]")
            
            body = " ".join(attachment_info)
        elif body.strip() and attachments:
            # If there's text AND attachments, append attachment info
            attachment_info = []
            for att in attachments[:2]:  # Limit to first 2 when there's already text
                try:
                    filename = os.path.basename(att) if att else "file"
                    # Quick size check if file exists
                    file_size = None
                    expanded_att = os.path.expanduser(att) if att else None
                    for path in [expanded_att, att] if expanded_att else [att]:
                        if path and os.path.exists(path):
                            try:
                                size_bytes = os.path.getsize(path)
                                size_mb = size_bytes / (1024 * 1024)
                                file_size = f"{size_mb:.1f}MB" if size_mb >= 1 else f"{size_mb * 1024:.0f}KB"
                            except Exception:
                                pass
                            break
                    
                    if file_size:
                        attachment_info.append(f"[Attachment: {filename}] ({file_size})")
                    else:
                        attachment_info.append(f"[Attachment: {filename}]")
                except Exception:
                    attachment_info.append("[Attachment]")
            
            if attachment_info:
                body = body + " " + " ".join(attachment_info)
        
        message = Message(
            message_id=f"whatsapp:{row.get('key_id') or row.get('_id')}",
            platform="whatsapp",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=None,
            body=body,
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
        logger.info(f"Exported {len(rows)} raw WhatsApp records to {output_path}")

