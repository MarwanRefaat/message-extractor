"""
Google Takeout Chat extraction module
Extracts messages from Google Chat JSON files
"""
import os
import json
from datetime import datetime
from typing import List, Optional
import re

try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

from schema import Message, Contact, UnifiedLedger
from constants import FILTER_START_DATE
from exceptions import ExtractionError
from utils.logger import get_logger

logger = get_logger(__name__)


class GoogleTakeoutChatExtractor:
    """Extract messages from Google Takeout Chat JSON files"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self, takeout_path: str = "raw_originals/Takeout/Google Chat"):
        """
        Initialize Google Takeout Chat extractor
        
        Args:
            takeout_path: Path to Google Takeout Chat directory
        """
        self.takeout_path = takeout_path
        self.start_date = FILTER_START_DATE
        
        if not DATEUTIL_AVAILABLE:
            raise ImportError(
                "python-dateutil not installed. Please run: pip install -r requirements.txt"
            )
        
        if not os.path.exists(self.takeout_path):
            raise FileNotFoundError(f"Google Takeout Chat directory not found at: {self.takeout_path}")
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all messages from Google Chat
        
        Args:
            max_results: Maximum number of messages to retrieve
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        try:
            # Find all messages.json files
            messages_files = []
            for root, dirs, files in os.walk(self.takeout_path):
                if 'messages.json' in files:
                    messages_files.append(os.path.join(root, 'messages.json'))
            
            logger.info(f"Found {len(messages_files)} chat file(s) to process")
            
            all_messages = []
            for messages_file in messages_files:
                messages = self._parse_messages_file(messages_file)
                all_messages.extend(messages)
            
            # Filter messages and add to ledger
            count = 0
            for msg_data in all_messages:
                if count >= max_results:
                    break
                try:
                    message = self._parse_message_to_schema(msg_data)
                    if message:
                        ledger.add_message(message)
                        count += 1
                except Exception as e:
                    logger.warning(f"Error processing message: {e}")
                    continue
            
            logger.info(f"Extracted {len(ledger.messages)} chat messages matching criteria")
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _parse_messages_file(self, messages_file: str) -> List[dict]:
        """Parse a messages.json file and return list of messages"""
        messages = []
        
        try:
            with open(messages_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'messages' in data:
                for msg in data['messages']:
                    # Parse date
                    date_str = msg.get('created_date', '')
                    if date_str:
                        try:
                            # Parse date like "Sunday, December 13, 2020 at 11:21:42 AM UTC"
                            msg_date = date_parser.parse(date_str)
                            # Filter by date (2024+)
                            if msg_date < self.start_date:
                                continue
                        except Exception:
                            # Skip if date parsing fails
                            continue
                    
                    messages.append(msg)
        
        except Exception as e:
            logger.warning(f"Error parsing messages file {messages_file}: {e}")
        
        return messages
    
    def _parse_message_to_schema(self, msg: dict) -> Optional[Message]:
        """Parse Google Chat message to Message object"""
        # Parse date
        date_str = msg.get('created_date', '')
        try:
            timestamp = date_parser.parse(date_str)
        except Exception:
            timestamp = datetime.now()
        
        # Parse sender
        creator = msg.get('creator', {})
        sender_email = creator.get('email', '')
        sender_name = creator.get('name', '')
        
        if not sender_email:
            return None
        
        sender = Contact(
            name=sender_name if sender_name else None,
            email=sender_email,
            phone=None,
            platform_id=sender_email,
            platform="googletakeoutchat"
        )
        
        # Recipients - for 1-on-1 chats, recipient is the other person
        # For group chats, we need to check if target emails are in the group
        recipients = []
        
        # Check if sender is one of our target emails
        is_sender_target = sender_email in self.TARGET_EMAILS
        
        # If sender is target, we need to find the recipient(s)
        # Otherwise, if recipient could be target, add them
        # For now, we'll include all messages where sender or potential recipient is target
        
        if is_sender_target:
            # If sender is target, we'll add a generic recipient
            # In group chats, we can't determine individual recipients easily
            recipients.append(Contact(
                name="Chat Participant",
                email=None,
                phone=None,
                platform_id="chat_participant",
                platform="googletakeoutchat"
            ))
        else:
            # If sender is not target, recipient might be (1-on-1 case)
            # Add target emails as recipients
            for email_addr in self.TARGET_EMAILS:
                recipients.append(Contact(
                    name=None,
                    email=email_addr,
                    phone=None,
                    platform_id=email_addr,
                    platform="googletakeoutchat"
                ))
        
        participants = [sender] + recipients
        
        message = Message(
            message_id=f"googletakeoutchat:{msg.get('message_id', 'unknown')}",
            platform="googletakeoutchat",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=None,
            body=msg.get('text', ''),
            attachments=[],
            thread_id=msg.get('topic_id'),
            is_read=None,
            is_starred=False,
            is_reply=None,
            original_message_id=None,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data=msg
        )
        
        # Only include if sender or potential recipient is target email
        if sender_email in self.TARGET_EMAILS:
            return message
        
        return None  # Skip messages not involving target emails
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw chat data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "googletakeoutchat_raw.jsonl")
        
        messages_files = []
        for root, dirs, files in os.walk(self.takeout_path):
            if 'messages.json' in files:
                messages_files.append(os.path.join(root, 'messages.json'))
        
        all_messages = []
        for messages_file in messages_files:
            messages = self._parse_messages_file(messages_file)
            all_messages.extend(messages)
        
        with open(output_path, 'w') as f:
            for msg in all_messages[:max_results]:
                f.write(json.dumps(msg) + '\n')
        
        logger.info(f"Exported {len(all_messages[:max_results])} raw chat records to {output_path}")

