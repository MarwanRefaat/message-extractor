"""
Apple Mail extraction module
Extracts emails from local Mail.app (filtered to specific recipients)
"""
import os
import subprocess
from datetime import datetime
from typing import List, Optional
import json
import email.utils
import re

from schema import Message, Contact, UnifiedLedger
from constants import FILTER_START_DATE
from utils.logger import get_logger
from .ocr_extractor import extract_from_attachment_path

logger = get_logger(__name__)


class AppleMailExtractor:
    """Extract emails from Apple Mail.app using AppleScript"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self):
        """Initialize Apple Mail extractor"""
        self.start_date = FILTER_START_DATE
        
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract emails from Apple Mail
        
        Args:
            max_results: Maximum number of messages to retrieve
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        try:
            # Use AppleScript to query Mail.app
            messages = self._query_mail_app(max_results)
            logger.info(f"Found {len(messages)} emails matching criteria")
            
            for i, msg in enumerate(messages):
                if i % 100 == 0 and i > 0:
                    logger.debug(f"Processing email {i}/{len(messages)}")
                
                try:
                    message = self._parse_mail_message(msg)
                    if message:
                        ledger.add_message(message)
                except Exception as e:
                    logger.warning(f"Error processing email: {e}")
                    continue
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _query_mail_app(self, max_results: int) -> List[dict]:
        """Query Mail.app using AppleScript"""
        # Build AppleScript to get emails
        target_emails_str = ", ".join([f'"{email}"' for email in self.TARGET_EMAILS])
        start_date_str = self.start_date.strftime("%A, %B %d, %Y")
        
        script = f'''
        tell application "Mail"
            set matchingMessages to {{}}
            set messageCount to 0
            
            repeat with currentMailbox in mailboxes
                repeat with currentMessage in messages of currentMailbox
                    if messageCount >= {max_results} then
                        exit repeat
                    end if
                    
                    try
                        set msgDate to date received of currentMessage
                        set msgDateObj to date "{start_date_str}"
                        if msgDate < msgDateObj then
                            exit repeat
                        end if
                        
                        -- Check if message is to one of our target emails
                        set msgRecipients to recipients of currentMessage
                        set isTarget to false
                        repeat with recipient in msgRecipients
                            set recipientAddress to address of recipient
                            if recipientAddress contains "{self.TARGET_EMAILS[0]}" or recipientAddress contains "{self.TARGET_EMAILS[1]}" then
                                set isTarget to true
                                exit repeat
                            end if
                        end repeat
                        
                        -- Also check To field
                        set msgTo to to recipients of currentMessage
                        repeat with recipient in msgTo
                            set recipientAddress to address of recipient
                            if recipientAddress contains "{self.TARGET_EMAILS[0]}" or recipientAddress contains "{self.TARGET_EMAILS[1]}" then
                                set isTarget to true
                                exit repeat
                            end if
                        end repeat
                        
                        if isTarget then
                            set messageInfo to {{message_id: (id of currentMessage), subject: (subject of currentMessage), sender: (sender of currentMessage), date_received: (date received of currentMessage), content: (content of currentMessage)}}
                            set end of matchingMessages to messageInfo
                            set messageCount to messageCount + 1
                        end if
                    on error
                        -- Skip messages that cause errors
                    end try
                end repeat
            end repeat
            
            return matchingMessages
        end tell
        '''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.warning(f"AppleScript error: {result.stderr}")
                return []
            
            # Parse results (AppleScript returns as text, need to parse)
            # For now, use a simpler approach - get messages via mailbox iteration
            return self._get_messages_simple(max_results)
            
        except subprocess.TimeoutExpired:
            logger.error("AppleScript query timed out")
            return []
        except Exception as e:
            logger.error(f"Error querying Mail.app: {e}")
            return []
    
    def _get_messages_simple(self, max_results: int) -> List[dict]:
        """Get messages using database query (fallback)"""
        return self._query_mail_database(max_results)
    
    def _query_mail_database(self, max_results: int) -> List[dict]:
        """Query Mail.app using AppleScript (simpler and more reliable)"""
        messages = []
        
        # Use AppleScript to query Mail.app directly
        target_emails_script = ' or '.join([f'"{email}"' for email in self.TARGET_EMAILS])
        start_date_iso = self.start_date.strftime("%Y-%m-%d")
        
        # Build script with proper escaping
        email1 = self.TARGET_EMAILS[0]
        email2 = self.TARGET_EMAILS[1]
        start_date_obj = self.start_date.strftime("%B %d, %Y")
        
        script = f'''
        tell application "Mail"
            set matchingMessages to {{}}
            set messageCount to 0
            set startDateObj to date "{start_date_obj}"
            
            -- Get all accounts
            repeat with accountNum from 1 to count of accounts
                try
                    set currentAccount to account accountNum
                    
                    -- Check Inbox
                    try
                        set inboxMailbox to mailbox "INBOX" of currentAccount
                        set allInboxMessages to messages of inboxMailbox
                        
                        repeat with currentMessage in allInboxMessages
                            if messageCount >= {max_results} then exit repeat
                            
                            try
                                set msgDate to date received of currentMessage
                                if msgDate < startDateObj then
                                    exit repeat
                                end if
                                
                                -- Check To recipients
                                set msgRecipients to every recipient of currentMessage
                                set isTarget to false
                                
                                repeat with recipient in msgRecipients
                                    try
                                        set recipientAddress to address of recipient as string
                                        if recipientAddress contains "{email1}" or recipientAddress contains "{email2}" then
                                            set isTarget to true
                                            exit repeat
                                        end if
                                    end try
                                end repeat
                                
                                if isTarget then
                                    set msgId to (id of currentMessage) as string
                                    set msgSubject to (subject of currentMessage) as string
                                    set msgSender to (sender of currentMessage) as string
                                    set msgDateStr to (date received of currentMessage) as string
                                    set msgContent to (content of currentMessage) as string
                                    
                                    set msgData to msgId & "|" & msgSubject & "|" & msgSender & "|" & msgDateStr & "|" & msgContent
                                    set end of matchingMessages to msgData
                                    set messageCount to messageCount + 1
                                end if
                            on error
                                -- Skip problematic messages
                            end try
                        end repeat
                    end try
                    
                    -- Check Sent mailbox too
                    try
                        set sentMailbox to mailbox "Sent" of currentAccount
                        set allSentMessages to messages of sentMailbox
                        
                        repeat with currentMessage in allSentMessages
                            if messageCount >= {max_results} then exit repeat
                            
                            try
                                set msgDate to date received of currentMessage
                                if msgDate < startDateObj then
                                    exit repeat
                                end if
                                
                                set msgRecipients to (to recipients of currentMessage)
                                set isTarget to false
                                
                                repeat with recipient in msgRecipients
                                    try
                                        set recipientAddress to (address of recipient) as string
                                        if recipientAddress contains "{email1}" or recipientAddress contains "{email2}" then
                                            set isTarget to true
                                            exit repeat
                                        end if
                                    end try
                                end repeat
                                
                                if isTarget then
                                    set msgId to (id of currentMessage) as string
                                    set msgSubject to (subject of currentMessage) as string
                                    set msgSender to (sender of currentMessage) as string
                                    set msgDateStr to (date received of currentMessage) as string
                                    set msgContent to (content of currentMessage) as string
                                    
                                    set msgData to msgId & "|" & msgSubject & "|" & msgSender & "|" & msgDateStr & "|" & msgContent
                                    set end of matchingMessages to msgData
                                    set messageCount to messageCount + 1
                                end if
                            on error
                                -- Skip
                            end try
                        end repeat
                    end try
                on error
                    -- Skip account
                end try
            end repeat
            
            return matchingMessages
        end tell
        '''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.warning(f"Mail AppleScript error: {result.stderr}")
                return []
            
            # Parse pipe-delimited results
            for line in result.stdout.strip().split('\n'):
                if line and '|' in line:
                    parts = line.split('|', 5)
                    if len(parts) >= 5:
                        messages.append({
                            'message_id': parts[0].strip(),
                            'subject': parts[1].strip(),
                            'sender': parts[2].strip(),
                            'date_received': parts[3].strip(),
                            'content': parts[4].strip(),
                            'to_addresses': parts[5].strip() if len(parts) > 5 else ''
                        })
        
        except subprocess.TimeoutExpired:
            logger.error("Mail query timed out")
        except Exception as e:
            logger.error(f"Error querying Mail.app: {e}")
        
        return messages
    
    def _parse_mail_message(self, msg: dict) -> Optional[Message]:
        """Parse Apple Mail message to Message object"""
        # Parse date (AppleScript returns dates in various formats)
        try:
            date_str = str(msg.get('date_received', ''))
            
            # Try to parse AppleScript date format (e.g., "Monday, January 1, 2024 12:00:00 PM")
            # Or ISO format
            if isinstance(msg.get('date_received'), (int, float)):
                timestamp = datetime.fromtimestamp(msg['date_received'])
            elif date_str:
                # Try different date formats
                try:
                    # ISO format
                    timestamp = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    try:
                        # AppleScript date format
                        # Remove day name if present
                        cleaned = re.sub(r'^[A-Za-z]+,?\s*', '', date_str)
                        timestamp = datetime.strptime(cleaned, "%B %d, %Y %I:%M:%S %p")
                    except:
                        try:
                            timestamp = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            # Fallback to now if all parsing fails
                            timestamp = datetime.now()
            else:
                timestamp = datetime.now()
        except Exception:
            timestamp = datetime.now()
        
        # Parse sender
        sender_str = msg.get('sender', 'Unknown')
        sender_name, sender_email = email.utils.parseaddr(sender_str)
        
        sender = Contact(
            name=sender_name if sender_name else None,
            email=sender_email if sender_email else sender_str,
            phone=None,
            platform_id=sender_email or sender_str,
            platform="applemail"
        )
        
        # Parse recipients
        recipients = []
        to_addresses = msg.get('to_addresses', '')
        if to_addresses:
            for addr in email.utils.getaddresses([to_addresses]):
                name, email_addr = addr
                if email_addr and email_addr in self.TARGET_EMAILS:
                    recipients.append(Contact(
                        name=name if name else None,
                        email=email_addr,
                        phone=None,
                        platform_id=email_addr,
                        platform="applemail"
                    ))
        
        if not recipients:
            # Default to target emails if not parsed
            for email_addr in self.TARGET_EMAILS:
                recipients.append(Contact(
                    name=None,
                    email=email_addr,
                    phone=None,
                    platform_id=email_addr,
                    platform="applemail"
                ))
        
        participants = [sender] + recipients
        
        # Parse subject and body
        subject = msg.get('subject', '')
        body = msg.get('content', '') or msg.get('snippet', '')
        
        message = Message(
            message_id=f"applemail:{msg.get('message_id', 'unknown')}",
            platform="applemail",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=subject,
            body=body,
            attachments=[],
            thread_id=None,
            is_read=None,
            is_starred=None,
            is_reply=None,
            original_message_id=None,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data=msg
        )
        
        return message
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw Apple Mail data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "applemail_raw.jsonl")
        
        messages = self._query_mail_database(max_results)
        
        with open(output_path, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')
        
        logger.info(f"Exported {len(messages)} raw Apple Mail records to {output_path}")

