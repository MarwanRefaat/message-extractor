#!/usr/bin/env python3
"""
Create a normalized SQLite database for chat messages

This script:
1. Creates the database schema
2. Parses HTML iMessage exports
3. Uses LLM to intelligently extract messages
4. Imports all data into the database
5. Generates neat reports

Run with: python create_chat_database.py
"""

import os
import sys
import sqlite3
import json
import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from schema import Message, Contact, UnifiedLedger
from extractors.llm_extractor import LLMExtractor
from utils.logger import get_logger

logger = get_logger('chat_db_creator')


class ChatDatabaseCreator:
    """Create and populate SQLite database with chat messages"""
    
    def __init__(self, db_path: str = "data/database/chats.db", contacts_csv_path: Optional[str] = None):
        """
        Initialize database creator
        
        Args:
            db_path: Path to SQLite database file
            contacts_csv_path: Path to contacts CSV for intelligent matching
        """
        self.db_path = db_path
        self.conn = None
        self.llm_extractor = None
        self.contacts_csv_path = contacts_csv_path
        self.contacts_lookup = {}  # Maps identifiers to contact records
        self._initialize_database()
        self._initialize_llm()
        self._load_contacts()
    
    def _initialize_database(self):
        """Create database connection and schema"""
        logger.info(f"Initializing database at {self.db_path}")
        
        # Remove existing database if it exists (fresh start)
        if os.path.exists(self.db_path):
            logger.info("Removing existing database for fresh import")
            os.remove(self.db_path)
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # Create schema
        self._create_schema()
        logger.info("Database schema created successfully")
    
    def _initialize_llm(self):
        """Initialize LLM extractor for intelligent message parsing"""
        try:
            logger.info("Initializing LLM extractor for message parsing...")
            self.llm_extractor = LLMExtractor(model_name="gpt4all")
            logger.info("LLM extractor ready")
        except Exception as e:
            logger.warning(f"Could not initialize LLM: {e}")
            logger.warning("Falling back to regex-based parsing")
            self.llm_extractor = None
    
    def _load_contacts(self):
        """Load contacts from CSV for intelligent matching"""
        if not self.contacts_csv_path or not os.path.exists(self.contacts_csv_path):
            logger.info("No contacts CSV provided or file not found")
            return
        
        logger.info(f"Loading contacts from: {self.contacts_csv_path}")
        
        try:
            with open(self.contacts_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('Name', '').strip()
                    email = row.get('Email', '').strip()
                    phone = row.get('Phone', '').strip()
                    organization = row.get('Organization', '').strip()
                    
                    # Skip empty rows
                    if not name and not email and not phone:
                        continue
                    
                    # Use organization as name if name is missing
                    display_name = name if name else organization
                    
                    # Normalize phone numbers (remove formatting)
                    normalized_phone = self._normalize_phone(phone)
                    
                    # Create lookup entries for all identifiers
                    contact_record = {
                        'display_name': display_name,
                        'email': email.lower() if email else None,
                        'phone': normalized_phone,
                        'organization': organization
                    }
                    
                    # Index by email
                    if email:
                        self.contacts_lookup[f"email:{email.lower()}"] = contact_record
                    
                    # Index by phone
                    if normalized_phone:
                        self.contacts_lookup[f"phone:{normalized_phone}"] = contact_record
                    
                    # Index by original phone format too
                    if phone and phone != normalized_phone:
                        self.contacts_lookup[f"phone:{phone}"] = contact_record
            
            logger.info(f"Loaded {len(self.contacts_lookup)} contact identifiers")
        
        except Exception as e:
            logger.error(f"Failed to load contacts CSV: {e}")
    
    def _normalize_phone(self, phone: str) -> Optional[str]:
        """Normalize phone number to standard format"""
        if not phone:
            return None
        
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Add + if it's a long number without country code
        if cleaned.isdigit():
            # US number
            if len(cleaned) == 10:
                return f"+1{cleaned}"
            # International without +
            elif len(cleaned) == 11 and cleaned.startswith('1'):
                return f"+{cleaned}"
            elif len(cleaned) > 10:
                return f"+{cleaned}"
        
        # Already has + or is short
        if cleaned.startswith('+'):
            return cleaned
        
        return phone  # Return original if can't normalize
    
    def _create_schema(self):
        """Create all database tables, views, and triggers"""
        
        # 1. Contacts table
        self.conn.execute("""
            CREATE TABLE contacts (
                contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT,
                email TEXT,
                phone TEXT,
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                first_seen TIMESTAMP,
                last_seen TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                is_me BOOLEAN DEFAULT 0,
                is_validated BOOLEAN DEFAULT 0,
                UNIQUE(platform, platform_id)
            )
        """)
        
        # Create index for contacts
        self.conn.execute("""
            CREATE INDEX idx_contacts_platform 
            ON contacts(platform, platform_id)
        """)
        self.conn.execute("""
            CREATE INDEX idx_contacts_email 
            ON contacts(email) WHERE email IS NOT NULL
        """)
        self.conn.execute("""
            CREATE INDEX idx_contacts_phone 
            ON contacts(phone) WHERE phone IS NOT NULL
        """)
        
        # 2. Conversations table
        self.conn.execute("""
            CREATE TABLE conversations (
                conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_name TEXT,
                platform TEXT NOT NULL,
                thread_id TEXT,
                first_message_at TIMESTAMP,
                last_message_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                is_group BOOLEAN DEFAULT 0,
                participant_count INTEGER DEFAULT 2,
                is_important BOOLEAN DEFAULT 0,
                category TEXT
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX idx_conversations_platform 
            ON conversations(platform, thread_id)
        """)
        self.conn.execute("""
            CREATE INDEX idx_conversations_last_message 
            ON conversations(last_message_at DESC)
        """)
        
        # 3. Messages table
        self.conn.execute("""
            CREATE TABLE messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                platform_message_id TEXT NOT NULL,
                conversation_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                timezone TEXT,
                body TEXT NOT NULL,
                subject TEXT,
                is_read BOOLEAN,
                is_starred BOOLEAN,
                is_sent BOOLEAN DEFAULT 1,
                is_deleted BOOLEAN DEFAULT 0,
                is_reply BOOLEAN DEFAULT 0,
                reply_to_message_id INTEGER,
                has_attachment BOOLEAN DEFAULT 0,
                is_tapback BOOLEAN DEFAULT 0,
                tapback_type TEXT,
                raw_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, platform_message_id),
                FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id),
                FOREIGN KEY(sender_id) REFERENCES contacts(contact_id),
                FOREIGN KEY(reply_to_message_id) REFERENCES messages(message_id)
            )
        """)
        
        # Indexes for messages
        self.conn.execute("""
            CREATE INDEX idx_messages_timestamp 
            ON messages(timestamp DESC)
        """)
        self.conn.execute("""
            CREATE INDEX idx_messages_conversation 
            ON messages(conversation_id, timestamp DESC)
        """)
        self.conn.execute("""
            CREATE INDEX idx_messages_sender 
            ON messages(sender_id, timestamp DESC)
        """)
        self.conn.execute("""
            CREATE INDEX idx_messages_platform 
            ON messages(platform, platform_message_id)
        """)
        
        # 4. Conversation participants table
        self.conn.execute("""
            CREATE TABLE conversation_participants (
                participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                contact_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP,
                left_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                UNIQUE(conversation_id, contact_id),
                FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id),
                FOREIGN KEY(contact_id) REFERENCES contacts(contact_id)
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX idx_participants_contact 
            ON conversation_participants(contact_id)
        """)
        self.conn.execute("""
            CREATE INDEX idx_participants_conversation 
            ON conversation_participants(conversation_id)
        """)
        
        # 5. Calendar events table (enhanced schema)
        self.conn.execute("""
            CREATE TABLE calendar_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                event_start TIMESTAMP NOT NULL,
                event_end TIMESTAMP,
                event_duration_seconds INTEGER,
                event_location TEXT,
                event_status TEXT DEFAULT 'confirmed',
                event_timezone TEXT,
                is_recurring BOOLEAN DEFAULT 0,
                recurrence_pattern TEXT,
                calendar_name TEXT,
                organizer_email TEXT,
                attendee_count INTEGER DEFAULT 0,
                has_video_conference BOOLEAN DEFAULT 0,
                video_conference_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(message_id),
                FOREIGN KEY(message_id) REFERENCES messages(message_id)
            )
        """)
        
        # Indexes for calendar events
        self.conn.execute("""
            CREATE INDEX idx_calendar_events_start 
            ON calendar_events(event_start DESC)
        """)
        self.conn.execute("""
            CREATE INDEX idx_calendar_events_status 
            ON calendar_events(event_status)
        """)
        self.conn.execute("""
            CREATE INDEX idx_calendar_events_location 
            ON calendar_events(event_location) WHERE event_location IS NOT NULL
        """)
        self.conn.execute("""
            CREATE INDEX idx_calendar_events_recurring 
            ON calendar_events(is_recurring) WHERE is_recurring = 1
        """)
        
        # 6. Message tags table
        self.conn.execute("""
            CREATE TABLE message_tags (
                tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                tag_name TEXT NOT NULL,
                tag_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(message_id) REFERENCES messages(message_id)
            )
        """)
        
        # Create triggers
        self._create_triggers()
        
        # Create views
        self._create_views()
        
        self.conn.commit()
    
    def _create_triggers(self):
        """Create database triggers for automatic updates"""
        
        # Update conversation timestamps
        self.conn.execute("""
            CREATE TRIGGER update_conversation_timestamps
            AFTER INSERT ON messages
            BEGIN
                UPDATE conversations 
                SET 
                    last_message_at = NEW.timestamp,
                    message_count = message_count + 1
                WHERE conversation_id = NEW.conversation_id;
                
                UPDATE conversations 
                SET first_message_at = COALESCE(first_message_at, NEW.timestamp)
                WHERE conversation_id = NEW.conversation_id;
            END
        """)
        
        # Update contact statistics
        self.conn.execute("""
            CREATE TRIGGER update_contact_stats
            AFTER INSERT ON messages
            BEGIN
                UPDATE contacts 
                SET 
                    last_seen = MAX(COALESCE(last_seen, '1970-01-01'), NEW.timestamp),
                    first_seen = MIN(COALESCE(first_seen, '9999-12-31'), NEW.timestamp),
                    message_count = message_count + 1
                WHERE contact_id = NEW.sender_id;
            END
        """)
        
        # Detect group conversations
        self.conn.execute("""
            CREATE TRIGGER detect_group_conversation
            AFTER INSERT ON conversation_participants
            BEGIN
                UPDATE conversations
                SET 
                    is_group = (SELECT COUNT(*) FROM conversation_participants 
                               WHERE conversation_id = NEW.conversation_id) > 2,
                    participant_count = (SELECT COUNT(*) FROM conversation_participants 
                                        WHERE conversation_id = NEW.conversation_id)
                WHERE conversation_id = NEW.conversation_id;
            END
        """)
    
    def _create_views(self):
        """Create useful database views"""
        
        # Recent conversations view
        self.conn.execute("""
            CREATE VIEW recent_conversations AS
            SELECT 
                c.conversation_id,
                c.conversation_name,
                c.platform,
                c.last_message_at,
                c.message_count,
                c.is_group,
                c.participant_count,
                GROUP_CONCAT(co.display_name, ', ') AS participant_names
            FROM conversations c
            LEFT JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
            LEFT JOIN contacts co ON cp.contact_id = co.contact_id
            WHERE co.is_me = 0 OR co.is_me IS NULL
            GROUP BY c.conversation_id
            ORDER BY c.last_message_at DESC
        """)
        
        # Contact statistics view
        self.conn.execute("""
            CREATE VIEW contact_statistics AS
            SELECT 
                co.contact_id,
                co.display_name,
                co.email,
                co.phone,
                co.platform,
                COUNT(DISTINCT m.message_id) AS total_messages,
                COUNT(DISTINCT CASE WHEN m.is_sent = 1 THEN m.message_id END) AS sent_count,
                COUNT(DISTINCT CASE WHEN m.is_sent = 0 THEN m.message_id END) AS received_count,
                COUNT(DISTINCT m.conversation_id) AS conversation_count,
                MIN(m.timestamp) AS first_message,
                MAX(m.timestamp) AS last_message
            FROM contacts co
            LEFT JOIN messages m ON co.contact_id = m.sender_id
            GROUP BY co.contact_id
            ORDER BY total_messages DESC
        """)
        
        # Platform summary view
        self.conn.execute("""
            CREATE VIEW platform_summary AS
            SELECT 
                platform,
                COUNT(DISTINCT message_id) AS total_messages,
                COUNT(DISTINCT conversation_id) AS total_conversations,
                COUNT(DISTINCT sender_id) AS unique_contacts,
                MIN(timestamp) AS first_message,
                MAX(timestamp) AS last_message,
                AVG(LENGTH(body)) AS avg_message_length,
                SUM(CASE WHEN is_starred = 1 THEN 1 ELSE 0 END) AS starred_count
            FROM messages
            GROUP BY platform
        """)
    
    def parse_imessage_html(self, html_path: str) -> List[Dict[str, Any]]:
        """
        Parse iMessage HTML export file
        
        Args:
            html_path: Path to HTML export file
            
        Returns:
            List of message dictionaries
        """
        logger.info(f"Parsing iMessage HTML: {html_path}")
        
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read HTML file: {e}")
            return []
        
        messages = []
        
        # Extract messages using regex patterns
        # Pattern for message blocks
        message_pattern = r'<div class="message">.*?</div></div>'
        
        matches = re.finditer(message_pattern, html_content, re.DOTALL)
        
        for match in matches:
            message_html = match.group(0)
            
            try:
                # Extract timestamp
                timestamp_match = re.search(r'<a[^>]*title="[^"]*">(.+?)</a>', message_html)
                if timestamp_match:
                    timestamp_str = timestamp_match.group(1)
                    timestamp = self._parse_timestamp(timestamp_str)
                else:
                    timestamp = datetime.now()
                
                # Extract sender
                sender_match = re.search(r'<span class="sender">(.+?)</span>', message_html)
                sender = sender_match.group(1) if sender_match else "Unknown"
                
                # Determine if sent or received
                is_sent = 'class="sent' in message_html
                is_imessage = 'iMessage' in message_html
                
                # Extract message body
                body_match = re.search(r'<span class="bubble">(.+?)</span>', message_html, re.DOTALL)
                body = body_match.group(1).strip() if body_match else ""
                
                # Clean HTML entities
                body = self._decode_html_entities(body)
                
                # Skip empty messages and messages that are only attachments
                if not body:
                    continue
                
                # Skip messages that are ONLY attachments (to save space)
                is_attachment_only = (body.startswith('[') and 'Attachment' in body and len(body) < 100)
                if is_attachment_only:
                    continue
                
                # Extract message GUID if available
                guid_match = re.search(r'href="sms://[^"]*message-guid=([^"]+)"', message_html)
                platform_message_id = guid_match.group(1) if guid_match else f"auto_{len(messages)}"
                
                # Detect tapbacks
                is_tapback = any(tapback in body for tapback in 
                                ['[Tapback:', '[Attachment]', '[Apple Pay]', '[Location]'])
                tapback_type = None
                if '[Tapback:' in body:
                    tap_type_match = re.search(r'\[Tapback:\s*(.+?)\]', body)
                    if tap_type_match:
                        tapback_type = tap_type_match.group(1).strip()
                
                messages.append({
                    'timestamp': timestamp,
                    'sender': sender,
                    'body': body,
                    'is_sent': is_sent,
                    'is_imessage': is_imessage,
                    'platform_message_id': platform_message_id,
                    'is_tapback': is_tapback,
                    'tapback_type': tapback_type,
                    'raw_data': {'html': message_html}
                })
                
            except Exception as e:
                logger.warning(f"Error parsing message: {e}")
                continue
        
        logger.info(f"Extracted {len(messages)} messages from {html_path}")
        return messages
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse iMessage timestamp string"""
        try:
            # Try common formats
            formats = [
                '%b %d, %Y  %I:%M:%S %p',  # Oct 14, 2025  8:30:21 PM
                '%Y-%m-%d %H:%M:%S',       # 2025-10-14 20:30:21
                '%b %d, %Y %I:%M %p',      # Oct 14, 2025 8:30 PM
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
            
            # Fallback to now
            logger.warning(f"Could not parse timestamp: {timestamp_str}")
            return datetime.now()
            
        except Exception as e:
            logger.error(f"Error parsing timestamp: {e}")
            return datetime.now()
    
    def _decode_html_entities(self, text: str) -> str:
        """Decode HTML entities in text"""
        # Common HTML entities
        entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&#8217;': "'",
            '&#8211;': '–',
            '&#8212;': '—',
        }
        
        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)
        
        return text.strip()
    
    def process_imessage_exports(self, export_dir: str = "IMESSAGE_EXPORT_TEMP"):
        """
        Process all iMessage HTML exports in a directory
        
        Args:
            export_dir: Directory containing HTML exports
        """
        logger.info(f"Processing iMessage exports from: {export_dir}")
        
        export_path = Path(export_dir)
        if not export_path.exists():
            logger.error(f"Export directory not found: {export_dir}")
            return
        
        # Find all HTML files
        html_files = list(export_path.glob("*.html"))
        logger.info(f"Found {len(html_files)} HTML export files")
        
        # Group by conversation (filename without extension is conversation identifier)
        conversations = defaultdict(list)
        
        for html_file in html_files:
            # Extract conversation identifier from filename
            conv_id = html_file.stem
            conversations[conv_id].append(html_file)
        
        logger.info(f"Processing {len(conversations)} conversations")
        
        # Process each conversation
        for conv_id, files in conversations.items():
            logger.info(f"Processing conversation: {conv_id}")
            
            # Parse all messages in this conversation
            all_messages = []
            for html_file in files:
                messages = self.parse_imessage_html(str(html_file))
                all_messages.extend(messages)
            
            if not all_messages:
                logger.warning(f"No messages found in conversation: {conv_id}")
                continue
            
            # Sort by timestamp
            all_messages.sort(key=lambda m: m['timestamp'])
            
            # Extract participants from first message and filename
            participants = self._extract_participants(conv_id, all_messages)
            
            # Create conversation in database
            conv_db_id = self._create_conversation(conv_id, participants, all_messages)
            
            # Import messages
            self._import_messages(conv_db_id, participants, all_messages)
            
            logger.info(f"Imported {len(all_messages)} messages for conversation {conv_id}")
        
        self.conn.commit()
    
    def _extract_participants(self, conv_id: str, messages: List[Dict]) -> List[Dict[str, Any]]:
        """Extract participants from conversation identifier and messages with intelligent contact matching"""
        participants = []
        
        # Extract from filename (e.g., "+14159408750, +16503873944" or "Group Name")
        parts = conv_id.split(', ')
        
        for part in parts:
            part = part.strip()
            
            # Try to find in contacts database first
            matched_contact = None
            
            if '@' in part:
                # Email - try lookup
                email_key = f"email:{part.lower()}"
                if email_key in self.contacts_lookup:
                    matched_contact = self.contacts_lookup[email_key]
            elif part.startswith('+') or part.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                # Phone number - normalize and try lookup
                normalized = self._normalize_phone(part)
                if normalized:
                    phone_key = f"phone:{normalized}"
                    if phone_key in self.contacts_lookup:
                        matched_contact = self.contacts_lookup[phone_key]
                
                # Also try original format
                if not matched_contact:
                    phone_key = f"phone:{part}"
                    if phone_key in self.contacts_lookup:
                        matched_contact = self.contacts_lookup[phone_key]
            
            if matched_contact:
                # Use matched contact info
                participants.append({
                    'platform_id': part,
                    'phone': matched_contact.get('phone'),
                    'email': matched_contact.get('email'),
                    'display_name': matched_contact.get('display_name') or part,
                    'platform': 'imessage',
                    'matched_from_contacts': True
                })
            else:
                # No match found, create basic participant
                if part.startswith('+') or part.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isdigit():
                    # Phone number
                    participants.append({
                        'platform_id': part,
                        'phone': part,
                        'display_name': part,
                        'platform': 'imessage',
                        'email': None
                    })
                elif '@' in part:
                    # Email
                    participants.append({
                        'platform_id': part,
                        'email': part,
                        'display_name': part,
                        'platform': 'imessage',
                        'phone': None
                    })
                else:
                    # Group name or unknown
                    participants.append({
                        'platform_id': part,
                        'display_name': part,
                        'platform': 'imessage',
                        'email': None,
                        'phone': None
                    })
        
        # Add "Me" as a participant if we sent any messages
        if any(m.get('is_sent') for m in messages):
            participants.append({
                'platform_id': 'me',
                'display_name': 'Me',
                'platform': 'imessage',
                'email': None,
                'phone': None,
                'is_me': True
            })
        
        return participants
    
    def _create_conversation(self, conv_id: str, participants: List[Dict], messages: List[Dict]) -> int:
        """Create conversation record and return ID"""
        # Determine conversation name
        if len(participants) > 2:
            conv_name = conv_id.split(',')[0]  # Use first part as name
        else:
            # Extract other participant name
            other_participants = [p for p in participants if not p.get('is_me')]
            if other_participants:
                conv_name = other_participants[0]['display_name']
            else:
                conv_name = conv_id
        
        # First and last timestamps
        timestamps = [m['timestamp'] for m in messages if m.get('timestamp')]
        first_ts = min(timestamps) if timestamps else None
        last_ts = max(timestamps) if timestamps else None
        
        cursor = self.conn.execute("""
            INSERT INTO conversations (
                conversation_name, platform, thread_id, 
                first_message_at, last_message_at,
                is_group, participant_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            conv_name,
            'imessage',
            conv_id,
            first_ts.isoformat() if first_ts else None,
            last_ts.isoformat() if last_ts else None,
            len(participants) > 2,
            len(participants)
        ))
        
        return cursor.lastrowid
    
    def _get_or_create_contact(self, participant: Dict[str, Any]) -> int:
        """Get existing contact or create new one, return contact_id"""
        
        # Try to find existing contact
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = ? AND platform_id = ?
        """, (participant['platform'], participant['platform_id']))
        
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        # Create new contact
        cursor = self.conn.execute("""
            INSERT INTO contacts (
                display_name, email, phone, platform, platform_id, is_me
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            participant['display_name'],
            participant.get('email'),
            participant.get('phone'),
            participant['platform'],
            participant['platform_id'],
            participant.get('is_me', False)
        ))
        
        return cursor.lastrowid
    
    def _import_messages(self, conv_id: int, participants: List[Dict], messages: List[Dict]):
        """Import messages into database"""
        
        # First, ensure all participants exist
        participant_ids = {}
        for p in participants:
            contact_id = self._get_or_create_contact(p)
            participant_ids[p['platform_id']] = contact_id
            
            # Add to conversation participants
            self.conn.execute("""
                INSERT OR IGNORE INTO conversation_participants 
                (conversation_id, contact_id, role)
                VALUES (?, ?, ?)
            """, (conv_id, contact_id, 'member'))
        
        # Import each message
        for msg in messages:
            # Determine sender_id
            sender_name = msg.get('sender', 'Unknown')
            sender_id = None
            
            # Match sender to participant
            if sender_name == 'Me' or msg.get('is_sent'):
                sender_id = participant_ids.get('me')
            else:
                # Try to match by platform_id
                for pid, cid in participant_ids.items():
                    if pid in sender_name or sender_name in pid:
                        sender_id = cid
                        break
            
            # Fallback: create sender contact if not found
            if not sender_id:
                # Try to find or create sender contact
                cursor = self.conn.execute("""
                    SELECT contact_id FROM contacts 
                    WHERE platform = ? AND platform_id = ?
                """, ('imessage', f"sender_{sender_name}"))
                row = cursor.fetchone()
                if row:
                    sender_id = row['contact_id']
                else:
                    # Create sender contact
                    cursor = self.conn.execute("""
                        INSERT INTO contacts (display_name, platform, platform_id)
                        VALUES (?, ?, ?)
                    """, (sender_name, 'imessage', f"sender_{sender_name}"))
                    sender_id = cursor.lastrowid
            
            # Insert message
            try:
                cursor = self.conn.execute("""
                    INSERT INTO messages (
                        platform, platform_message_id, conversation_id, sender_id,
                        timestamp, body, is_sent, is_tapback, tapback_type,
                        raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'imessage',
                    msg['platform_message_id'],
                    conv_id,
                    sender_id,
                    msg['timestamp'].isoformat(),
                    msg['body'],
                    msg.get('is_sent', True),
                    msg.get('is_tapback', False),
                    msg.get('tapback_type'),
                    json.dumps(msg.get('raw_data', {}))
                ))
            except sqlite3.IntegrityError as e:
                logger.warning(f"Duplicate message skipped: {e}")
    
    def import_unified_ledger(self, ledger_path: str):
        """
        Import from existing unified ledger JSON
        
        Args:
            ledger_path: Path to unified_ledger.json
        """
        logger.info(f"Importing unified ledger from: {ledger_path}")
        
        try:
            with open(ledger_path, 'r', encoding='utf-8') as f:
                ledger_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read unified ledger: {e}")
            return
        
        messages = ledger_data.get('messages', [])
        logger.info(f"Found {len(messages)} messages in unified ledger")
        
        # TODO: Implement full ledger import
        logger.info("Unified ledger import not yet fully implemented")
    
    def generate_report(self) -> str:
        """
        Generate a comprehensive report of the database contents
        
        Returns:
            Formatted report string
        """
        logger.info("Generating database report...")
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CHAT DATABASE REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Overall statistics
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM messages")
        total_messages = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM conversations")
        total_conversations = cursor.fetchone()['count']
        
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM contacts")
        total_contacts = cursor.fetchone()['count']
        
        report_lines.append(f"Total Messages:     {total_messages:>10,}")
        report_lines.append(f"Total Conversations: {total_conversations:>8,}")
        report_lines.append(f"Total Contacts:     {total_contacts:>10,}")
        report_lines.append("")
        
        # Platform summary
        report_lines.append("-" * 80)
        report_lines.append("PLATFORM SUMMARY")
        report_lines.append("-" * 80)
        
        cursor = self.conn.execute("SELECT * FROM platform_summary ORDER BY total_messages DESC")
        for row in cursor:
            report_lines.append(f"\n{row['platform'].upper()}:")
            report_lines.append(f"  Messages:       {row['total_messages']:>8,}")
            report_lines.append(f"  Conversations:  {row['total_conversations']:>8,}")
            report_lines.append(f"  Unique Contacts: {row['unique_contacts']:>7,}")
            if row['first_message']:
                report_lines.append(f"  First Message:  {row['first_message']}")
            if row['last_message']:
                report_lines.append(f"  Last Message:   {row['last_message']}")
        
        report_lines.append("")
        
        # Top conversations
        report_lines.append("-" * 80)
        report_lines.append("TOP 20 MOST ACTIVE CONVERSATIONS")
        report_lines.append("-" * 80)
        
        cursor = self.conn.execute("""
            SELECT * FROM recent_conversations 
            ORDER BY message_count DESC 
            LIMIT 20
        """)
        
        for idx, row in enumerate(cursor, 1):
            report_lines.append(f"\n{idx}. {row['conversation_name']}")
            report_lines.append(f"   Platform: {row['platform']}")
            report_lines.append(f"   Messages: {row['message_count']:,}")
            report_lines.append(f"   Participants: {row['participant_count']}")
            if row['last_message_at']:
                report_lines.append(f"   Last: {row['last_message_at']}")
            if row['participant_names']:
                report_lines.append(f"   People: {row['participant_names']}")
        
        report_lines.append("")
        
        # Top contacts
        report_lines.append("-" * 80)
        report_lines.append("TOP 20 MOST MESSAGED CONTACTS")
        report_lines.append("-" * 80)
        
        cursor = self.conn.execute("""
            SELECT * FROM contact_statistics 
            ORDER BY total_messages DESC 
            LIMIT 20
        """)
        
        for idx, row in enumerate(cursor, 1):
            report_lines.append(f"\n{idx}. {row['display_name'] or '(Unknown)'}")
            report_lines.append(f"   Platform: {row['platform']}")
            report_lines.append(f"   Total: {row['total_messages']:,} messages")
            report_lines.append(f"   Sent: {row['sent_count']:,} | Received: {row['received_count']:,}")
            if row['phone']:
                report_lines.append(f"   Phone: {row['phone']}")
            if row['email']:
                report_lines.append(f"   Email: {row['email']}")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        report = '\n'.join(report_lines)
        
        # Also save to file
        report_path = "data/database/database_report.txt"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Report saved to {report_path}")
        
        return report
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """Main execution function"""
    logger.info("Starting chat database creation...")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Create SQLite database from chat exports")
    parser.add_argument('--export-dir', default='data/exports/IMESSAGE_EXPORT_TEMP',
                       help='Directory containing iMessage HTML exports')
    parser.add_argument('--db-path', default='data/database/chats.db',
                       help='Path to SQLite database file')
    parser.add_argument('--ledger', help='Path to unified ledger JSON file')
    parser.add_argument('--contacts-csv', default='data/exports/CONTACTS_EXPORT/contacts_database.csv',
                       help='Path to contacts CSV for intelligent matching')
    
    args = parser.parse_args()
    
    # Create database
    creator = ChatDatabaseCreator(db_path=args.db_path, contacts_csv_path=args.contacts_csv)
    
    try:
        # Import from iMessage exports
        if Path(args.export_dir).exists():
            creator.process_imessage_exports(args.export_dir)
        else:
            logger.warning(f"Export directory not found: {args.export_dir}")
        
        # Import from unified ledger if provided
        if args.ledger and Path(args.ledger).exists():
            creator.import_unified_ledger(args.ledger)
        
        # Generate report
        report = creator.generate_report()
        print("\n" + report)
        
        logger.info("Database creation complete!")
        logger.info(f"Database saved to: {args.db_path}")
        
    finally:
        creator.close()


if __name__ == '__main__':
    main()

