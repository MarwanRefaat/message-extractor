#!/usr/bin/env python3
"""
Full Gmail extraction using gmail-exporter
Extracts emails from INBOX and SENT, filters for target emails, and creates unified ledger
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extractors.gmail_extractor import GmailExtractor
from utils.logger import get_logger

logger = get_logger('gmail_extraction')

print("=" * 70)
print("Gmail Extraction - Full Run")
print("=" * 70)
print()

try:
    # Initialize extractor
    extractor = GmailExtractor(export_dir="gmail_export")
    
    print(f"✓ Extractor initialized")
    print(f"  Binary: {extractor.gmail_exporter_path}")
    print(f"  Export dir: {extractor.export_dir}")
    print(f"  Target emails: {extractor.TARGET_EMAILS}")
    print(f"  Start date filter: {extractor.start_date.strftime('%Y-%m-%d')}")
    print()
    
    # Extract all emails
    print("Starting email extraction...")
    print("(This will export emails from INBOX and SENT folders)")
    print()
    
    ledger = extractor.extract_all(max_results=10000)
    
    print()
    print("=" * 70)
    print("Extraction Complete!")
    print("=" * 70)
    print(f"  Total messages extracted: {len(ledger.messages)}")
    print(f"  Unique contacts: {len(ledger.contact_registry)}")
    print()
    
    # Show some stats
    if ledger.messages:
        platform_counts = ledger.get_platform_counts()
        if platform_counts:
            print("Messages by platform:")
            for platform, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {platform}: {count:,}")
        
        print()
        top_contacts = ledger.get_top_contacts(10)
        if top_contacts:
            print("Top 10 contacts:")
            for contact, count in top_contacts:
                print(f"  {contact}: {count:,}")
    
    print()
    print(f"✓ EML files saved to: {extractor.eml_dir}")
    print(f"✓ Spreadsheet saved to: {extractor.spreadsheet_path}")
    print()
    print("The extracted messages are now in the UnifiedLedger object.")
    print("You can export them using ledger.export_to_json() or similar methods.")
    
except KeyboardInterrupt:
    logger.warning("\nInterrupted by user")
    sys.exit(130)
except Exception as e:
    logger.error(f"Error during extraction: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

