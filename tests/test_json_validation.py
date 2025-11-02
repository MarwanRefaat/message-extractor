"""
Comprehensive tests for JSON validation and output robustness
"""
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from schema import UnifiedLedger, Message, Contact
from datetime import datetime
from utils.validators import (
    validate_contact, validate_message, validate_ledger,
    sanitize_contact, sanitize_message, sanitize_json_data,
    ValidationError
)


def test_valid_contact():
    """Test validation of a valid contact"""
    contact = {
        'name': 'John Doe',
        'email': 'john@example.com',
        'phone': '+1234567890',
        'platform_id': '+1234567890',
        'platform': 'imessage'
    }
    errors = validate_contact(contact)
    assert len(errors) == 0, f"Valid contact had errors: {errors}"


def test_invalid_email():
    """Test detection of invalid email"""
    contact = {
        'name': 'John Doe',
        'email': 'invalid-email',
        'phone': '+1234567890',
        'platform_id': '+1234567890',
        'platform': 'imessage'
    }
    errors = validate_contact(contact)
    assert len(errors) > 0, "Invalid email not detected"
    assert any('email' in err for err in errors), "Email validation error not found"


def test_invalid_platform():
    """Test detection of invalid platform"""
    contact = {
        'name': 'John Doe',
        'email': None,
        'phone': '+1234567890',
        'platform_id': '+1234567890',
        'platform': 'invalid_platform'
    }
    errors = validate_contact(contact)
    assert len(errors) > 0, "Invalid platform not detected"


def test_valid_message():
    """Test validation of a valid message"""
    message = {
        'message_id': 'imessage:ABC123',
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'timezone': None,
        'sender': {
            'name': None,
            'email': None,
            'phone': '+1234567890',
            'platform_id': '+1234567890',
            'platform': 'imessage'
        },
        'recipients': [{
            'name': 'Me',
            'email': None,
            'phone': None,
            'platform_id': 'me',
            'platform': 'imessage'
        }],
        'participants': [{
            'name': None,
            'email': None,
            'phone': '+1234567890',
            'platform_id': '+1234567890',
            'platform': 'imessage'
        }],
        'subject': None,
        'body': 'Test message',
        'attachments': [],
        'thread_id': None,
        'is_read': True,
        'is_starred': False,
        'is_reply': False,
        'original_message_id': None,
        'event_start': None,
        'event_end': None,
        'event_location': None,
        'event_status': None,
        'raw_data': {}
    }
    errors = validate_message(message)
    assert len(errors) == 0, f"Valid message had errors: {errors}"


def test_empty_body():
    """Test detection of empty body"""
    message = {
        'message_id': 'imessage:ABC123',
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'timezone': None,
        'sender': {
            'name': None,
            'email': None,
            'phone': '+1234567890',
            'platform_id': '+1234567890',
            'platform': 'imessage'
        },
        'recipients': [],
        'participants': [],
        'subject': None,
        'body': '',  # Empty body
        'attachments': [],
        'thread_id': None,
        'is_read': True,
        'is_starred': False,
        'is_reply': False,
        'original_message_id': None,
        'event_start': None,
        'event_end': None,
        'event_location': None,
        'event_status': None,
        'raw_data': {}
    }
    errors = validate_message(message)
    assert len(errors) > 0, "Empty body not detected"
    assert any('body' in err for err in errors)


def test_invalid_message_id():
    """Test detection of invalid message ID"""
    message = {
        'message_id': 'invalid_id',  # Invalid format
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'timezone': None,
        'sender': {'name': None, 'email': None, 'phone': '+1234567890', 'platform_id': '+1234567890', 'platform': 'imessage'},
        'recipients': [],
        'participants': [],
        'subject': None,
        'body': 'Test',
        'attachments': [],
        'thread_id': None,
        'is_read': True,
        'is_starred': False,
        'is_reply': False,
        'original_message_id': None,
        'event_start': None,
        'event_end': None,
        'event_location': None,
        'event_status': None,
        'raw_data': {}
    }
    errors = validate_message(message)
    assert len(errors) > 0, "Invalid message_id not detected"


def test_sanitize_null_bytes():
    """Test sanitization of null bytes"""
    dirty_string = "Hello\x00World"
    sanitized = sanitize_json_data({'messages': [{'body': dirty_string}]})
    assert '\x00' not in str(sanitized), "Null bytes not removed"


def test_sanitize_long_string():
    """Test truncation of very long strings"""
    long_body = "A" * 200000  # 200KB
    sanitized_msg = sanitize_message({'body': long_body})
    assert len(sanitized_msg['body']) < 200000, "Long string not truncated"
    assert '...' in sanitized_msg['body'], "Truncation marker missing"


def test_sanitize_unusual_line_terminators():
    """Test removal of unusual line terminators"""
    from utils.validators import sanitize_string
    
    # Test Line Separator (LS)
    dirty = "Line 1\u2028Line 2"
    clean = sanitize_string(dirty)
    assert '\u2028' not in clean, "Line Separator not removed"
    
    # Test Paragraph Separator (PS)
    dirty = "Para 1\u2029Para 2"
    clean = sanitize_string(dirty)
    assert '\u2029' not in clean, "Paragraph Separator not removed"
    
    # Test both
    dirty = "Text\u2028with\u2029both"
    clean = sanitize_string(dirty)
    assert '\u2028' not in clean and '\u2029' not in clean, "Unusual terminators not removed"


def test_end_to_end_extraction():
    """Test end-to-end extraction produces valid JSON"""
    # This test should be run with actual extractors
    pass


def test_mutually_exclusive_structure():
    """Test that no fields overlap"""
    message = {
        'message_id': 'imessage:ABC123',
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'timezone': None,
        'sender': {'name': None, 'email': None, 'phone': '+1234567890', 'platform_id': '+1234567890', 'platform': 'imessage'},
        'recipients': [],
        'participants': [],
        'subject': None,
        'body': 'Test',
        'attachments': [],
        'thread_id': None,
        'is_read': True,
        'is_starred': False,
        'is_reply': False,
        'original_message_id': None,
        'event_start': None,
        'event_end': None,
        'event_location': None,
        'event_status': None,
        'raw_data': {}
    }
    
    # Check all required fields are present
    errors = validate_message(message)
    assert len(errors) == 0
    
    # Verify JSON serialization works
    json_str = json.dumps(message)
    parsed = json.loads(json_str)
    assert parsed == message, "JSON serialization roundtrip failed"


def run_all_tests():
    """Run all validation tests"""
    print("Running JSON validation tests...")
    
    tests = [
        test_valid_contact,
        test_invalid_email,
        test_invalid_platform,
        test_valid_message,
        test_empty_body,
        test_invalid_message_id,
        test_sanitize_null_bytes,
        test_sanitize_long_string,
        test_sanitize_unusual_line_terminators,
        test_mutually_exclusive_structure
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

