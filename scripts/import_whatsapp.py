#!/usr/bin/env python3
"""
Import WhatsApp messages into the existing chat database using WhatsApp Chat Exporter

This script:
1. Uses the WhatsApp Chat Exporter to parse WhatsApp data
2. Imports messages into the existing normalized database structure
3. Supports both iOS and Android WhatsApp backups
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src and WhatsApp Exporter to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / "_archived_tools" / "WhatsApp-Chat-Exporter"))

from Whatsapp_Chat_Exporter import android_handler, ios_handler
from Whatsapp_Chat_Exporter.data_model import ChatCollection, ChatStore, Message
from Whatsapp_Chat_Exporter.utility import Device, APPLE_TIME
from utils.logger import get_logger

logger = get_logger('whatsapp_importer')


class WhatsAppDatabaseImporter:
    """Import WhatsApp messages into existing chat database"""
    
    def __init__(self, db_path: str, chat_exporter_data: ChatCollection):
        """
        Initialize importer with existing database
        
        Args:
            db_path: Path to SQLite database
            chat_exporter_data: ChatCollection from WhatsApp Chat Exporter
        """
        self.db_path = db_path
        self.chat_data = chat_exporter_data
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
    
    def import_all(self):
        """Import all WhatsApp conversations and messages"""
        logger.info("Starting WhatsApp import...")
        
        if not self.conn:
            self.connect()
        
        total_chats = len(self.chat_data)
        logger.info(f"Processing {total_chats} conversations")
        
        for idx, (chat_id, chat_store) in enumerate(self.chat_data.items(), 1):
            try:
                self.import_conversation(chat_id, chat_store)
                if idx % 10 == 0:
                    logger.info(f"Progress: {idx}/{total_chats} conversations")
            except Exception as e:
                logger.error(f"Error importing conversation {chat_id}: {e}")
                continue
        
        # Commit all changes
        self.conn.commit()
        logger.info("WhatsApp import complete!")
    
    def import_conversation(self, chat_id: str, chat_store: ChatStore):
        """Import a single WhatsApp conversation"""
        
        # Determine if group chat
        is_group = '@g.us' in chat_id or len(chat_store._messages) > 0
        
        # Get conversation name
        conv_name = chat_store.name or chat_id
        
        # Get first and last message timestamps
        messages_list = list(chat_store._messages.values())
        if not messages_list:
            logger.warning(f"No messages in conversation: {conv_name}")
            return
        
        # Sort by timestamp
        messages_list.sort(key=lambda m: m.timestamp if m.timestamp else 0)
        
        first_timestamp = datetime.fromtimestamp(messages_list[0].timestamp) if messages_list[0].timestamp else None
        last_timestamp = datetime.fromtimestamp(messages_list[-1].timestamp) if messages_list[-1].timestamp else None
        
        # Check if conversation already exists
        cursor = self.conn.execute("""
            SELECT conversation_id FROM conversations 
            WHERE platform = 'whatsapp' AND thread_id = ?
        """, (chat_id,))
        
        row = cursor.fetchone()
        if row:
            conv_db_id = row['conversation_id']
            logger.debug(f"Conversation {conv_name} already exists (ID: {conv_db_id})")
        else:
            # Create new conversation
            cursor = self.conn.execute("""
                INSERT INTO conversations (
                    conversation_name, platform, thread_id,
                    first_message_at, last_message_at,
                    is_group, participant_count, message_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conv_name,
                'whatsapp',
                chat_id,
                first_timestamp.isoformat() if first_timestamp else None,
                last_timestamp.isoformat() if last_timestamp else None,
                is_group,
                2,  # Will be updated when we process participants
                len(messages_list)
            ))
            conv_db_id = cursor.lastrowid
            logger.debug(f"Created conversation {conv_name} (ID: {conv_db_id})")
        
        # Import participants
        self.import_participants(conv_db_id, chat_id, chat_store, messages_list)
        
        # Import messages
        self.import_messages(conv_db_id, chat_id, messages_list)
    
    def import_participants(self, conv_db_id: int, chat_id: str, chat_store: ChatStore, messages: List[Message]):
        """Import conversation participants"""
        
        # Collect unique participants
        participants = set()
        me_participant = None
        
        for msg in messages:
            if msg.from_me:
                if not me_participant:
                    me_participant = 'me'
            else:
                # Extract sender info
                if msg.sender:
                    participants.add(msg.sender)
                elif chat_store.name:
                    participants.add(chat_store.name)
                else:
                    # Extract from chat_id
                    if '@s.whatsapp.net' in chat_id:
                        # Individual chat - extract phone number
                        phone = chat_id.split('@')[0]
                        participants.add(phone)
                    elif '@g.us' in chat_id:
                        # Group chat
                        participants.add(chat_id)
        
        # Add "Me" if we have sent messages
        all_participants = list(participants)
        if me_participant:
            all_participants.insert(0, 'me')
        
        logger.debug(f"Found {len(all_participants)} participants for conversation {chat_store.name}")
        
        # Create/get contact records and link to conversation
        for participant in all_participants:
            contact_id = self._get_or_create_whatsapp_contact(participant, chat_id, chat_store)
            
            # Link to conversation
            self.conn.execute("""
                INSERT OR IGNORE INTO conversation_participants 
                (conversation_id, contact_id, role)
                VALUES (?, ?, ?)
            """, (conv_db_id, contact_id, 'member'))
    
    def _get_or_create_whatsapp_contact(self, participant: str, chat_id: str, chat_store: ChatStore) -> int:
        """Get or create a WhatsApp contact, return contact_id"""
        
        # Determine platform_id and participant info
        is_me = participant == 'me'
        
        if is_me:
            platform_id = 'me'
            display_name = 'Me'
            phone = None
            email = None
        elif '@' in chat_id:
            # Extract from chat_id
            if '@s.whatsapp.net' in chat_id:
                phone = chat_id.split('@')[0]
                platform_id = chat_id
            elif '@g.us' in chat_id:
                phone = chat_id
                platform_id = chat_id
            else:
                phone = None
                platform_id = chat_id
            
            display_name = participant if participant else chat_store.name or phone
            email = None
        else:
            # Use participant as-is
            platform_id = participant
            display_name = participant
            phone = participant if participant.replace('+', '').isdigit() else None
            email = None
        
        # Check if contact exists
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = 'whatsapp' AND platform_id = ?
        """, (platform_id,))
        
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        # Create new contact
        cursor = self.conn.execute("""
            INSERT INTO contacts (
                display_name, phone, platform, platform_id, is_me
            ) VALUES (?, ?, ?, ?, ?)
        """, (display_name, phone, 'whatsapp', platform_id, is_me))
        
        return cursor.lastrowid
    
    def import_messages(self, conv_db_id: int, chat_id: str, messages: List[Message]):
        """Import messages for a conversation"""
        
        # Get contact IDs for this conversation
        cursor = self.conn.execute("""
            SELECT c.contact_id, c.platform_id, c.is_me
            FROM contacts c
            JOIN conversation_participants cp ON c.contact_id = cp.contact_id
            WHERE cp.conversation_id = ?
        """, (conv_db_id,))
        
        participants = {row['platform_id']: row['contact_id'] for row in cursor}
        me_contact_id = participants.get('me')
        
        imported_count = 0
        skipped_count = 0
        
        for msg in messages:
            try:
                # Determine sender
                if msg.from_me:
                    sender_id = me_contact_id
                else:
                    # Try to find sender
                    sender_id = None
                    
                    # Try by sender name
                    if msg.sender:
                        for pid, cid in participants.items():
                            if msg.sender in pid or pid in msg.sender:
                                sender_id = cid
                                break
                    
                    # Fallback: if individual chat, use other participant
                    if not sender_id and '@s.whatsapp.net' in chat_id:
                        other_participants = [cid for pid, cid in participants.items() if pid != 'me']
                        if other_participants:
                            sender_id = other_participants[0]
                    
                    # Final fallback: create contact
                    if not sender_id:
                        logger.warning(f"Could not determine sender for message in {chat_id}")
                        continue
                
                # Prepare message data
                message_body = self._extract_message_body(msg)
                platform_msg_id = str(msg.key_id) if msg.key_id else f"wa_{msg.timestamp}"
                
                # Convert timestamp
                if msg.timestamp:
                    # WhatsApp timestamps are in seconds (iOS uses Apple time)
                    if chat_store.type == Device.IOS:
                        # iOS uses Apple time (seconds since 2001-01-01)
                        unix_timestamp = msg.timestamp + APPLE_TIME
                    else:
                        # Android uses Unix timestamp (can be in milliseconds)
                        unix_timestamp = msg.timestamp / 1000 if msg.timestamp > 9999999999 else msg.timestamp
                    
                    msg_timestamp = datetime.fromtimestamp(unix_timestamp)
                else:
                    msg_timestamp = datetime.now()
                
                # Determine if reply
                is_reply = msg.reply is not None and msg.reply != ''
                reply_to_id = None
                
                # Insert message
                cursor = self.conn.execute("""
                    INSERT INTO messages (
                        platform, platform_message_id, conversation_id, sender_id,
                        timestamp, body, is_sent, has_attachment, is_reply,
                        raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'whatsapp',
                    platform_msg_id,
                    conv_db_id,
                    sender_id,
                    msg_timestamp.isoformat(),
                    message_body,
                    msg.from_me,
                    msg.media,
                    is_reply,
                    json.dumps(self._message_to_dict(msg))
                ))
                
                imported_count += 1
                
            except sqlite3.IntegrityError:
                skipped_count += 1
                logger.debug(f"Skipped duplicate message: {platform_msg_id}")
            except Exception as e:
                logger.warning(f"Error importing message: {e}")
                skipped_count += 1
        
        logger.debug(f"Imported {imported_count} messages, skipped {skipped_count} duplicates")
    
    def _extract_message_body(self, msg: Message) -> str:
        """Extract message body text, handling special cases"""
        
        if msg.data:
            # Already formatted text
            body = msg.data
        elif msg.meta:
            # Metadata message
            body = "[Metadata]"
        elif msg.media:
            # Media message
            if msg.caption:
                body = f"[Media] {msg.caption}"
            else:
                body = "[Media]"
        else:
            body = "[Empty message]"
        
        # Clean HTML tags if present
        if '<br>' in body:
            body = body.replace('<br>', ' ')
        
        return body[:10000]  # Limit length
    
    def _message_to_dict(self, msg: Message) -> Dict[str, Any]:
        """Convert Message object to dict for raw_data"""
        return {
            'from_me': msg.from_me,
            'timestamp': msg.timestamp,
            'key_id': msg.key_id,
            'data': msg.data,
            'sender': msg.sender,
            'media': msg.media,
            'meta': msg.meta,
            'caption': msg.caption,
            'reply': msg.reply,
            'sticker': msg.sticker,
            'mime': msg.mime
        }


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Import WhatsApp messages into chat database using WhatsApp Chat Exporter'
    )
    parser.add_argument(
        '--db', 
        default='chats.db',
        help='Path to SQLite database (default: chats.db)'
    )
    parser.add_argument(
        '--backup',
        help='Path to WhatsApp backup directory (Android) or backup file (iOS)'
    )
    parser.add_argument(
        '--ios',
        action='store_true',
        help='Process iOS backup'
    )
    parser.add_argument(
        '--android',
        action='store_true',
        help='Process Android backup'
    )
    parser.add_argument(
        '--msg-db',
        help='Path to message database (msgstore.db or iOS message DB)'
    )
    parser.add_argument(
        '--media',
        help='Path to media folder'
    )
    parser.add_argument(
        '--contacts-db',
        help='Path to contacts database (wa.db or ContactsV2.sqlite)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.backup and not args.msg_db:
        logger.error("Must provide either --backup or --msg-db")
        return 1
    
    if not args.ios and not args.android:
        logger.error("Must specify either --ios or --android")
        return 1
    
    # Initialize WhatsApp Chat Exporter handlers
    logger.info("Initializing WhatsApp Chat Exporter...")
    
    chat_data = ChatCollection()
    
    try:
        if args.ios:
            # iOS backup
            logger.info("Processing iOS WhatsApp backup...")
            
            if not args.msg_db:
                logger.error("--msg-db required for iOS")
                return 1
            
            # Import contacts module for iOS
            import sqlite3
            conn = sqlite3.connect(args.msg_db)
            conn.row_factory = sqlite3.Row
            
            # Process contacts
            if args.contacts_db:
                ios_handler.contacts(conn, chat_data)
            
            # Process messages
            ios_handler.messages(conn, chat_data, args.media or '.', 0, None, (None, None), True)
            
            conn.close()
            
        else:
            # Android backup
            logger.info("Processing Android WhatsApp backup...")
            
            if not args.msg_db:
                logger.error("--msg-db required for Android")
                return 1
            
            import sqlite3
            conn = sqlite3.connect(args.msg_db)
            conn.row_factory = sqlite3.Row
            
            # Process contacts
            if args.contacts_db:
                android_handler.contacts(conn, chat_data, None)
            
            # Process messages
            android_handler.messages(conn, chat_data, args.media or '.', 0, None, (None, None), True)
            
            conn.close()
        
        logger.info(f"Exported {len(chat_data)} conversations from WhatsApp")
        
        # Import into database
        importer = WhatsAppDatabaseImporter(args.db, chat_data)
        importer.import_all()
        importer.close()
        
        logger.info("WhatsApp import completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"WhatsApp import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

