#!/usr/bin/env python3
"""
Import emails into the existing chat database using LLM-based extraction

This script:
1. Uses EmailLLMExtractor to intelligently parse emails from various sources
2. Imports emails into the existing normalized database structure
3. Handles email threads, participants, and attachments robustly
4. Supports EML files, JSON/JSONL files, and raw text
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from extractors.email_llm_extractor import EmailLLMExtractor
from schema import Message, Contact
from utils.logger import get_logger

logger = get_logger('email_importer')


class EmailDatabaseImporter:
    """Import emails into existing chat database"""
    
    def __init__(self, db_path: str):
        """
        Initialize importer with existing database
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = None
        self.extractor = EmailLLMExtractor()
        
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
    
    def import_from_file(self, file_path: str):
        """Import emails from a single file"""
        logger.info(f"Importing emails from file: {file_path}")
        
        if not self.conn:
            self.connect()
        
        # Extract emails using LLM extractor
        ledger = self.extractor.extract_from_file(file_path)
        
        if not ledger.messages:
            logger.warning(f"No messages extracted from {file_path}")
            return
        
        logger.info(f"Extracted {len(ledger.messages)} emails from file")
        
        # Import each message
        imported_count = 0
        skipped_count = 0
        
        for message in ledger.messages:
            try:
                self.import_message(message)
                imported_count += 1
                
                if imported_count % 50 == 0:
                    logger.info(f"Progress: {imported_count} emails imported...")
                    
            except sqlite3.IntegrityError:
                skipped_count += 1
                logger.debug(f"Skipped duplicate message: {message.message_id}")
            except Exception as e:
                logger.warning(f"Error importing message {message.message_id}: {e}")
                skipped_count += 1
                continue
        
        # Commit all changes
        self.conn.commit()
        logger.info(f"Imported {imported_count} emails, skipped {skipped_count} duplicates")
    
    def import_from_directory(self, directory: str, max_files: Optional[int] = None):
        """Import emails from all files in a directory"""
        logger.info(f"Importing emails from directory: {directory}")
        
        if not self.conn:
            self.connect()
        
        # Extract emails using LLM extractor
        ledger = self.extractor.extract_from_directory(directory, max_files=max_files)
        
        if not ledger.messages:
            logger.warning(f"No messages extracted from {directory}")
            return
        
        logger.info(f"Extracted {len(ledger.messages)} emails from directory")
        
        # Group messages by thread/conversation for efficient import
        self._import_ledger(ledger)
    
    def _import_ledger(self, ledger):
        """Import all messages from a ledger, grouping by conversations"""
        
        # Group messages by thread_id or subject+participants
        conversations = {}
        
        for message in ledger.messages:
            # Determine conversation key
            if message.thread_id:
                conv_key = f"email:{message.thread_id}"
            else:
                # Use subject + participant emails as key
                participant_emails = sorted([p.email for p in message.participants if p.email])
                subject = message.subject or ""
                conv_key = f"email:{subject}:{':'.join(participant_emails)}"
            
            if conv_key not in conversations:
                conversations[conv_key] = []
            conversations[conv_key].append(message)
        
        logger.info(f"Grouped into {len(conversations)} conversations")
        
        # Import each conversation
        total_imported = 0
        total_skipped = 0
        
        for conv_key, messages in conversations.items():
            try:
                # Sort messages by timestamp
                messages.sort(key=lambda m: m.timestamp)
                
                # Import conversation and messages
                conv_db_id = self._create_or_get_conversation(conv_key, messages)
                self._import_conversation_messages(conv_db_id, messages)
                
                imported = sum(1 for _ in messages)
                total_imported += imported
                
                if total_imported % 100 == 0:
                    logger.info(f"Progress: {total_imported} emails imported...")
                    
            except Exception as e:
                logger.error(f"Error importing conversation {conv_key}: {e}")
                continue
        
        # Commit all changes
        self.conn.commit()
        logger.info(f"Imported {total_imported} emails from {len(conversations)} conversations")
    
    def import_message(self, message: Message):
        """Import a single email message"""
        if not self.conn:
            self.connect()
        
        # Get or create conversation
        if message.thread_id:
            conv_key = f"email:{message.thread_id}"
        else:
            participant_emails = sorted([p.email for p in message.participants if p.email])
            subject = message.subject or ""
            conv_key = f"email:{subject}:{':'.join(participant_emails)}"
        
        conv_db_id = self._create_or_get_conversation(conv_key, [message])
        
        # Import participants
        self._import_participants(conv_db_id, message)
        
        # Import message
        self._insert_message(conv_db_id, message)
    
    def _create_or_get_conversation(self, conv_key: str, messages: List[Message]) -> int:
        """Create or get conversation ID"""
        
        # Determine conversation name from first message
        first_msg = messages[0]
        conv_name = first_msg.subject or "Email Conversation"
        
        # Get first and last timestamps
        timestamps = [m.timestamp for m in messages]
        first_ts = min(timestamps) if timestamps else None
        last_ts = max(timestamps) if timestamps else None
        
        # Determine if group (more than 2 participants)
        all_participants = set()
        for msg in messages:
            for p in msg.participants:
                if p.email:
                    all_participants.add(p.email)
        
        is_group = len(all_participants) > 2
        
        # Check if conversation already exists
        # Use thread_id if available, otherwise use subject+participants
        thread_id = first_msg.thread_id if first_msg.thread_id else conv_key
        
        cursor = self.conn.execute("""
            SELECT conversation_id FROM conversations 
            WHERE platform = 'email' AND thread_id = ?
        """, (thread_id,))
        
        row = cursor.fetchone()
        if row:
            conv_db_id = row['conversation_id']
            logger.debug(f"Using existing conversation {conv_name} (ID: {conv_db_id})")
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
                'email',
                thread_id,
                first_ts.isoformat() if first_ts else None,
                last_ts.isoformat() if last_ts else None,
                is_group,
                len(all_participants),
                len(messages)
            ))
            conv_db_id = cursor.lastrowid
            logger.debug(f"Created conversation {conv_name} (ID: {conv_db_id})")
        
        return conv_db_id
    
    def _import_participants(self, conv_db_id: int, message: Message):
        """Import conversation participants"""
        
        # Collect all unique participants
        participants = set()
        for p in message.participants:
            if p.email:
                participants.add((p.email, p.name))
        
        # Create/get contact records and link to conversation
        for email_addr, name in participants:
            contact_id = self._get_or_create_email_contact(email_addr, name)
            
            # Link to conversation
            self.conn.execute("""
                INSERT OR IGNORE INTO conversation_participants 
                (conversation_id, contact_id, role)
                VALUES (?, ?, ?)
            """, (conv_db_id, contact_id, 'member'))
    
    def _get_or_create_email_contact(self, email_addr: str, name: Optional[str] = None) -> int:
        """Get or create an email contact, return contact_id"""
        
        # Normalize email
        email_addr = email_addr.lower().strip()
        
        # Detect if this is "me" - check for common patterns
        is_me = self._is_me_email(email_addr)
        
        # Check if contact exists (by email across all platforms)
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE email = ?
            ORDER BY platform = 'email' DESC
            LIMIT 1
        """, (email_addr,))
        
        row = cursor.fetchone()
        if row:
            contact_id = row['contact_id']
            # Update name if we have a better one
            if name and name.strip():
                self.conn.execute("""
                    UPDATE contacts 
                    SET display_name = COALESCE(NULLIF(display_name, ''), ?),
                        is_me = ?
                    WHERE contact_id = ?
                """, (name.strip(), is_me, contact_id))
            elif is_me:
                # Update is_me flag if we detect it
                self.conn.execute("""
                    UPDATE contacts SET is_me = ? WHERE contact_id = ?
                """, (is_me, contact_id))
            return contact_id
        
        # Check if exists with email platform
        cursor = self.conn.execute("""
            SELECT contact_id FROM contacts 
            WHERE platform = 'email' AND platform_id = ?
        """, (email_addr,))
        
        row = cursor.fetchone()
        if row:
            # Update is_me if detected
            if is_me:
                self.conn.execute("""
                    UPDATE contacts SET is_me = ? WHERE contact_id = ?
                """, (is_me, row['contact_id']))
            return row['contact_id']
        
        # Create new contact
        display_name = name.strip() if name and name.strip() else (email_addr.split('@')[0] if not is_me else "Me")
        
        cursor = self.conn.execute("""
            INSERT INTO contacts (
                display_name, email, platform, platform_id, is_me
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            display_name,
            email_addr,
            'email',
            email_addr,
            is_me
        ))
        
        return cursor.lastrowid
    
    def _is_me_email(self, email_addr: str) -> bool:
        """Detect if email address belongs to the user"""
        # Check if there's already a contact marked as "me"
        cursor = self.conn.execute("""
            SELECT email FROM contacts WHERE is_me = 1 AND email IS NOT NULL LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            # If we have a known "me" email, compare
            return email_addr.lower() == row['email'].lower()
        
        # Heuristic: check for common "me" email patterns
        # This could be enhanced with a config file or user input
        email_lower = email_addr.lower()
        
        # Check if it matches common patterns (user can configure this)
        # For now, we'll mark it as not me and let user update manually
        return False
    
    def _insert_message(self, conv_db_id: int, message: Message):
        """Insert a single message into the database"""
        
        # Get sender contact ID
        sender_id = self._get_or_create_email_contact(message.sender.email, message.sender.name)
        
        # Determine if reply
        is_reply = message.is_reply or bool(message.original_message_id)
        reply_to_id = None
        
        if message.original_message_id:
            # Try to find the original message
            cursor = self.conn.execute("""
                SELECT message_id FROM messages 
                WHERE platform_message_id LIKE ? 
                ORDER BY timestamp DESC
                LIMIT 1
            """, (f"%{message.original_message_id}%",))
            row = cursor.fetchone()
            if row:
                reply_to_id = row['message_id']
        
        # Determine if sent (sender is "me" or matches known "me" addresses)
        is_sent = False
        if sender_id:
            cursor = self.conn.execute("""
                SELECT is_me FROM contacts WHERE contact_id = ?
            """, (sender_id,))
            row = cursor.fetchone()
            if row and row['is_me']:
                is_sent = True
        
        # Insert message
        platform_msg_id = message.message_id.replace('email:', '')
        
        cursor = self.conn.execute("""
            INSERT INTO messages (
                platform, platform_message_id, conversation_id, sender_id,
                timestamp, timezone, body, subject, is_sent, is_reply,
                reply_to_message_id, has_attachment, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'email',
            platform_msg_id,
            conv_db_id,
            sender_id,
            message.timestamp.isoformat(),
            message.timezone,
            message.body,
            message.subject,
            is_sent,
            is_reply,
            reply_to_id,
            len(message.attachments) > 0,
            json.dumps(message.raw_data)
        ))
        
        return cursor.lastrowid
    
    def _import_conversation_messages(self, conv_db_id: int, messages: List[Message]):
        """Import all messages for a conversation"""
        
        imported_count = 0
        skipped_count = 0
        
        for message in messages:
            try:
                # Import participants for this message
                self._import_participants(conv_db_id, message)
                
                # Insert message
                self._insert_message(conv_db_id, message)
                imported_count += 1
                
            except sqlite3.IntegrityError:
                skipped_count += 1
                logger.debug(f"Skipped duplicate message: {message.message_id}")
            except Exception as e:
                logger.warning(f"Error importing message: {e}")
                skipped_count += 1
        
        logger.debug(f"Imported {imported_count} messages, skipped {skipped_count} duplicates for conversation {conv_db_id}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Import emails into chat database using LLM-based extraction'
    )
    parser.add_argument(
        '--db', 
        default='data/database/chats.db',
        help='Path to SQLite database (default: data/database/chats.db)'
    )
    parser.add_argument(
        '--file',
        help='Path to email file (EML, JSON, or JSONL)'
    )
    parser.add_argument(
        '--directory',
        help='Path to directory containing email files'
    )
    parser.add_argument(
        '--eml-dir',
        help='Path to directory containing EML files (from gmail-exporter)'
    )
    parser.add_argument(
        '--json-file',
        help='Path to JSON/JSONL file containing emails'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.file and not args.directory and not args.eml_dir and not args.json_file:
        logger.error("Must provide one of: --file, --directory, --eml-dir, or --json-file")
        return 1
    
    # Initialize importer
    importer = EmailDatabaseImporter(args.db)
    importer.connect()
    
    try:
        if args.file:
            # Import from single file
            importer.import_from_file(args.file)
        
        elif args.directory:
            # Import from directory
            importer.import_from_directory(args.directory, max_files=args.max_files)
        
        elif args.eml_dir:
            # Import from EML directory (common case for gmail-exporter output)
            importer.import_from_directory(args.eml_dir, max_files=args.max_files)
        
        elif args.json_file:
            # Import from JSON file
            importer.import_from_file(args.json_file)
        
        logger.info("Email import completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Email import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        importer.close()


if __name__ == '__main__':
    sys.exit(main())

