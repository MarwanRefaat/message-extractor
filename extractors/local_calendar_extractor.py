"""
Local Calendar extraction module
Extracts events from macOS Calendar.app (filtered to specific attendees)
"""
import os
import subprocess
from datetime import datetime
from typing import List, Optional
import json
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


class LocalCalendarExtractor:
    """Extract events from macOS Calendar.app using AppleScript"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self):
        """Initialize local Calendar extractor"""
        self.start_date = FILTER_START_DATE
        
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract events from Calendar.app
        
        Args:
            max_results: Maximum number of events to retrieve
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        if not DATEUTIL_AVAILABLE:
            raise ImportError(
                "python-dateutil not installed. Please run: pip install -r requirements.txt"
            )
        
        try:
            # Query Calendar.app using AppleScript
            events = self._query_calendar_app(max_results)
            logger.info(f"Found {len(events)} calendar events matching criteria")
            
            for event in events:
                try:
                    message = self._parse_calendar_event(event)
                    if message:
                        ledger.add_message(message)
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _query_calendar_app(self, max_results: int) -> List[dict]:
        """Query Calendar.app using AppleScript"""
        start_date_str = self.start_date.strftime("%B %d, %Y")
        
        script = f'''
        tell application "Calendar"
            set matchingEvents to {{}}
            set eventCount to 0
            
            repeat with currentCalendar in calendars
                try
                    set calendarEvents to events of currentCalendar whose start date >= date "{start_date_str}"
                    
                    repeat with currentEvent in calendarEvents
                        if eventCount >= {max_results} then
                            exit repeat
                        end if
                        
                        try
                            -- Check if event has target email in attendees
                            set eventAttendees to attendees of currentEvent
                            set isTarget to false
                            
                            repeat with attendee in eventAttendees
                                try
                                    set attendeeEmail to email of attendee
                                    if attendeeEmail contains "{self.TARGET_EMAILS[0]}" or attendeeEmail contains "{self.TARGET_EMAILS[1]}" then
                                        set isTarget to true
                                        exit repeat
                                    end if
                                end try
                            end repeat
                            
                            -- Also check organizer
                            try
                                set organizerEmail to email of organizer of currentEvent
                                if organizerEmail contains "{self.TARGET_EMAILS[0]}" or organizerEmail contains "{self.TARGET_EMAILS[1]}" then
                                    set isTarget to true
                                end if
                            end try
                            
                            if isTarget then
                                set eventInfo to {{id: (id of currentEvent), summary: (summary of currentEvent), start_date: (start date of currentEvent), end_date: (end date of currentEvent), description: (description of currentEvent), location: (location of currentEvent), status: (status of currentEvent), organizer: (email of organizer of currentEvent)}}
                                set end of matchingEvents to eventInfo
                                set eventCount to eventCount + 1
                            end if
                        on error
                            -- Skip problematic events
                        end try
                    end repeat
                on error
                    -- Calendar doesn't exist or has no events, skip
                end try
            end repeat
            
            return matchingEvents
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
                # Fallback to simpler query
                return self._query_calendar_simple(max_results)
            
            # Parse AppleScript output (returns as text, need proper parsing)
            # For now, use simpler approach
            return self._query_calendar_simple(max_results)
            
        except subprocess.TimeoutExpired:
            logger.error("AppleScript query timed out")
            return []
        except Exception as e:
            logger.error(f"Error querying Calendar.app: {e}")
            return []
    
    def _query_calendar_simple(self, max_results: int) -> List[dict]:
        """Query Calendar.app using simpler AppleScript"""
        start_date_obj = self.start_date.strftime("%B %d, %Y")
        email1 = self.TARGET_EMAILS[0]
        email2 = self.TARGET_EMAILS[1]
        
        script = f'''
        tell application "Calendar"
            set matchingEvents to {{}}
            set eventCount to 0
            set startDateObj to date "{start_date_obj}"
            
            repeat with currentCal in calendars
                try
                    set allCalEvents to events of currentCal
                    
                    repeat with evt in allCalEvents
                        if eventCount >= {max_results} then
                            exit repeat
                        end if
                        
                        try
                            set evtStartDate to start date of evt
                            if evtStartDate < startDateObj then
                                exit repeat
                            end if
                            
                            set hasTargetEmail to false
                            
                            -- Check attendees
                            try
                                set evtAttendees to every attendee of evt
                                repeat with att in evtAttendees
                                    try
                                        set attEmail to email of att as string
                                        if attEmail contains "{email1}" or attEmail contains "{email2}" then
                                            set hasTargetEmail to true
                                            exit repeat
                                        end if
                                    end try
                                end repeat
                            end try
                            
                            -- Check organizer
                            if not hasTargetEmail then
                                try
                                    set orgEmail to email of organizer of evt as string
                                    if orgEmail contains "{email1}" or orgEmail contains "{email2}" then
                                        set hasTargetEmail to true
                                    end if
                                end try
                            end if
                            
                            if hasTargetEmail then
                                try
                                    set evtId to (id of evt) as string
                                    set evtSummary to (summary of evt) as string
                                    set evtStartStr to (start date of evt) as string
                                    set evtEndStr to (end date of evt) as string
                                    set evtLocation to (location of evt) as string
                                    set evtDesc to (description of evt) as string
                                    
                                    set evtData to evtId & "|" & evtSummary & "|" & evtStartStr & "|" & evtEndStr & "|" & evtLocation & "|" & evtDesc
                                    set end of matchingEvents to evtData
                                    set eventCount to eventCount + 1
                                end try
                            end if
                        on error
                            -- Skip event
                        end try
                    end repeat
                on error
                    -- Skip calendar
                end try
            end repeat
            
            return matchingEvents
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
                logger.warning(f"Calendar AppleScript error: {result.stderr}")
                return []
            
            # Parse pipe-delimited results
            events = []
            for line in result.stdout.strip().split('\n'):
                if line and '|' in line:
                    parts = line.split('|', 5)
                    if len(parts) >= 4:
                        events.append({
                            'id': parts[0].strip(),
                            'summary': parts[1].strip(),
                            'start_date': parts[2].strip(),
                            'end_date': parts[3].strip() if len(parts) > 3 else parts[2].strip(),
                            'location': parts[4].strip() if len(parts) > 4 else '',
                            'description': parts[5].strip() if len(parts) > 5 else ''
                        })
            
            return events
            
        except Exception as e:
            logger.error(f"Error in calendar query: {e}")
            return []
    
    def _parse_calendar_event(self, event: dict) -> Optional[Message]:
        """Parse Calendar event to Message object"""
        try:
            # Parse dates (AppleScript returns dates in various formats)
            start_date_str = event.get('start_date', '')
            end_date_str = event.get('end_date', start_date_str)
            
            if start_date_str:
                try:
                    # Try dateutil parser first (handles many formats)
                    event_start = date_parser.parse(start_date_str)
                except:
                    # Try manual parsing for common AppleScript formats
                    try:
                        # Remove day name if present (e.g., "Monday, January 1, 2024 12:00:00 PM")
                        cleaned = re.sub(r'^[A-Za-z]+,?\s*', '', start_date_str)
                        event_start = datetime.strptime(cleaned, "%B %d, %Y %I:%M:%S %p")
                    except:
                        event_start = datetime.now()
            else:
                event_start = None
            
            if end_date_str and end_date_str != start_date_str:
                try:
                    event_end = date_parser.parse(end_date_str)
                except:
                    try:
                        cleaned = re.sub(r'^[A-Za-z]+,?\s*', '', end_date_str)
                        event_end = datetime.strptime(cleaned, "%B %d, %Y %I:%M:%S %p")
                    except:
                        event_end = event_start
            else:
                event_end = event_start
            
            timestamp = event_start if event_start else datetime.now()
            
        except Exception as e:
            logger.debug(f"Error parsing event dates: {e}")
            timestamp = datetime.now()
            event_start = None
            event_end = None
        
        # Parse summary (subject)
        subject = event.get('summary', 'Untitled Event')
        body = event.get('description', '')
        location = event.get('location', '')
        
        # Organizer (sender)
        organizer_email = event.get('organizer', '')
        if not organizer_email:
            # Default to one of target emails
            organizer_email = self.TARGET_EMAILS[0]
        
        sender = Contact(
            name=None,
            email=organizer_email,
            phone=None,
            platform_id=organizer_email,
            platform="localcal"
        )
        
        # Recipients (default to target emails since we filtered for them)
        recipients = []
        for email_addr in self.TARGET_EMAILS:
            recipients.append(Contact(
                name=None,
                email=email_addr,
                phone=None,
                platform_id=email_addr,
                platform="localcal"
            ))
        
        participants = [sender] + recipients
        
        message = Message(
            message_id=f"localcal:{event.get('id', 'unknown')}",
            platform="localcal",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=subject,
            body=body,
            attachments=[],
            thread_id=None,
            is_read=True,
            is_starred=False,
            is_reply=False,
            original_message_id=None,
            event_start=event_start,
            event_end=event_end,
            event_location=location,
            event_status="confirmed",
            raw_data=event
        )
        
        return message
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw Calendar data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "localcal_raw.jsonl")
        
        events = self._query_calendar_simple(max_results)
        
        with open(output_path, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        
        logger.info(f"Exported raw Calendar records to {output_path}")

