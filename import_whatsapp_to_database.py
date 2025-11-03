#!/usr/bin/env python3
"""
Import WhatsApp messages into the existing chat database using WhatsApp Chat Exporter

This script:
1. Uses the WhatsApp Chat Exporter to parse WhatsApp data from macOS
2. Imports messages into the existing normalized database structure
3. Supports iOS/macOS WhatsApp databases
"""
import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root and WhatsApp Exporter to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "_archived_tools" / "WhatsApp-Chat-Exporter"))

from Whatsapp_Chat_Exporter import ios_handler
from Whatsapp_Chat_Exporter.data_model import ChatCollection, ChatStore, Message
from Whatsapp_Chat_Exporter.utility import Device, APPLE_TIME

# Simple logger
class Logger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def debug(self, msg): pass
logger = Logger()


class WhatsAppDatabaseImporter:
    """Import WhatsApp messages into existing chat database"""
    
    def __init__(self, db_path: str, chat_exporter_data: ChatCollection):
        """Initialize importer with existing database"""
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
        
        self.conn.commit()
        logger.info("WhatsApp import complete!")
    
    def import_conversation(self, chat_id: str, chat_store: ChatStore):
        """Import a single WhatsApp conversation"""
        is_group = '@g.us' in chat_id
        conv_name = chat_store.name or chat_id
        messages_list = list(chat_store._messages.values())
        
        if not messages_list:
            logger.warning(f"No messages in conversation: {conv_name}")
            return
        
        messages_list.sort(key=lambda m: m.timestamp if m.timestamp else 0)
        
        # Count participants before importing - filter out large groups (>7 participants)
        participant_count = self._count_participants(chat_id, chat_store, messages_list)
        if participant_count > 7:
            logger.info(f"Skipping large WhatsApp group '{conv_name}' with {participant_count} participants (limit: 7)")
            return
        
        first_timestamp = datetime.fromtimestamp(messages_list[0].timestamp) if messages_list[0].timestamp else None
        last_timestamp = datetime.fromtimestamp(messages_list[-1].timestamp) if messages_list[-1].timestamp else None
        
        # Check if conversation exists
        cursor = self.conn.execute("""
            SELECT conversation_id FROM conversations 
            WHERE platform = 'whatsapp' AND thread_id = ?
        """, (chat_id,))
        row = cursor.fetchone()
        if row:
            conv_db_id = row['conversation_id']
            logger.debug(f"Conversation {conv_name} exists (ID: {conv_db_id})")
        else:
            cursor = self.conn.execute("""
                INSERT INTO conversations (
                    conversation_name, platform, thread_id,
                    first_message_at, last_message_at,
                    is_group, participant_count, message_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (conv_name, 'whatsapp', chat_id,
                  first_timestamp.isoformat() if first_timestamp else None,
                  last_timestamp.isoformat() if last_timestamp else None,
                  is_group, 2, len(messages_list)))
            conv_db_id = cursor.lastrowid
            logger.debug(f"Created conversation {conv_name}")
        
        # Import participants and messages
        self.import_participants(conv_db_id, chat_id, chat_store, messages_list)
        self.import_messages(conv_db_id, chat_id, messages_list)
    
    def _count_participants(self, chat_id: str, chat_store: ChatStore, messages: List[Message]) -> int:
        """Count unique participants in a conversation"""
        participants = set()
        me_participant = None
        
        for msg in messages:
            if msg.from_me:
                if not me_participant:
                    me_participant = 'me'
            else:
                if msg.sender:
                    participants.add(msg.sender)
                elif chat_store.name:
                    participants.add(chat_store.name)
                elif '@s.whatsapp.net' in chat_id:
                    phone = chat_id.split('@')[0]
                    participants.add(phone)
                elif '@g.us' in chat_id:
                    participants.add(chat_id)
        
        total = len(participants)
        if me_participant:
            total += 1
        
        return total
    
    def import_participants(self, conv_db_id: int, chat_id: str, chat_store: ChatStore, messages: List[Message]):
        """Import conversation participants"""
        participants = set()
        me_participant = None
        
        for msg in messages:
            if msg.from_me:
                if not me_participant:
                    me_participant = 'me'
            else:
                if msg.sender:
                    participants.add(msg.sender)
                elif chat_store.name:
                    participants.add(chat_store.name)
                elif '@s.whatsapp.net' in chat_id:
                    phone = chat_id.split('@')[0]
                    participants.add(phone)
                elif '@g.us' in chat_id:
                    participants.add(chat_id)
        
        all_participants = list(participants)
        if me_participant:
            all_participants.insert(0, 'me')
        
        for participant in all_participants:
            contact_id = self._get_or_create_whatsapp_contact(participant, chat_id, chat_store)
            self.conn.execute("""
                INSERT OR IGNORE INTO conversation_participants 
                (conversation_id, contact_id, role) VALUES (?, ?, ?)
            """, (conv_db_id, contact_id, 'member'))
    
    def _get_or_create_whatsapp_contact(self, participant: str, chat_id: str, chat_store: ChatStore) -> int:
        """Get or create WhatsApp contact"""
        is_me = participant == 'me'
        
        # Initialize defaults
        platform_id = None
        display_name = None
        phone = None
        
        if is_me:
            platform_id = 'me'
            display_name = 'Me'
            phone = None
        elif '@' in chat_id:
            if '@s.whatsapp.net' in chat_id:
                phone = chat_id.split('@')[0]
                platform_id = chat_id
            elif '@g.us' in chat_id:
                phone = chat_id
                platform_id = chat_id
            display_name = participant if participant else chat_store.name or phone
        else:
            platform_id = participant if participant else chat_id
            display_name = participant if participant else chat_id
            phone = participant if participant and participant.replace('+', '').isdigit() else None
        
        # Ensure platform_id is set
        if not platform_id:
            platform_id = chat_id
        
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = 'whatsapp' AND platform_id = ?
        """, (platform_id,))
        row = cursor.fetchone()
        if row:
            return row['contact_id']
        
        cursor = self.conn.execute("""
            INSERT INTO contacts (display_name, phone, platform, platform_id, is_me)
            VALUES (?, ?, ?, ?, ?)
        """, (display_name, phone, 'whatsapp', platform_id, is_me))
        return cursor.lastrowid
    
    def import_messages(self, conv_db_id: int, chat_id: str, messages: List[Message]):
        """Import messages for a conversation"""
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
                if msg.from_me:
                    sender_id = me_contact_id
                else:
                    sender_id = None
                    if msg.sender:
                        for pid, cid in participants.items():
                            if msg.sender in pid or pid in msg.sender:
                                sender_id = cid
                                break
                    if not sender_id and '@s.whatsapp.net' in chat_id:
                        other_participants = [cid for pid, cid in participants.items() if pid != 'me']
                        if other_participants:
                            sender_id = other_participants[0]
                    if not sender_id:
                        logger.warning(f"Could not determine sender for message in {chat_id}")
                        continue
                
                message_body = self._extract_message_body(msg)
                platform_msg_id = str(msg.key_id) if msg.key_id else f"wa_{msg.timestamp}"
                
                if msg.timestamp:
                    unix_timestamp = msg.timestamp / 1000 if msg.timestamp > 9999999999 else msg.timestamp
                    msg_timestamp = datetime.fromtimestamp(unix_timestamp)
                else:
                    msg_timestamp = datetime.now()
                
                is_reply = msg.reply is not None and msg.reply != ''
                cursor = self.conn.execute("""
                    INSERT INTO messages (
                        platform, platform_message_id, conversation_id, sender_id,
                        timestamp, body, is_sent, has_attachment, is_reply,
                        raw_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, ('whatsapp', platform_msg_id, conv_db_id, sender_id,
                      msg_timestamp.isoformat(), message_body, msg.from_me,
                      msg.media, is_reply, json.dumps(self._message_to_dict(msg))))
                imported_count += 1
            except sqlite3.IntegrityError:
                skipped_count += 1
            except Exception as e:
                logger.warning(f"Error importing message: {e}")
                skipped_count += 1
        
        logger.debug(f"Imported {imported_count} messages, skipped {skipped_count}")
    
    def _extract_message_body(self, msg: Message) -> str:
        """Extract message body text"""
        if msg.data:
            body = msg.data
        elif msg.meta:
            body = "[Metadata]"
        elif msg.media:
            body = f"[Media] {msg.caption}" if msg.caption else "[Media]"
        else:
            body = "[Empty message]"
        if '<br>' in body:
            body = body.replace('<br>', ' ')
        return body[:10000]
    
    def _message_to_dict(self, msg: Message) -> Dict[str, Any]:
        """Convert Message to dict"""
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
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import WhatsApp messages into chat database')
    parser.add_argument('--db', default='database/chats.db', help='Path to SQLite database')
    parser.add_argument('--backup', help='Path to WhatsApp backup (not used for macOS)')
    parser.add_argument('--ios', action='store_true', help='Process iOS/macOS backup')
    parser.add_argument('--msg-db', help='Path to message database')
    parser.add_argument('--media', help='Path to media folder')
    args = parser.parse_args()
    
    # Default paths for macOS WhatsApp
    if not args.msg_db:
        wa_path = Path.home() / "Library/Group Containers/group.net.whatsapp.WhatsApp.shared"
        args.msg_db = str(wa_path / "ChatStorage.sqlite")
    
    if not os.path.exists(args.msg_db):
        logger.error(f"WhatsApp database not found at: {args.msg_db}")
        return 1
    
    logger.info("Initializing WhatsApp Chat Exporter...")
    chat_data = ChatCollection()
    
    try:
        import sqlite3
        conn = sqlite3.connect(args.msg_db)
        conn.row_factory = sqlite3.Row
        ios_handler.messages(conn, chat_data, args.media or '.', 0, None, (None, None), True)
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

