"""
Google Takeout Calendar extraction module
Extracts events from Google Takeout .ics calendar files
"""
import os
from datetime import datetime
from typing import List, Optional
import json
import re

try:
    from icalendar import Calendar, Event
    ICALENDAR_AVAILABLE = True
except ImportError:
    ICALENDAR_AVAILABLE = False

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


class GoogleTakeoutCalendarExtractor:
    """Extract events from Google Takeout .ics calendar files"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self, takeout_path: str = "raw_originals/Takeout/Calendar"):
        """
        Initialize Google Takeout Calendar extractor
        
        Args:
            takeout_path: Path to Google Takeout Calendar directory
        """
        self.takeout_path = takeout_path
        self.start_date = FILTER_START_DATE
        
        if not ICALENDAR_AVAILABLE:
            raise ImportError(
                "python-icalendar not installed. Please run: pip install icalendar"
            )
        
        if not DATEUTIL_AVAILABLE:
            raise ImportError(
                "python-dateutil not installed. Please run: pip install -r requirements.txt"
            )
        
        if not os.path.exists(self.takeout_path):
            raise FileNotFoundError(f"Google Takeout Calendar directory not found at: {self.takeout_path}")
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all calendar events from .ics files
        
        Args:
            max_results: Maximum number of events to retrieve
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        try:
            # Find all .ics files in the directory
            ics_files = []
            for file in os.listdir(self.takeout_path):
                if file.endswith('.ics'):
                    ics_files.append(os.path.join(self.takeout_path, file))
            
            logger.info(f"Found {len(ics_files)} calendar file(s) to process")
            
            all_events = []
            for ics_file in ics_files:
                events = self._parse_ics_file(ics_file)
                all_events.extend(events)
            
            # Filter events and add to ledger
            for event in all_events[:max_results]:
                try:
                    message = self._parse_event_to_message(event)
                    if message:
                        ledger.add_message(message)
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue
            
            logger.info(f"Extracted {len(ledger.messages)} calendar events matching criteria")
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _parse_ics_file(self, ics_file: str) -> List[dict]:
        """Parse a single .ics file and return list of events"""
        events = []
        
        try:
            with open(ics_file, 'rb') as f:
                calendar = Calendar.from_ical(f.read())
            
            for component in calendar.walk():
                if component.name == "VEVENT":
                    event_data = {}
                    
                    # Parse dates
                    if component.get('dtstart'):
                        dtstart = component.get('dtstart').dt
                        if isinstance(dtstart, datetime):
                            event_data['start'] = dtstart
                        else:
                            # All-day event
                            event_data['start'] = datetime.combine(dtstart, datetime.min.time())
                    
                    if component.get('dtend'):
                        dtend = component.get('dtend').dt
                        if isinstance(dtend, datetime):
                            event_data['end'] = dtend
                        else:
                            # All-day event
                            event_data['end'] = datetime.combine(dtend, datetime.max.time())
                    elif event_data.get('start'):
                        # Default to same as start if no end
                        event_data['end'] = event_data['start']
                    
                    # Filter by date (2024+)
                    if event_data.get('start'):
                        start_date = event_data['start']
                        # Handle timezone-aware vs timezone-naive comparison
                        if start_date.tzinfo is not None:
                            # Convert to UTC naive for comparison
                            start_date = start_date.astimezone().replace(tzinfo=None)
                        
                        if start_date < self.start_date:
                            continue
                    
                    # Parse summary (title)
                    if component.get('summary'):
                        event_data['summary'] = str(component.get('summary'))
                    else:
                        event_data['summary'] = 'Untitled Event'
                    
                    # Parse description
                    if component.get('description'):
                        event_data['description'] = str(component.get('description'))
                    else:
                        event_data['description'] = ''
                    
                    # Parse location
                    if component.get('location'):
                        event_data['location'] = str(component.get('location'))
                    else:
                        event_data['location'] = ''
                    
                    # Parse organizer
                    if component.get('organizer'):
                        organizer = str(component.get('organizer'))
                        # Extract email from "CN=Name:mailto:email@example.com"
                        email_match = re.search(r'mailto:([^\s]+)', organizer)
                        if email_match:
                            event_data['organizer'] = email_match.group(1)
                        else:
                            event_data['organizer'] = organizer
                    else:
                        event_data['organizer'] = None
                    
                    # Parse attendees
                    event_data['attendees'] = []
                    for attendee in component.get('attendee', []):
                        if isinstance(attendee, list):
                            for att in attendee:
                                att_str = str(att)
                                email_match = re.search(r'mailto:([^\s]+)', att_str)
                                if email_match:
                                    event_data['attendees'].append(email_match.group(1))
                        else:
                            att_str = str(attendee)
                            email_match = re.search(r'mailto:([^\s]+)', att_str)
                            if email_match:
                                event_data['attendees'].append(email_match.group(1))
                    
                    # Parse UID
                    if component.get('uid'):
                        event_data['uid'] = str(component.get('uid'))
                    else:
                        event_data['uid'] = None
                    
                    # Parse status
                    if component.get('status'):
                        event_data['status'] = str(component.get('status')).lower()
                    else:
                        event_data['status'] = 'confirmed'
                    
                    events.append(event_data)
        
        except Exception as e:
            logger.warning(f"Error parsing .ics file {ics_file}: {e}")
        
        return events
    
    def _parse_event_to_message(self, event: dict) -> Optional[Message]:
        """Parse calendar event to Message object"""
        # Check if event has target email in attendees or organizer
        has_target_email = False
        
        # Check organizer
        organizer_email = event.get('organizer')
        if organizer_email and (organizer_email in self.TARGET_EMAILS):
            has_target_email = True
        
        # Check attendees
        if not has_target_email:
            for attendee_email in event.get('attendees', []):
                if attendee_email in self.TARGET_EMAILS:
                    has_target_email = True
                    break
        
        # Skip if not relevant
        if not has_target_email:
            return None
        
        # Parse dates
        start_date = event.get('start')
        end_date = event.get('end', start_date)
        timestamp = start_date if start_date else datetime.now()
        
        # Organizer (sender)
        if organizer_email:
            sender = Contact(
                name=None,
                email=organizer_email,
                phone=None,
                platform_id=organizer_email,
                platform="googletakeoutcal"
            )
        else:
            # Default to first target email
            sender = Contact(
                name=None,
                email=self.TARGET_EMAILS[0],
                phone=None,
                platform_id=self.TARGET_EMAILS[0],
                platform="googletakeoutcal"
            )
        
        # Recipients (attendees with target emails)
        recipients = []
        for attendee_email in event.get('attendees', []):
            if attendee_email in self.TARGET_EMAILS:
                recipients.append(Contact(
                    name=None,
                    email=attendee_email,
                    phone=None,
                    platform_id=attendee_email,
                    platform="googletakeoutcal"
                ))
        
        # If no recipients found, add target emails
        if not recipients:
            for email_addr in self.TARGET_EMAILS:
                recipients.append(Contact(
                    name=None,
                    email=email_addr,
                    phone=None,
                    platform_id=email_addr,
                    platform="googletakeoutcal"
                ))
        
        participants = [sender] + recipients
        
        # Sanitize UID for message_id (remove special chars)
        uid = event.get('uid', 'unknown')
        sanitized_uid = re.sub(r'[^\w-]', '_', uid)
        
        # Ensure body is not empty
        body = event.get('description', '') or event.get('summary', '') or '[Calendar Event]'
        
        message = Message(
            message_id=f"googletakeoutcal:{sanitized_uid}",
            platform="googletakeoutcal",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=event.get('summary', 'Untitled Event'),
            body=body,
            attachments=[],
            thread_id=None,
            is_read=True,
            is_starred=False,
            is_reply=False,
            original_message_id=None,
            event_start=start_date,
            event_end=end_date,
            event_location=event.get('location', ''),
            event_status=event.get('status', 'confirmed'),
            raw_data=self._make_json_serializable(event)
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
        """Export raw calendar data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "googletakeoutcal_raw.jsonl")
        
        ics_files = []
        for file in os.listdir(self.takeout_path):
            if file.endswith('.ics'):
                ics_files.append(os.path.join(self.takeout_path, file))
        
        all_events = []
        for ics_file in ics_files:
            events = self._parse_ics_file(ics_file)
            all_events.extend(events)
        
        with open(output_path, 'w') as f:
            for event in all_events[:max_results]:
                # Convert datetime objects to ISO format strings for JSON
                event_serializable = self._make_json_serializable(event)
                f.write(json.dumps(event_serializable) + '\n')
        
        logger.info(f"Exported {len(all_events[:max_results])} raw calendar records to {output_path}")

