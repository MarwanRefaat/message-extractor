"""
JSON validation utilities for message extractor
Ensures robust, standardized JSON outputs
"""
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


# Regex patterns for validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
# Phone regex: allows +, digits, spaces, hyphens, parentheses, and parentheses with text (like "filtered")
PHONE_REGEX = re.compile(r'^\+?[\d\s\-()]+(\([^)]+\))?$')
PLATFORM_REGEX = re.compile(r'^(imessage|whatsapp|gmail|gcal|googletakeoutcal|googletakeoutchat|googletakeoutmeet|googletakeoutcontacts)$')
MESSAGE_ID_REGEX = re.compile(r'^[a-z]+:[a-zA-Z0-9_-]+$')
TIMESTAMP_REGEX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$')


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


def validate_email(email: Optional[str]) -> bool:
    """Validate email format"""
    if email is None:
        return True
    return bool(EMAIL_REGEX.match(email))


def validate_phone(phone: Optional[str]) -> bool:
    """Validate phone number format"""
    if phone is None:
        return True
    return bool(PHONE_REGEX.match(phone))


def validate_platform(platform: str) -> bool:
    """Validate platform identifier"""
    return bool(PLATFORM_REGEX.match(platform))


def validate_message_id(message_id: str) -> bool:
    """Validate message ID format"""
    return bool(MESSAGE_ID_REGEX.match(message_id))


def validate_timestamp(timestamp: str) -> bool:
    """Validate ISO 8601 timestamp format"""
    return bool(TIMESTAMP_REGEX.match(timestamp))


def validate_contact(contact: Dict[str, Any]) -> List[str]:
    """
    Validate a contact dictionary
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required fields
    if 'platform_id' not in contact:
        errors.append("Missing required field: platform_id")
    if 'platform' not in contact:
        errors.append("Missing required field: platform")
    
    # Validate fields if present
    if 'email' in contact and contact['email'] is not None:
        if not validate_email(contact['email']):
            errors.append(f"Invalid email format: {contact['email']}")
    
    if 'phone' in contact and contact['phone'] is not None:
        if not validate_phone(contact['phone']):
            errors.append(f"Invalid phone format: {contact['phone']}")
    
    if 'platform' in contact:
        if not validate_platform(contact['platform']):
            errors.append(f"Invalid platform: {contact['platform']}")
    
    return errors


def validate_message(message: Dict[str, Any]) -> List[str]:
    """
    Validate a message dictionary
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required fields
    required_fields = ['message_id', 'platform', 'timestamp', 'sender', 'body']
    for field in required_fields:
        if field not in message:
            errors.append(f"Missing required field: {field}")
    
    # Validate message_id
    if 'message_id' in message:
        if not validate_message_id(message['message_id']):
            errors.append(f"Invalid message_id format: {message['message_id']}")
    
    # Validate platform
    if 'platform' in message:
        if not validate_platform(message['platform']):
            errors.append(f"Invalid platform: {message['platform']}")
    
    # Validate timestamp
    if 'timestamp' in message:
        if not validate_timestamp(message['timestamp']):
            errors.append(f"Invalid timestamp format: {message['timestamp']}")
    
    # Validate sender
    if 'sender' in message:
        sender_errors = validate_contact(message['sender'])
        errors.extend([f"sender.{e}" for e in sender_errors])
    
    # Validate recipients (list of contacts)
    if 'recipients' in message:
        if not isinstance(message['recipients'], list):
            errors.append("recipients must be a list")
        else:
            for i, recipient in enumerate(message['recipients']):
                recipient_errors = validate_contact(recipient)
                errors.extend([f"recipients[{i}].{e}" for e in recipient_errors])
    
    # Validate participants (list of contacts)
    if 'participants' in message:
        if not isinstance(message['participants'], list):
            errors.append("participants must be a list")
        else:
            for i, participant in enumerate(message['participants']):
                participant_errors = validate_contact(participant)
                errors.extend([f"participants[{i}].{e}" for e in participant_errors])
    
    # Validate body is not empty (should be handled by extractors)
    if 'body' in message and not message['body']:
        errors.append("body cannot be empty")
    
    return errors


def validate_ledger(data: Dict[str, Any]) -> List[str]:
    """
    Validate a complete ledger export
    
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required top-level fields
    required_fields = ['total_messages', 'platforms', 'unique_contacts', 'messages']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate messages is a list
    if 'messages' in data:
        if not isinstance(data['messages'], list):
            errors.append("messages must be a list")
        else:
            # Validate each message
            for i, message in enumerate(data['messages']):
                message_errors = validate_message(message)
                errors.extend([f"messages[{i}].{e}" for e in message_errors])
    
    # Validate counts are consistent
    if 'messages' in data and isinstance(data['messages'], list):
        actual_count = len(data['messages'])
        if 'total_messages' in data:
            if data['total_messages'] != actual_count:
                errors.append(f"total_messages mismatch: expected {actual_count}, got {data['total_messages']}")
    
    return errors


def sanitize_string(value: Optional[str], max_length: int = 10000) -> Optional[str]:
    """
    Sanitize string values for safe JSON output
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string or None
    """
    if value is None:
        return None
    
    if not isinstance(value, str):
        return str(value)
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Remove unusual line terminators (LS, PS) that cause issues in JSON
    # LS (Line Separator, U+2028) and PS (Paragraph Separator, U+2029)
    # These are problematic in JSON strings
    value = value.replace('\u2028', ' ')  # Line Separator
    value = value.replace('\u2029', ' ')  # Paragraph Separator
    
    # Truncate if too long
    if len(value) > max_length:
        return value[:max_length] + "..."
    
    return value


def sanitize_contact(contact: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize contact data for JSON output"""
    return {
        'name': sanitize_string(contact.get('name'), 500),
        'email': sanitize_string(contact.get('email'), 500),
        'phone': sanitize_string(contact.get('phone'), 50),
        'platform_id': sanitize_string(contact.get('platform_id'), 500),
        'platform': sanitize_string(contact.get('platform'), 50)
    }


def sanitize_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize message data for JSON output"""
    sanitized = {
        'message_id': sanitize_string(message.get('message_id'), 500),
        'platform': sanitize_string(message.get('platform'), 50),
        'timestamp': message.get('timestamp'),
        'timezone': sanitize_string(message.get('timezone'), 100),
        'sender': sanitize_contact(message.get('sender', {})),
        'recipients': [sanitize_contact(r) for r in message.get('recipients', [])],
        'participants': [sanitize_contact(p) for p in message.get('participants', [])],
        'subject': sanitize_string(message.get('subject'), 1000),
        'body': sanitize_string(message.get('body'), 100000),
        'attachments': [sanitize_string(a, 1000) for a in message.get('attachments', [])],
        'thread_id': sanitize_string(message.get('thread_id'), 500),
        'is_read': message.get('is_read'),
        'is_starred': message.get('is_starred'),
        'is_reply': message.get('is_reply'),
        'original_message_id': sanitize_string(message.get('original_message_id'), 500),
        'event_start': message.get('event_start'),
        'event_end': message.get('event_end'),
        'event_location': sanitize_string(message.get('event_location'), 500),
        'event_status': sanitize_string(message.get('event_status'), 100),
        'raw_data': message.get('raw_data', {})
    }
    
    # Ensure body is not None
    if sanitized['body'] is None:
        sanitized['body'] = ""
    
    return sanitized


def sanitize_json_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize entire ledger data for JSON output"""
    if 'messages' in data and isinstance(data['messages'], list):
        data['messages'] = [sanitize_message(msg) for msg in data['messages']]
    return data

