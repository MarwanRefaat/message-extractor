#!/usr/bin/env python3
"""
Comprehensive test suite for message extractor
"""
import json
from collections import Counter
from datetime import datetime


def test_unified_ledger():
    """Test unified ledger structure and data quality"""
    print("\n" + "="*80)
    print("TEST: Unified Ledger Structure")
    print("="*80)
    
    with open('output/unified/unified_ledger.json') as f:
        data = json.load(f)
    
    # Check structure
    assert 'total_messages' in data, "Missing total_messages"
    assert 'platforms' in data, "Missing platforms"
    assert 'unique_contacts' in data, "Missing unique_contacts"
    assert 'messages' in data, "Missing messages"
    
    print(f"✓ Structure valid: {len(data.keys())} top-level keys")
    print(f"✓ Total messages: {data['total_messages']:,}")
    print(f"✓ Unique contacts: {data['unique_contacts']:,}")
    print(f"✓ Platforms: {data['platforms']}")
    
    # Validate messages
    assert len(data['messages']) == data['total_messages'], "Message count mismatch"
    print(f"✓ Message count validated: {len(data['messages']):,}")
    
    return data


def test_message_types(data):
    """Test message type categorization"""
    print("\n" + "="*80)
    print("TEST: Message Type Categorization")
    print("="*80)
    
    tapbacks = []
    with_text = []
    empty = []
    
    for msg in data['messages']:
        body = msg.get('body', '')
        if '[Tapback:' in body or '[Tapback/Reaction]' in body:
            tapbacks.append(msg)
        elif body and len(body.strip()) > 0:
            with_text.append(msg)
        else:
            empty.append(msg)
    
    print(f"✓ Total messages: {len(data['messages']):,}")
    print(f"✓ Tapbacks: {len(tapbacks):,} ({len(tapbacks)/len(data['messages'])*100:.1f}%)")
    print(f"✓ With text: {len(with_text):,} ({len(with_text)/len(data['messages'])*100:.1f}%)")
    print(f"✓ Empty: {len(empty):,} ({len(empty)/len(data['messages'])*100:.1f}%)")
    
    # Check for empty messages
    assert len(empty) == 0, f"Found {len(empty)} empty messages"
    print(f"✓ No empty messages!")
    
    # Check tapback breakdown
    tapback_types = Counter()
    for msg in tapbacks:
        body = msg.get('body', '')
        tapback_types[body] += 1
    
    print(f"\nTapback types:")
    for ttype, count in tapback_types.most_common():
        print(f"  {ttype}: {count:,} ({count/len(tapbacks)*100:.1f}%)")
    
    return True


def test_chronological_order(data):
    """Test that messages are in chronological order"""
    print("\n" + "="*80)
    print("TEST: Chronological Order")
    print("="*80)
    
    timestamps = []
    for msg in data['messages']:
        try:
            ts = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
            timestamps.append(ts)
        except Exception as e:
            print(f"ERROR: Invalid timestamp {msg['timestamp']}: {e}")
            return False
    
    is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
    print(f"✓ Chronological: {is_sorted}")
    
    if timestamps:
        print(f"✓ Date range: {min(timestamps).date()} to {max(timestamps).date()}")
    
    return is_sorted


def test_contact_info(data):
    """Test contact information is captured"""
    print("\n" + "="*80)
    print("TEST: Contact Information")
    print("="*80)
    
    contacts_with_info = []
    contacts_without_info = []
    
    for msg in data['messages']:
        sender = msg['sender']
        has_info = sender.get('phone') or sender.get('email') or sender.get('name')
        
        if has_info:
            contacts_with_info.append(sender)
        else:
            contacts_without_info.append(sender)
    
    print(f"✓ Contacts with info: {len(set(str(c) for c in contacts_with_info)):,}")
    print(f"✓ Contacts without info: {len(set(str(c) for c in contacts_without_info)):,}")
    
    # Check for "unknown" contacts
    unknown_count = sum(1 for msg in data['messages'] 
                       if msg['sender'].get('platform_id') == 'unknown')
    print(f"  Unknown contacts: {unknown_count:,} messages")
    
    return True


def test_tapback_details(data):
    """Test tapback type detection"""
    print("\n" + "="*80)
    print("TEST: Tapback Type Details")
    print("="*80)
    
    tapback_types = Counter()
    for msg in data['messages']:
        body = msg.get('body', '')
        if '[Tapback:' in body:
            tapback_types[body] += 1
    
    print(f"✓ Specific tapback types detected: {len(tapback_types)}")
    for ttype, count in tapback_types.most_common():
        print(f"  {ttype}: {count:,}")
    
    return True


def test_data_quality(data):
    """Test overall data quality"""
    print("\n" + "="*80)
    print("TEST: Data Quality Checks")
    print("="*80)
    
    issues = []
    
    # Check for required fields
    required_fields = ['message_id', 'platform', 'timestamp', 'sender', 'body']
    for msg in data['messages']:
        for field in required_fields:
            if field not in msg:
                issues.append(f"Missing field {field} in message {msg.get('message_id', 'unknown')}")
    
    if issues:
        print(f"✗ Found {len(issues)} issues")
        for issue in issues[:10]:
            print(f"  {issue}")
        return False
    else:
        print(f"✓ All messages have required fields")
    
    # Check for valid timestamps
    invalid_timestamps = 0
    for msg in data['messages']:
        try:
            datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
        except:
            invalid_timestamps += 1
    
    if invalid_timestamps > 0:
        print(f"✗ Found {invalid_timestamps} invalid timestamps")
        return False
    else:
        print(f"✓ All timestamps are valid")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    try:
        data = test_unified_ledger()
        assert test_message_types(data), "Message type test failed"
        assert test_chronological_order(data), "Chronological order test failed"
        assert test_contact_info(data), "Contact info test failed"
        assert test_tapback_details(data), "Tapback details test failed"
        assert test_data_quality(data), "Data quality test failed"
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
