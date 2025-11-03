"""
Google Takeout Meet extraction module
Extracts meetings from Google Meet CSV files
"""
import os
import csv
from datetime import datetime
from typing import List, Optional
import json

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


class GoogleTakeoutMeetExtractor:
    """Extract meetings from Google Takeout Meet CSV files"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self, takeout_path: str = "raw_originals/Takeout/Google Meet"):
        """
        Initialize Google Takeout Meet extractor
        
        Args:
            takeout_path: Path to Google Takeout Meet directory
        """
        self.takeout_path = takeout_path
        self.start_date = FILTER_START_DATE
        
        if not DATEUTIL_AVAILABLE:
            raise ImportError(
                "python-dateutil not installed. Please run: pip install -r requirements.txt"
            )
        
        if not os.path.exists(self.takeout_path):
            raise FileNotFoundError(f"Google Takeout Meet directory not found at: {self.takeout_path}")
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all meetings from Google Meet CSV files
        
        Args:
            max_results: Maximum number of meetings to retrieve
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        try:
            # Find all CSV files
            csv_files = []
            for root, dirs, files in os.walk(self.takeout_path):
                for file in files:
                    if file.endswith('.csv'):
                        csv_files.append(os.path.join(root, file))
            
            logger.info(f"Found {len(csv_files)} Meet CSV file(s) to process")
            
            all_meetings = []
            for csv_file in csv_files:
                meetings = self._parse_csv_file(csv_file)
                all_meetings.extend(meetings)
            
            # Filter meetings and add to ledger
            for meeting in all_meetings[:max_results]:
                try:
                    message = self._parse_meeting_to_message(meeting)
                    if message:
                        ledger.add_message(message)
                except Exception as e:
                    logger.warning(f"Error processing meeting: {e}")
                    continue
            
            logger.info(f"Extracted {len(ledger.messages)} Meet meetings matching criteria")
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _parse_csv_file(self, csv_file: str) -> List[dict]:
        """Parse a CSV file and return list of meetings"""
        meetings = []
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Try to parse date fields (varies by CSV structure)
                    meeting_date = None
                    for date_field in ['Start Time', 'Start time', 'Date', 'Call Date', 'start_time', 'date']:
                        if date_field in row and row[date_field]:
                            try:
                                meeting_date = date_parser.parse(row[date_field])
                                break
                            except Exception:
                                continue
                    
                    # Filter by date (2024+)
                    if meeting_date:
                        # Handle timezone-aware vs timezone-naive comparison
                        if meeting_date.tzinfo is not None:
                            # Convert to UTC naive for comparison
                            meeting_date = meeting_date.astimezone().replace(tzinfo=None)
                        
                        if meeting_date < self.start_date:
                            continue
                    
                    row['_parsed_date'] = meeting_date
                    meetings.append(row)
        
        except Exception as e:
            logger.warning(f"Error parsing CSV file {csv_file}: {e}")
        
        return meetings
    
    def _parse_meeting_to_message(self, meeting: dict) -> Optional[Message]:
        """Parse meeting data to Message object"""
        # Check if meeting involves target emails
        has_target_email = False
        
        # Check various fields for target emails
        meeting_text = json.dumps(meeting).lower()
        for email in self.TARGET_EMAILS:
            if email.lower() in meeting_text:
                has_target_email = True
                break
        
        if not has_target_email:
            return None
        
        # Parse date - ensure it's timezone-naive for consistency
        timestamp = meeting.get('_parsed_date')
        if not timestamp:
            timestamp = datetime.now()
        elif timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone().replace(tzinfo=None)
        
        # Extract organizer/participant emails from meeting data
        organizer_email = None
        participant_emails = []
        
        for key, value in meeting.items():
            if isinstance(value, str):
                for email in self.TARGET_EMAILS:
                    if email.lower() in value.lower():
                        if 'organizer' in key.lower() or 'host' in key.lower():
                            organizer_email = email
                        else:
                            participant_emails.append(email)
        
        # Default organizer
        if not organizer_email:
            organizer_email = self.TARGET_EMAILS[0]
        
        sender = Contact(
            name=None,
            email=organizer_email,
            phone=None,
            platform_id=organizer_email,
            platform="googletakeoutmeet"
        )
        
        # Recipients (target emails)
        recipients = []
        for email_addr in self.TARGET_EMAILS:
            recipients.append(Contact(
                name=None,
                email=email_addr,
                phone=None,
                platform_id=email_addr,
                platform="googletakeoutmeet"
            ))
        
        participants = [sender] + recipients
        
        # Build summary from meeting data
        summary_parts = []
        for key in ['Meeting Title', 'Title', 'Meeting Name', 'Call Title']:
            if key in meeting and meeting[key]:
                summary_parts.append(str(meeting[key]))
                break
        
        if not summary_parts:
            summary_parts.append('Google Meet')
        
        summary = ' - '.join(summary_parts)
        
        # Build body from meeting details
        body_parts = []
        for key, value in meeting.items():
            if key != '_parsed_date' and value and isinstance(value, str) and len(value) < 200:
                body_parts.append(f"{key}: {value}")
        
        body = '\n'.join(body_parts[:10])  # Limit to first 10 fields
        
        message = Message(
            message_id=f"googletakeoutmeet:{abs(hash(str(meeting)))}",
            platform="googletakeoutmeet",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=summary,
            body=body,
            attachments=[],
            thread_id=None,
            is_read=True,
            is_starred=False,
            is_reply=False,
            original_message_id=None,
            event_start=timestamp,
            event_end=None,
            event_location=None,
            event_status="confirmed",
            raw_data=self._make_json_serializable(meeting)
        )
        
        return message
    
    def _make_json_serializable(self, obj):
        """Convert datetime objects to ISO format strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        else:
            return obj
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw meeting data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "googletakeoutmeet_raw.jsonl")
        
        csv_files = []
        for root, dirs, files in os.walk(self.takeout_path):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
        
        all_meetings = []
        for csv_file in csv_files:
            meetings = self._parse_csv_file(csv_file)
            all_meetings.extend(meetings)
        
        with open(output_path, 'w') as f:
            for meeting in all_meetings[:max_results]:
                # Convert datetime objects to ISO format strings for JSON
                meeting_serializable = self._make_json_serializable(meeting)
                f.write(json.dumps(meeting_serializable) + '\n')
        
        logger.info(f"Exported {len(all_meetings[:max_results])} raw meeting records to {output_path}")

