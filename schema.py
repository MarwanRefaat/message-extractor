"""
Standardized schema for cross-platform message/transaction extraction
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Contact:
    """Standardized contact representation"""
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    platform_id: str  # Original ID from the platform
    platform: str  # 'imessage', 'whatsapp', 'gmail', 'gcal'


@dataclass
class Message:
    """
    Standardized message/transaction representation
    MECE (Mutually Exclusive, Collectively Exhaustive) format
    """
    # Unique identifiers
    message_id: str  # Unique across all platforms
    platform: str  # Source platform
    
    # Time
    timestamp: datetime
    timezone: Optional[str]
    
    # People involved
    sender: Contact
    recipients: List[Contact]  # All recipients (to, cc, bcc)
    participants: List[Contact]  # All unique people involved
    
    # Content
    subject: Optional[str]  # For emails and calendar events
    body: str
    attachments: List[str]  # File paths or references
    
    # Metadata
    thread_id: Optional[str]  # Conversation/thread identifier
    is_read: Optional[bool]
    is_starred: Optional[bool]
    is_reply: Optional[bool]
    original_message_id: Optional[str]  # If this is a reply/forward
    
    # Calendar-specific fields
    event_start: Optional[datetime]
    event_end: Optional[datetime]
    event_location: Optional[str]
    event_status: Optional[str]  # 'confirmed', 'tentative', 'cancelled'
    
    # Platform-specific raw data
    raw_data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'message_id': self.message_id,
            'platform': self.platform,
            'timestamp': self.timestamp.isoformat(),
            'timezone': self.timezone,
            'sender': {
                'name': self.sender.name,
                'email': self.sender.email,
                'phone': self.sender.phone,
                'platform_id': self.sender.platform_id,
                'platform': self.sender.platform
            },
            'recipients': [{
                'name': r.name,
                'email': r.email,
                'phone': r.phone,
                'platform_id': r.platform_id,
                'platform': r.platform
            } for r in self.recipients],
            'participants': [{
                'name': p.name,
                'email': p.email,
                'phone': p.phone,
                'platform_id': p.platform_id,
                'platform': p.platform
            } for p in self.participants],
            'subject': self.subject,
            'body': self.body,
            'attachments': self.attachments,
            'thread_id': self.thread_id,
            'is_read': self.is_read,
            'is_starred': self.is_starred,
            'is_reply': self.is_reply,
            'original_message_id': self.original_message_id,
            'event_start': self.event_start.isoformat() if self.event_start else None,
            'event_end': self.event_end.isoformat() if self.event_end else None,
            'event_location': self.event_location,
            'event_status': self.event_status,
            'raw_data': self.raw_data
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)


class UnifiedLedger:
    """
    Main ledger that combines all messages/transactions from all platforms
    """
    def __init__(self, start_date: Optional[datetime] = None):
        """
        Initialize ledger with optional date filter
        
        Args:
            start_date: Only include messages from this date onwards
        """
        self.messages: List[Message] = []
        self.contact_registry: Dict[str, Contact] = {}  # Unified contact registry
        self.start_date = start_date
    
    def add_message(self, message: Message):
        """Add a message to the ledger if it meets the date filter"""
        if self.start_date is None or message.timestamp >= self.start_date:
            self.messages.append(message)
            self._register_contacts(message)
    
    def _register_contacts(self, message: Message):
        """Register contacts in unified registry"""
        contacts = [message.sender] + message.recipients
        for contact in contacts:
            # Create composite key from all identifiers
            if contact.email:
                self.contact_registry[f"email:{contact.email}"] = contact
            if contact.phone:
                self.contact_registry[f"phone:{contact.phone}"] = contact
            if contact.platform_id:
                self.contact_registry[f"{contact.platform}:{contact.platform_id}"] = contact
    
    def get_conversations_with_contact(self, contact_key: str) -> List[Message]:
        """
        Get all conversations with a specific contact across all platforms
        contact_key can be email, phone, or platform_id
        """
        messages = []
        for message in self.messages:
            # Check sender
            if (contact_key in message.sender.email.lower() if message.sender.email else False) or \
               (contact_key in message.sender.phone if message.sender.phone else False):
                messages.append(message)
            # Check recipients
            for recipient in message.recipients:
                if (contact_key in recipient.email.lower() if recipient.email else False) or \
                   (contact_key in recipient.phone if recipient.phone else False):
                    messages.append(message)
                    break
        return messages
    
    def generate_timeline(self) -> List[Message]:
        """Generate chronological timeline of all messages"""
        return sorted(self.messages, key=lambda m: m.timestamp)
    
    def export_to_json(self, output_path: str):
        """Export entire ledger to JSON file"""
        timeline = self.generate_timeline()
        data = {
            'total_messages': len(self.messages),
            'platforms': list(set(m.platform for m in self.messages)),
            'unique_contacts': len(self.contact_registry),
            'messages': [m.to_dict() for m in timeline]
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def export_timeline_text(self, output_path: str):
        """Export timeline to human-readable text file"""
        timeline = self.generate_timeline()
        with open(output_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("UNIFIED MESSAGE LEDGER - TIMELINE\n")
            f.write("=" * 80 + "\n\n")
            
            for msg in timeline:
                f.write(f"\n[{msg.platform.upper()}] {msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"From: {msg.sender.name or msg.sender.email or msg.sender.phone}\n")
                
                if msg.recipients:
                    f.write(f"To: {', '.join(r.name or r.email or r.phone for r in msg.recipients)}\n")
                
                if msg.subject:
                    f.write(f"Subject: {msg.subject}\n")
                
                if msg.event_start:
                    f.write(f"Event: {msg.event_start.strftime('%Y-%m-%d %H:%M:%S')} - {msg.event_end.strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                f.write(f"\n{msg.body[:200]}{'...' if len(msg.body) > 200 else ''}\n")
                f.write("-" * 80 + "\n")

