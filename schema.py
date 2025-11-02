"""
Standardized schema for cross-platform message/transaction extraction
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import os


@dataclass
class Contact:
    """
    Standardized contact representation across all platforms
    
    Attributes:
        name: Display name of the contact
        email: Email address (if available)
        phone: Phone number (if available)
        platform_id: Original identifier from the source platform
        platform: Source platform identifier
    """
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    platform_id: str
    platform: str
    
    def __hash__(self):
        """Make Contact hashable for use in sets/dicts"""
        return hash((self.email, self.phone, self.platform_id, self.platform))
    
    def __eq__(self, other):
        """Equality based on identifiers"""
        if not isinstance(other, Contact):
            return False
        return (self.email == other.email and 
                self.phone == other.phone and 
                self.platform_id == other.platform_id)


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
    Main ledger that combines all messages/transactions from all platforms.
    Provides unified access with cross-platform contact linking.
    """
    def __init__(self, start_date: Optional[datetime] = None):
        """
        Initialize ledger with optional date filter
        
        Args:
            start_date: Only include messages from this date onwards
        """
        self.messages: List[Message] = []
        self.contact_registry: Dict[str, Contact] = {}
        self.start_date = start_date
    
    def __len__(self) -> int:
        """Return number of messages in ledger"""
        return len(self.messages)
    
    def __repr__(self) -> str:
        """String representation"""
        platforms = set(m.platform for m in self.messages)
        return (f"UnifiedLedger(messages={len(self.messages)}, "
                f"contacts={len(self.contact_registry)}, "
                f"platforms={platforms})")
    
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
    
    def export_to_json(self, output_path: str, validate: bool = True) -> None:
        """
        Export entire ledger to JSON file with validation
        
        Args:
            output_path: Path to output JSON file
            validate: Whether to validate JSON structure
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            timeline = self.generate_timeline()
            data = {
                'total_messages': len(self.messages),
                'platforms': sorted(set(m.platform for m in self.messages)),
                'unique_contacts': len(self.contact_registry),
                'messages': [m.to_dict() for m in timeline]
            }
            
            # Sanitize data for safe JSON output
            from utils.validators import sanitize_json_data
            data = sanitize_json_data(data)
            
            # Validate structure if requested
            if validate:
                from utils.validators import validate_ledger, ValidationError
                errors = validate_ledger(data)
                if errors:
                    import warnings
                    warnings.warn(f"JSON validation errors: {errors[:5]}...")
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        except IOError as e:
            raise IOError(f"Failed to write JSON export to {output_path}: {e}")
    
    def export_timeline_text(self, output_path: str, max_preview: int = 200) -> None:
        """
        Export timeline to human-readable text file
        
        Args:
            output_path: Path to output text file
            max_preview: Maximum characters to preview from message body
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            timeline = self.generate_timeline()
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("UNIFIED MESSAGE LEDGER - TIMELINE\n")
                f.write("=" * 80 + "\n\n")
                
                for msg in timeline:
                    f.write(f"\n[{msg.platform.upper()}] {msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    sender_str = str(msg.sender.name or msg.sender.email or msg.sender.phone or 'Unknown')
                    f.write(f"From: {sender_str}\n")
                    
                    if msg.recipients:
                        recipient_strs = []
                        for r in msg.recipients:
                            val = r.name or r.email or r.phone
                            if val:
                                recipient_strs.append(str(val))
                        if recipient_strs:
                            f.write(f"To: {', '.join(recipient_strs)}\n")
                    
                    if msg.subject:
                        f.write(f"Subject: {msg.subject}\n")
                    
                    if msg.event_start:
                        end_str = msg.event_end.strftime('%Y-%m-%d %H:%M:%S') if msg.event_end else 'N/A'
                        f.write(f"Event: {msg.event_start.strftime('%Y-%m-%d %H:%M:%S')} - {end_str}\n")
                    
                    body_preview = msg.body[:max_preview]
                    if len(msg.body) > max_preview:
                        body_preview += '...'
                    f.write(f"\n{body_preview}\n")
                    f.write("-" * 80 + "\n")
        except IOError as e:
            raise IOError(f"Failed to write timeline export to {output_path}: {e}")
    
    def get_platform_counts(self) -> Dict[str, int]:
        """
        Get message counts by platform
        
        Returns:
            Dictionary mapping platform names to counts
        """
        from collections import Counter
        return dict(Counter(m.platform for m in self.messages))
    
    def get_top_contacts(self, n: int = 10) -> List[tuple]:
        """
        Get top N contacts by message count
        
        Args:
            n: Number of top contacts to return
            
        Returns:
            List of (contact_identifier, count) tuples
        """
        from collections import Counter
        sender_counts = Counter()
        for msg in self.messages:
            sender = msg.sender
            key = sender.phone or sender.email or sender.name or sender.platform_id
            if key:
                sender_counts[key] += 1
        return sender_counts.most_common(n)
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive analytics summary
        
        Returns:
            Dictionary with analytics data
        """
        from collections import Counter
        
        # Count by platform
        platform_counts = self.get_platform_counts()
        
        # Top contacts
        top_contacts = dict(self.get_top_contacts(10))
        
        # Message type breakdown
        tapbacks = sum(1 for m in self.messages if '[Tapback' in m.body)
        with_text = sum(1 for m in self.messages if m.body and not m.body.startswith('[') and len(m.body.strip()) > 0)
        attachments = sum(1 for m in self.messages if '[Attachment]' in m.body)
        app_shares = sum(1 for m in self.messages if '[App Share]' in m.body)
        
        return {
            'total_messages': len(self.messages),
            'unique_contacts': len(self.contact_registry),
            'platforms': platform_counts,
            'top_contacts': top_contacts,
            'message_types': {
                'tapbacks': tapbacks,
                'with_text': with_text,
                'attachments': attachments,
                'app_shares': app_shares,
            }
        }

