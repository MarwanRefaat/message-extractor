"""
Google Calendar extraction module
Uses Google Calendar API to extract events
"""
import os
from datetime import datetime
from typing import List, Optional
import json

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

# Filter start date: January 1, 2024
FILTER_START_DATE = datetime(2024, 1, 1)


class GoogleCalendarExtractor:
    """Extract events from Google Calendar using Calendar API"""
    
    # Calendar API scopes
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __init__(self, credentials_path: str = 'credentials.json', 
                 token_path: str = 'token.json'):
        """
        Initialize Calendar extractor
        
        Args:
            credentials_path: Path to OAuth2 credentials file
            token_path: Path to store authentication token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()
    
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
            
            print(f"Found {len(calendar_list)} calendars")
            
            for calendar in calendar_list:
                calendar_id = calendar['id']
                calendar_summary = calendar.get('summary', 'Unknown')
                
                # Get events from each calendar (filtered to 2024 onwards)
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    maxResults=2500,  # API limit per page
                    singleEvents=True,
                    orderBy='startTime',
                    timeMin=FILTER_START_DATE.isoformat() + 'Z'
                ).execute()
                
                events = events_result.get('items', [])
                
                print(f"Found {len(events)} events in calendar: {calendar_summary}")
                
                for event in events:
                    try:
                        message = self._parse_event(event, calendar_summary)
                        ledger.add_message(message)
                    except Exception as e:
                        print(f"Error processing event {event.get('id', 'unknown')}: {e}")
                        continue
        
        except Exception as error:
            print(f'An error occurred: {error}')
            raise
        
        return ledger
    
    def _parse_event(self, event: dict, calendar_name: str) -> Message:
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
        
        # Parse description (body)
        body = event.get('description', '')
        
        # Parse location
        location = event.get('location', '')
        
        # Parse status
        status = event.get('status', 'confirmed')
        
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
            raw_data=event
        )
        
        return message
    
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
        
        print(f"Exported raw Google Calendar records to {output_path}")

