"""
Example usage of the message extractor
Demonstrates how to use the API programmatically
"""
from schema import UnifiedLedger
from extractors import iMessageExtractor


def example_basic_usage():
    """Basic example: extract iMessage data"""
    print("Extracting iMessage data...")
    
    try:
        extractor = iMessageExtractor()
        ledger = extractor.extract_all()
        
        print(f"Extracted {len(ledger.messages)} messages")
        print(f"Unique contacts: {len(ledger.contact_registry)}")
        
        # Get timeline
        timeline = ledger.generate_timeline()
        print(f"\nFirst 5 messages:")
        for msg in timeline[:5]:
            print(f"  {msg.timestamp} - {msg.platform} - From: {msg.sender.name}")
        
        # Export unified data
        ledger.export_to_json("example_output.json")
        ledger.export_timeline_text("example_timeline.txt")
        
        print("\nExample completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")


def example_contact_linking():
    """Example: find all messages with a specific contact"""
    print("Finding messages with specific contact...")
    
    try:
        extractor = iMessageExtractor()
        ledger = extractor.extract_all()
        
        # Find all messages with a specific contact
        # This works across all platforms
        contact_key = "+1234567890"  # Replace with actual phone/email
        conversations = ledger.get_conversations_with_contact(contact_key)
        
        print(f"\nFound {len(conversations)} messages with {contact_key}")
        for msg in conversations[:10]:
            print(f"  {msg.timestamp} - {msg.platform}: {msg.body[:50]}...")
        
    except Exception as e:
        print(f"Error: {e}")


def example_cross_platform():
    """Example: unified ledger from multiple platforms"""
    print("Creating unified ledger from multiple platforms...")
    
    unified_ledger = UnifiedLedger()
    
    # Add iMessage
    try:
        print("\nExtracting iMessage...")
        extractor = iMessageExtractor()
        ledger = extractor.extract_all()
        for msg in ledger.messages:
            unified_ledger.add_message(msg)
        print(f"  Added {len(ledger.messages)} iMessage records")
    except Exception as e:
        print(f"  Skipping iMessage: {e}")
    
    # Add Gmail (requires credentials)
    # try:
    #     print("\nExtracting Gmail...")
    #     extractor = GmailExtractor()
    #     ledger = extractor.extract_all()
    #     for msg in ledger.messages:
    #         unified_ledger.add_message(msg)
    #     print(f"  Added {len(ledger.messages)} Gmail records")
    # except Exception as e:
    #     print(f"  Skipping Gmail: {e}")
    
    # Add Google Calendar (requires credentials)
    # try:
    #     print("\nExtracting Google Calendar...")
    #     extractor = GoogleCalendarExtractor()
    #     ledger = extractor.extract_all()
    #     for msg in ledger.messages:
    #         unified_ledger.add_message(msg)
    #     print(f"  Added {len(ledger.messages)} Calendar records")
    # except Exception as e:
    #     print(f"  Skipping Calendar: {e}")
    
    print(f"\nTotal messages in unified ledger: {len(unified_ledger.messages)}")
    print(f"Platforms: {', '.join(set(m.platform for m in unified_ledger.messages))}")
    
    # Export unified timeline
    unified_ledger.export_timeline_text("unified_example.txt")
    print("\nExported to unified_example.txt")


if __name__ == "__main__":
    print("="*80)
    print("Message Extractor - Example Usage")
    print("="*80)
    
    # Run examples
    example_basic_usage()
    # example_contact_linking()
    # example_cross_platform()

