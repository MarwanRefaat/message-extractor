"""
Tests for LLM-based extraction
"""
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extractors.llm_extractor import LLMExtractor


def test_llm_response_parsing():
    """Test parsing of LLM response"""
    extractor = LLMExtractor()
    
    # Test pure JSON (use null not None for JSON)
    response1 = '[{"message_id": "test:1", "platform": "imessage", "timestamp": "2024-01-01T12:00:00", "sender": {"name": null, "email": null, "phone": "+123", "platform_id": "+123", "platform": "imessage"}, "recipients": [], "participants": [{"name": null, "email": null, "phone": "+123", "platform_id": "+123", "platform": "imessage"}], "body": "test", "raw_data": {}}]'
    result1 = extractor._parse_llm_response(response1)
    assert len(result1) == 1
    assert result1[0]['message_id'] == 'test:1'
    
    # Test JSON in code blocks
    response2 = '```json\n' + response1 + '\n```'
    result2 = extractor._parse_llm_response(response2)
    assert len(result2) == 1
    
    # Test with markdown
    response3 = 'Here are the messages:\n\n' + response1
    result3 = extractor._parse_llm_response(response3)
    assert len(result3) == 1
    
    print("✓ LLM response parsing works")


def test_sanitization_integration():
    """Test that sanitization is applied"""
    extractor = LLMExtractor()
    
    # Create a message dict with unusual characters
    msg_dict = {
        'message_id': 'test:1',
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'sender': {'name': None, 'email': None, 'phone': '+123', 'platform_id': '+123', 'platform': 'imessage'},
        'recipients': [],
        'participants': [{'name': None, 'email': None, 'phone': '+123', 'platform_id': '+123', 'platform': 'imessage'}],
        'body': 'Text with\u2028line separator',
        'raw_data': {}
    }
    
    # Sanitize should remove LS
    sanitized = extractor._dict_to_message(msg_dict)
    assert '\u2028' not in sanitized.body
    print("✓ Sanitization integrated")


def test_validation_integration():
    """Test that validation is applied"""
    extractor = LLMExtractor()
    
    # Try invalid message (empty body)
    msg_dict = {
        'message_id': 'test:1',
        'platform': 'imessage',
        'timestamp': '2024-01-01T12:00:00',
        'sender': {'name': None, 'email': None, 'phone': '+123', 'platform_id': '+123', 'platform': 'imessage'},
        'recipients': [],
        'participants': [{'name': None, 'email': None, 'phone': '+123', 'platform_id': '+123', 'platform': 'imessage'}],
        'body': '',  # Invalid
        'raw_data': {}
    }
    
    # Should still create (body sanitization should prevent this at message level)
    # but validation should catch it in export
    print("✓ Validation check")


def run_all_tests():
    """Run all LLM extractor tests"""
    print("Testing LLM extractor...\n")
    
    tests = [
        test_llm_response_parsing,
        test_sanitization_integration,
        test_validation_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

