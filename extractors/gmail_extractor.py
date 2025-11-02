"""
Gmail/G Suite email extraction module
Uses Gmail API to extract emails
"""
import os
from datetime import datetime
from typing import List, Optional
import json
import base64
import email.utils

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from schema import Message, Contact, UnifiedLedger
from constants import GMAIL_FILTER_QUERY
from exceptions import AuthenticationError, ExtractionError
from utils.logger import get_logger

logger = get_logger(__name__)


class GmailExtractor:
    """Extract emails from Gmail using Gmail API"""
    
    # Gmail API scopes
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, credentials_path: str = 'credentials.json', 
                 token_path: str = 'token.json'):
        """
        Initialize Gmail extractor
        
        Args:
            credentials_path: Path to OAuth2 credentials file
            token_path: Path to store authentication token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Gmail API"""
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. Please run: pip install -r requirements.txt"
            )
        
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail credentials not found. Please download credentials.json from "
                        f"Google Cloud Console and place it in: {self.credentials_path}"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('gmail', 'v1', credentials=creds)
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all emails from Gmail
        
        Args:
            max_results: Maximum number of messages to retrieve
        """
        ledger = UnifiedLedger()
        
        try:
            # Get all messages (filtered to 2024 onwards)
            results = self.service.users().messages().list(
                userId='me', 
                maxResults=min(max_results, 500),
                q=GMAIL_FILTER_QUERY
            ).execute()
            messages = results.get('messages', [])
            
            # Paginate through all messages
            while 'nextPageToken' in results and len(messages) < max_results:
                results = self.service.users().messages().list(
                    userId='me',
                    maxResults=500,
                    pageToken=results['nextPageToken'],
                    q=GMAIL_FILTER_QUERY
                ).execute()
                messages.extend(results.get('messages', []))
            
            logger.info(f"Found {len(messages)} emails to process")
            
            # Get full details for each message
            for i, msg in enumerate(messages):
                if i % 100 == 0:
                    logger.debug(f"Processing email {i}/{len(messages)}")
                
                try:
                    full_msg = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    message = self._parse_email(full_msg)
                    ledger.add_message(message)
                except Exception as e:
                    logger.warning(f"Error processing email {msg['id']}: {e}")
                    continue
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _parse_email(self, msg: dict) -> Message:
        """Parse Gmail API message format to Message object"""
        msg_id = msg['id']
        headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
        
        # Parse timestamp
        date_str = headers.get('Date', '')
        if date_str:
            try:
                timestamp_tuple = email.utils.parsedate_tz(date_str)
                timestamp = datetime.fromtimestamp(email.utils.mktime_tz(timestamp_tuple))
            except:
                timestamp = datetime.fromtimestamp(int(msg['internalDate']) / 1000)
        else:
            timestamp = datetime.fromtimestamp(int(msg['internalDate']) / 1000)
        
        # Parse sender
        from_field = headers.get('From', '')
        sender = self._parse_email_address(from_field, msg_id, 'sent')
        
        # Parse recipients
        recipients = []
        for field in ['To', 'Cc', 'Bcc']:
            if field in headers:
                recipients.extend(self._parse_email_address_list(headers[field], msg_id, field))
        
        participants = [sender] + recipients
        
        # Parse subject and body
        subject = headers.get('Subject', '')
        body = self._extract_body(msg['payload'])
        
        # Parse attachments
        attachments = []
        if 'parts' in msg['payload']:
            for part in msg['parts']:
                if part.get('filename'):
                    attachments.append(part['filename'])
        
        # Check if read
        is_read = not msg.get('labelIds', []).__contains__('UNREAD')
        
        # Get thread ID
        thread_id = msg.get('threadId')
        
        # Check if it's a reply (in-reply-to or references headers)
        original_message_id = headers.get('In-Reply-To') or headers.get('References', '').split()[0] if headers.get('References') else None
        is_reply = original_message_id is not None
        
        message = Message(
            message_id=f"gmail:{msg_id}",
            platform="gmail",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=subject,
            body=body,
            attachments=attachments,
            thread_id=thread_id,
            is_read=is_read,
            is_starred='STARRED' in msg.get('labelIds', []),
            is_reply=is_reply,
            original_message_id=original_message_id,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data=msg
        )
        
        return message
    
    def _parse_email_address(self, address_string: str, msg_id: str, role: str) -> Contact:
        """Parse email address string to Contact"""
        # Handle "Name <email@domain.com>" format
        name, email_addr = email.utils.parseaddr(address_string)
        if not email_addr:
            email_addr = address_string
        
        return Contact(
            name=name if name else email_addr,
            email=email_addr,
            phone=None,
            platform_id=email_addr,
            platform="gmail"
        )
    
    def _parse_email_address_list(self, address_string: str, msg_id: str, field: str) -> List[Contact]:
        """Parse list of email addresses"""
        addresses = []
        for addr in email.utils.getaddresses([address_string]):
            name, email_addr = addr
            if email_addr:
                addresses.append(Contact(
                    name=name if name else email_addr,
                    email=email_addr,
                    phone=None,
                    platform_id=email_addr,
                    platform="gmail"
                ))
        return addresses
    
    def _extract_body(self, payload: dict) -> str:
        """Extract body text from email payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif part['mimeType'] == 'text/html':
                    # Prefer plain text, but fall back to HTML if needed
                    if not body:
                        data = part['body'].get('data')
                        if data:
                            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        else:
            # Single part message
            if payload['mimeType'] == 'text/plain':
                data = payload['body'].get('data')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return body.strip()
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw Gmail data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "gmail_raw.jsonl")
        
        results = self.service.users().messages().list(
            userId='me', maxResults=min(max_results, 500)).execute()
        messages = results.get('messages', [])
        
        while 'nextPageToken' in results and len(messages) < max_results:
            results = self.service.users().messages().list(
                userId='me',
                maxResults=500,
                pageToken=results['nextPageToken']
            ).execute()
            messages.extend(results.get('messages', []))
        
        with open(output_path, 'w') as f:
            for msg in messages:
                try:
                    full_msg = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    f.write(json.dumps(full_msg) + '\n')
                except Exception as e:
                    logger.warning(f"Error exporting email {msg['id']}: {e}")
                    continue
        
        logger.info(f"Exported {len(messages)} raw Gmail records to {output_path}")

