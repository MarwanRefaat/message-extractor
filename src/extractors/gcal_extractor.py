"""
Google Calendar extraction module
Uses Google Calendar API with LLM to intelligently extract and filter events
Filters for events where user was invited and excludes generic holidays
"""
import os
import re
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

try:
    from dateutil import parser as date_parser
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

from schema import Message, Contact, UnifiedLedger
from constants import GCAL_FILTER_TIME_MIN, FILTER_START_DATE
from exceptions import AuthenticationError, ExtractionError
from utils.logger import get_logger
from utils.validators import validate_message, sanitize_json_data

logger = get_logger(__name__)


class GoogleCalendarExtractor:
    """
    Extract events from Google Calendar using Calendar API with LLM-based intelligent filtering
    
    Filters for events where user was invited (by email or phone) and excludes generic holidays
    """
    
    # Calendar API scopes
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    # User identifiers to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    TARGET_PHONE = "+14247774242"  # Normalized: +1 (424) 777-4242
    
    # Generic holiday indicators (to exclude)
    HOLIDAY_INDICATORS = [
        "holiday", "public holiday", "national holiday", "federal holiday",
        "christmas", "new year", "thanksgiving", "independence day",
        "memorial day", "labor day", "president's day", "martin luther king",
        "columbus day", "veterans day", "easter", "halloween", "valentine",
        "mother's day", "father's day", "memorial day", "july 4th",
        "4th of july", "groundhog day", "st. patrick", "cinco de mayo"
    ]
    
    def __init__(self, credentials_path: str = 'credentials.json', 
                 token_path: str = 'token.json',
                 use_llm: bool = True,
                 model_name: str = "gpt4all",
                 temperature: float = 0.0):
        """
        Initialize Calendar extractor with LLM support
        
        Args:
            credentials_path: Path to OAuth2 credentials file
            token_path: Path to store authentication token
            use_llm: Whether to use LLM for intelligent filtering and extraction
            model_name: Name of local LLM to use
            temperature: Sampling temperature (0.0 for deterministic)
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.use_llm = use_llm
        self.model_name = model_name
        self.temperature = temperature
        self.llm = None
        self.start_date = FILTER_START_DATE
        self._initialize_llm()
        self._authenticate()
    
    def _initialize_llm(self):
        """Initialize the local LLM for intelligent event filtering"""
        if not self.use_llm:
            return
            
        try:
            from gpt4all import GPT4All  # type: ignore
            fast_models = ["orca-mini-3b-gguf2-q4_0.gguf", "ggml-gpt4all-j-v1.3-groovy.bin", "gpt4all"]
            model_initialized = False
            
            for model in fast_models:
                try:
                    self.llm = GPT4All(model_name=model, allow_download=True, device='cpu')
                    logger.info(f"Initialized LLM model: {model}")
                    model_initialized = True
                    break
                except Exception:
                    continue
            
            if not model_initialized:
                self.llm = GPT4All(model_name=self.model_name, allow_download=True, device='cpu')
                logger.info(f"Initialized {self.model_name}")
        except ImportError:
            logger.warning("GPT4All not installed. Install with: pip install gpt4all")
            logger.warning("Falling back to rule-based filtering")
            self.llm = None
            self.use_llm = False
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
            self.use_llm = False
    
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. Please run: pip install -r requirements.txt"
            )
        if not DATEUTIL_AVAILABLE:
            raise ImportError(
                "python-dateutil not installed. Please run: pip install -r requirements.txt"
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
                        f"Google Calendar credentials not found. Please download credentials.json from "
                        f"Google Cloud Console and place it in: {self.credentials_path}"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('calendar', 'v3', credentials=creds)
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all calendar events
        
        Args:
            max_results: Maximum number of events to retrieve
        """
        ledger = UnifiedLedger()
        
        try:
            # Get all calendars
            calendars = self.service.calendarList().list().execute()
            calendar_list = calendars.get('items', [])
            
            logger.info(f"Found {len(calendar_list)} calendars")
            
            for calendar in calendar_list:
                calendar_id = calendar['id']
                calendar_summary = calendar.get('summary', 'Unknown')
                
                # Get events from each calendar (filtered to 2024 onwards)
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    maxResults=2500,  # API limit per page
                    singleEvents=True,
                    orderBy='startTime',
                    timeMin=GCAL_FILTER_TIME_MIN
                ).execute()
                
                events = events_result.get('items', [])
                
                logger.info(f"Found {len(events)} events in calendar: {calendar_summary}")
                
                filtered_count = 0
                for event in events:
                    try:
                        # Filter: check if user was invited
                        if not self._should_include_event(event):
                            continue
                        
                        # Parse event with LLM enhancement
                        message = self._parse_event(event, calendar_summary)
                        if message:
                            ledger.add_message(message)
                            filtered_count += 1
                    except Exception as e:
                        logger.warning(f"Error processing event {event.get('id', 'unknown')}: {e}")
                        continue
                
                if filtered_count < len(events):
                    logger.info(f"Filtered: {filtered_count}/{len(events)} events included from calendar: {calendar_summary}")
        
        except Exception as error:
            logger.error(f'An error occurred: {error}')
            raise
        
        logger.info(f"Extracted {len(ledger.messages)} calendar events matching criteria")
        return ledger
    
    def _should_include_event(self, event: dict) -> bool:
        """
        Determine if event should be included based on filtering criteria
        
        Args:
            event: Google Calendar event dictionary
            
        Returns:
            True if event should be included, False otherwise
        """
        # Check if user's email/phone is in attendees
        attendees_list = event.get('attendees', [])
        organizer = event.get('organizer', {})
        organizer_email = organizer.get('email', '').lower()
        
        # Check organizer
        if organizer_email in [e.lower() for e in self.TARGET_EMAILS]:
            # Use LLM to check if it's a generic holiday
            if self.use_llm and self.llm:
                if not self._llm_is_not_generic_holiday(event):
                    return False
            else:
                # Rule-based holiday check
                if self._is_generic_holiday(event):
                    return False
            return True
        
        # Check attendees
        user_invited = False
        for attendee in attendees_list:
            attendee_email = attendee.get('email', '').lower()
            if attendee_email in [e.lower() for e in self.TARGET_EMAILS]:
                user_invited = True
                break
        
        if not user_invited:
            return False
        
        # Check if it's a generic holiday (exclude these)
        if self.use_llm and self.llm:
            return self._llm_is_not_generic_holiday(event)
        else:
            return not self._is_generic_holiday(event)
    
    def _is_generic_holiday(self, event: dict) -> bool:
        """Rule-based check if event is a generic holiday"""
        summary = event.get('summary', '').lower()
        description = event.get('description', '').lower()
        
        # Check if any holiday indicator appears
        text = f"{summary} {description}"
        for indicator in self.HOLIDAY_INDICATORS:
            if indicator in text:
                return True
        
        # Check if event appears in a holiday calendar
        calendar_id = event.get('organizer', {}).get('email', '')
        if 'holiday' in calendar_id.lower() or 'holidays' in calendar_id.lower():
            return True
        
        return False
    
    def _llm_is_not_generic_holiday(self, event: dict) -> bool:
        """
        Use LLM to determine if event is NOT a generic holiday
        
        Returns:
            True if event is NOT a generic holiday (should include)
            False if event IS a generic holiday (should exclude)
        """
        if not self.llm:
            return not self._is_generic_holiday(event)
        
        summary = event.get('summary', '')
        description = event.get('description', '')
        
        prompt = f"""Analyze this calendar event and determine if it's a generic/public holiday that should be excluded.

Event Summary: {summary}
Event Description: {description[:500]}

CRITICAL REQUIREMENTS:
1. Return ONLY "true" or "false" (no quotes, no explanation, no JSON, no markdown)
2. Return "true" if this is a REAL, PERSONAL calendar event (meetings, appointments, calls, personal events)
3. Return "false" if this is a generic/public holiday like Christmas, New Year, Thanksgiving, Independence Day, etc.
4. Return "false" if this is an automatic holiday calendar entry
5. If the event is ambiguous but seems personal (like "Team Meeting", "Dentist", "Coffee with John"), return "true"

Event data:
{json.dumps(event, indent=2, default=str)[:1000]}

Answer (true or false only):"""
        
        try:
            response = self.llm.generate(
                prompt,
                max_tokens=10,
                temp=self.temperature
            ).strip().lower()
            
            # Parse response
            if 'true' in response:
                return True
            elif 'false' in response:
                return False
            else:
                # Fallback to rule-based
                logger.warning(f"LLM returned unclear response: {response}, using rule-based check")
                return not self._is_generic_holiday(event)
        except Exception as e:
            logger.warning(f"LLM holiday check failed: {e}, using rule-based check")
            return not self._is_generic_holiday(event)
    
    def _parse_event(self, event: dict, calendar_name: str) -> Optional[Message]:
        """Parse Google Calendar event to Message object"""
        event_id = event['id']
        
        # Parse start and end times
        start = event.get('start', {})
        end = event.get('end', {})
        
        # Handle both dateTime (specific time) and date (all-day) formats
        if 'dateTime' in start:
            event_start = date_parser.parse(start['dateTime'])
            event_end = date_parser.parse(end.get('dateTime', start['dateTime']))
        elif 'date' in start:
            event_start = date_parser.parse(start['date'])
            event_end = date_parser.parse(end.get('date', start['date']))
        else:
            event_start = None
            event_end = None
        
        # Use start time as timestamp for sorting
        timestamp = event_start if event_start else datetime.now()
        
        # Parse summary (subject)
        subject = event.get('summary', 'Untitled Event')
        if calendar_name:
            subject = f"[{calendar_name}] {subject}"
        
        # Parse description (body) - use LLM to clean if available
        raw_description = event.get('description', '')
        body = raw_description
        
        if self.use_llm and self.llm:
            cleaned_body = self._llm_clean_description(raw_description, subject)
            if cleaned_body:
                body = cleaned_body
        
        # Ensure body is not empty
        if not body.strip():
            body = f"[Calendar Event: {subject}]"
        
        # Parse location
        location = event.get('location', '')
        
        # Parse status
        status = event.get('status', 'confirmed')
        
        # Parse recurrence info
        recurrence = event.get('recurrence', [])
        is_recurring = len(recurrence) > 0
        recurrence_pattern = '; '.join(recurrence) if recurrence else None
        
        # Parse organizer (sender)
        organizer = event.get('organizer', {})
        organizer_email = organizer.get('email', '')
        organizer_name = organizer.get('displayName', organizer_email)
        
        sender = Contact(
            name=organizer_name,
            email=organizer_email,
            phone=None,
            platform_id=organizer_email or 'system',
            platform="gcal"
        )
        
        # Parse attendees (recipients)
        attendees_list = event.get('attendees', [])
        recipients = []
        for attendee in attendees_list:
            attendee_email = attendee.get('email', '')
            attendee_name = attendee.get('displayName', attendee_email)
            recipients.append(Contact(
                name=attendee_name,
                email=attendee_email,
                phone=None,
                platform_id=attendee_email,
                platform="gcal"
            ))
        
        # If no attendees, add organizer as participant
        if not recipients:
            recipients = [sender]
        
        participants = [sender] + recipients
        
        # Parse attachments
        attachments = []
        attachments_data = event.get('attachments', [])
        for att in attachments_data:
            if att.get('fileUrl'):
                attachments.append(att['fileUrl'])
        
        message = Message(
            message_id=f"gcal:{event_id}",
            platform="gcal",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=subject,
            body=body,
            attachments=attachments,
            thread_id=None,
            is_read=True,
            is_starred=False,
            is_reply=False,
            original_message_id=None,
            event_start=event_start,
            event_end=event_end,
            event_location=location,
            event_status=status,
            raw_data={
                **event,
                'calendar_name': calendar_name,
                'is_recurring': is_recurring,
                'recurrence_pattern': recurrence_pattern
            }
        )
        
        # Validate and sanitize
        try:
            msg_dict = message.to_dict()
            msg_dict = sanitize_json_data({'messages': [msg_dict]})['messages'][0]
            errors = validate_message(msg_dict)
            if errors:
                logger.warning(f"Event validation warnings: {errors[:3]}")
        except Exception as e:
            logger.warning(f"Event validation error: {e}")
        
        return message
    
    def _llm_clean_description(self, description: str, subject: str) -> Optional[str]:
        """Use LLM to clean and extract meaningful description"""
        if not self.llm or not description:
            return description
        
        prompt = f"""Clean and extract the meaningful description from this calendar event.

Event Subject: {subject}
Raw Description: {description[:800]}

CRITICAL REQUIREMENTS:
1. Extract the actual meaningful content
2. Remove:
   - Meeting links (zoom, meet, teams URLs)
   - Generic boilerplate text
   - Automatic calendar text
   - "Join Google Meet" or similar standard text
3. Keep:
   - Actual event description/notes
   - Agenda items
   - Important details
   - Participant notes
4. If there's no meaningful content, return empty string
5. Return ONLY the cleaned text, no explanations, no JSON, no quotes

Cleaned description:"""
        
        try:
            response = self.llm.generate(
                prompt,
                max_tokens=500,
                temp=self.temperature
            ).strip()
            
            # Remove quotes if present
            response = response.strip('"').strip("'")
            
            # If response seems meaningful (not just "none" or empty)
            if response and len(response) > 5 and response.lower() not in ['none', 'n/a', 'empty', 'no content']:
                return response
            else:
                return description  # Return original if LLM didn't help
        except Exception as e:
            logger.warning(f"LLM description cleaning failed: {e}")
            return description
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw Google Calendar data to separate file"""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "gcal_raw.jsonl")
        
        calendars = self.service.calendarList().list().execute()
        calendar_list = calendars.get('items', [])
        
        with open(output_path, 'w') as f:
            for calendar in calendar_list:
                calendar_id = calendar['id']
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    maxResults=2500,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                
                for event in events:
                    f.write(json.dumps(event) + '\n')
        
        logger.info(f"Exported raw Google Calendar records to {output_path}")

