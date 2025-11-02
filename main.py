"""
Main orchestrator script for message extraction
Extracts from iMessage, WhatsApp, Gmail, and Google Calendar
"""
import os
import argparse
import sys
from pathlib import Path
from datetime import datetime

from schema import UnifiedLedger
from extractors import iMessageExtractor, WhatsAppExtractor, GmailExtractor, GoogleCalendarExtractor


def main():
    parser = argparse.ArgumentParser(
        description="Extract messages from iMessage, WhatsApp, Gmail, and Google Calendar"
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./output',
        help='Output directory for extracted data (default: ./output)'
    )
    
    parser.add_argument(
        '--extract-imessage',
        action='store_true',
        help='Extract iMessage data'
    )
    
    parser.add_argument(
        '--extract-whatsapp',
        action='store_true',
        help='Extract WhatsApp data'
    )
    
    parser.add_argument(
        '--whatsapp-db',
        type=str,
        help='Path to WhatsApp database file'
    )
    
    parser.add_argument(
        '--extract-gmail',
        action='store_true',
        help='Extract Gmail data'
    )
    
    parser.add_argument(
        '--extract-gcal',
        action='store_true',
        help='Extract Google Calendar data'
    )
    
    parser.add_argument(
        '--extract-all',
        action='store_true',
        help='Extract from all available sources'
    )
    
    parser.add_argument(
        '--raw-only',
        action='store_true',
        help='Only export raw data, do not create unified ledger'
    )
    
    parser.add_argument(
        '--max-results',
        type=int,
        default=10000,
        help='Maximum number of records to extract per source (default: 10000)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    unified_dir = output_dir / "unified"
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(unified_dir, exist_ok=True)
    
    # Create unified ledger with start date of 2024-01-01
    start_date = datetime(2024, 1, 1)
    unified_ledger = UnifiedLedger(start_date=start_date)
    print(f"\nFiltering messages from {start_date.strftime('%Y-%m-%d')} onwards")
    
    extracted_count = 0
    
    # Extract iMessage
    if args.extract_all or args.extract_imessage:
        print("\n" + "="*80)
        print("Extracting iMessage data...")
        print("="*80)
        
        try:
            extractor = iMessageExtractor()
            
            # Export raw data
            extractor.export_raw(str(raw_dir))
            
            if not args.raw_only:
                ledger = extractor.extract_all()
                for msg in ledger.messages:
                    unified_ledger.add_message(msg)
                extracted_count += len(ledger.messages)
                print(f"Extracted {len(ledger.messages)} iMessage records")
        
        except Exception as e:
            print(f"Error extracting iMessage: {e}")
    
    # Extract WhatsApp
    if args.extract_all or args.extract_whatsapp:
        print("\n" + "="*80)
        print("Extracting WhatsApp data...")
        print("="*80)
        
        if not args.whatsapp_db:
            print("Warning: --whatsapp-db not specified, skipping WhatsApp extraction")
        else:
            try:
                extractor = WhatsAppExtractor(args.whatsapp_db)
                
                # Export raw data
                extractor.export_raw(str(raw_dir))
                
                if not args.raw_only:
                    ledger = extractor.extract_all()
                    for msg in ledger.messages:
                        unified_ledger.add_message(msg)
                    extracted_count += len(ledger.messages)
                    print(f"Extracted {len(ledger.messages)} WhatsApp records")
            
            except Exception as e:
                print(f"Error extracting WhatsApp: {e}")
    
    # Extract Gmail
    if args.extract_all or args.extract_gmail:
        print("\n" + "="*80)
        print("Extracting Gmail data...")
        print("="*80)
        
        try:
            extractor = GmailExtractor()
            
            # Export raw data
            extractor.export_raw(str(raw_dir), max_results=args.max_results)
            
            if not args.raw_only:
                ledger = extractor.extract_all(max_results=args.max_results)
                for msg in ledger.messages:
                    unified_ledger.add_message(msg)
                extracted_count += len(ledger.messages)
                print(f"Extracted {len(ledger.messages)} Gmail records")
        
        except Exception as e:
            print(f"Error extracting Gmail: {e}")
    
    # Extract Google Calendar
    if args.extract_all or args.extract_gcal:
        print("\n" + "="*80)
        print("Extracting Google Calendar data...")
        print("="*80)
        
        try:
            extractor = GoogleCalendarExtractor()
            
            # Export raw data
            extractor.export_raw(str(raw_dir), max_results=args.max_results)
            
            if not args.raw_only:
                ledger = extractor.extract_all(max_results=args.max_results)
                for msg in ledger.messages:
                    unified_ledger.add_message(msg)
                extracted_count += len(ledger.messages)
                print(f"Extracted {len(ledger.messages)} Google Calendar records")
        
        except Exception as e:
            print(f"Error extracting Google Calendar: {e}")
    
    # Export unified ledger
    if not args.raw_only and unified_ledger.messages:
        print("\n" + "="*80)
        print("Creating unified ledger...")
        print("="*80)
        
        # Export JSON
        json_path = unified_dir / "unified_ledger.json"
        unified_ledger.export_to_json(str(json_path))
        print(f"Exported unified JSON ledger: {json_path}")
        
        # Export text timeline
        text_path = unified_dir / "unified_timeline.txt"
        unified_ledger.export_timeline_text(str(text_path))
        print(f"Exported unified text timeline: {text_path}")
        
        print(f"\nTotal messages in unified ledger: {len(unified_ledger.messages)}")
        print(f"Unique contacts: {len(unified_ledger.contact_registry)}")
        print(f"Platforms: {', '.join(set(m.platform for m in unified_ledger.messages))}")
    
    print("\n" + "="*80)
    print("Extraction complete!")
    print("="*80)
    print(f"Output directory: {output_dir}")
    print(f"  - Raw data: {raw_dir}")
    if not args.raw_only:
        print(f"  - Unified ledger: {unified_dir}")


if __name__ == "__main__":
    main()

