"""
Main orchestrator script for message extraction
Extracts from iMessage, WhatsApp, Gmail, and Google Calendar
"""
import os
import argparse
import sys
import inspect
from pathlib import Path

from schema import UnifiedLedger
from constants import (
    FILTER_START_DATE, OUTPUT_DIR, RAW_DIR, UNIFIED_DIR,
    DEFAULT_MAX_RESULTS, UNIFIED_LEDGER_JSON, UNIFIED_TIMELINE_TXT
)
from extractors import (
    iMessageExtractor, WhatsAppExtractor, GmailExtractor, GoogleCalendarExtractor,
    AppleMailExtractor, LocalCalendarExtractor
)
from exceptions import (
    MessageExtractorError, ConfigurationError, ExtractionError
)
from utils.logger import get_logger

logger = get_logger('main')


def extract_platform(extractor, platform_name: str, raw_dir: Path, raw_only: bool = False, 
                     unified_ledger: UnifiedLedger = None, max_results: int = DEFAULT_MAX_RESULTS):
    """
    Extract messages from a platform
    
    Args:
        extractor: Platform extractor instance
        platform_name: Name of the platform for logging
        raw_dir: Directory for raw exports
        raw_only: Whether to skip unified ledger
        unified_ledger: Unified ledger to add messages to
        max_results: Maximum results to extract
        
    Returns:
        Number of extracted messages
    """
    logger.info(f"Extracting {platform_name} data...")
    
    try:
        # Export raw data
        if hasattr(extractor, 'export_raw'):
            # Check if export_raw accepts max_results parameter
            sig = inspect.signature(extractor.export_raw)
            if 'max_results' in sig.parameters:
                extractor.export_raw(str(raw_dir), max_results=max_results)
            else:
                extractor.export_raw(str(raw_dir))
        
        if raw_only or unified_ledger is None:
            return 0
        
        # Extract and add to unified ledger
        # Check if extract_all accepts max_results parameter
        sig = inspect.signature(extractor.extract_all)
        if 'max_results' in sig.parameters:
            ledger = extractor.extract_all(max_results=max_results)
        else:
            ledger = extractor.extract_all()
        
        for msg in ledger.messages:
            unified_ledger.add_message(msg)
        
        logger.info(f"✓ Extracted {len(ledger.messages)} {platform_name} records")
        return len(ledger.messages)
        
    except Exception as e:
        logger.error(f"✗ Error extracting {platform_name}: {e}")
        raise ExtractionError(f"Failed to extract {platform_name}: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Extract messages from iMessage, WhatsApp, Apple Mail, and Local Calendar",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --extract-imessage
  python main.py --extract-all
  python main.py --extract-gmail --extract-gcal  # Apple Mail & Local Calendar
  python main.py --extract-whatsapp --whatsapp-db /path/to/db
        """
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=OUTPUT_DIR,
        help=f'Output directory for extracted data (default: {OUTPUT_DIR})'
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
        default=DEFAULT_MAX_RESULTS,
        help=f'Maximum number of records to extract per source (default: {DEFAULT_MAX_RESULTS})'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / RAW_DIR
    unified_dir = output_dir / UNIFIED_DIR
    
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(unified_dir, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("Message Extractor - Starting extraction")
    logger.info("=" * 80)
    
    # Create unified ledger with start date of 2024-01-01
    unified_ledger = UnifiedLedger(start_date=FILTER_START_DATE)
    logger.info(f"Filtering messages from {FILTER_START_DATE.strftime('%Y-%m-%d')} onwards")
    
    extracted_count = 0
    
    # Extract iMessage
    if args.extract_all or args.extract_imessage:
        try:
            extractor = iMessageExtractor()
            count = extract_platform(extractor, "iMessage", raw_dir, args.raw_only, unified_ledger)
            extracted_count += count
        except MessageExtractorError as e:
            logger.error(f"Skipping iMessage: {e}")
    
    # Extract WhatsApp
    if args.extract_all or args.extract_whatsapp:
        if not args.whatsapp_db:
            logger.warning("--whatsapp-db not specified, skipping WhatsApp extraction")
        else:
            try:
                extractor = WhatsAppExtractor(args.whatsapp_db)
                count = extract_platform(extractor, "WhatsApp", raw_dir, args.raw_only, unified_ledger)
                extracted_count += count
            except MessageExtractorError as e:
                logger.error(f"Skipping WhatsApp: {e}")
    
    # Extract Apple Mail (replaces Gmail - local Mail.app)
    if args.extract_all or args.extract_gmail:
        try:
            extractor = AppleMailExtractor()
            count = extract_platform(extractor, "Apple Mail", raw_dir, args.raw_only, unified_ledger, args.max_results)
            extracted_count += count
        except (MessageExtractorError, FileNotFoundError, ImportError) as e:
            logger.warning(f"Skipping Apple Mail: {e}")
    
    # Extract Local Calendar (replaces Google Calendar - local Calendar.app)
    if args.extract_all or args.extract_gcal:
        try:
            extractor = LocalCalendarExtractor()
            count = extract_platform(extractor, "Local Calendar", raw_dir, args.raw_only, unified_ledger, args.max_results)
            extracted_count += count
        except (MessageExtractorError, FileNotFoundError, ImportError) as e:
            logger.warning(f"Skipping Local Calendar: {e}")
    
    # Export unified ledger
    if not args.raw_only and unified_ledger.messages:
        logger.info("=" * 80)
        logger.info("Creating unified ledger...")
        logger.info("=" * 80)
        
        try:
            # Export JSON
            json_path = unified_dir / UNIFIED_LEDGER_JSON
            unified_ledger.export_to_json(str(json_path))
            logger.info(f"✓ Exported unified JSON ledger: {json_path}")
            
            # Export text timeline
            text_path = unified_dir / UNIFIED_TIMELINE_TXT
            unified_ledger.export_timeline_text(str(text_path))
            logger.info(f"✓ Exported unified text timeline: {text_path}")
            
            logger.info(f"\nSummary:")
            logger.info(f"  Total messages: {len(unified_ledger.messages)}")
            logger.info(f"  Unique contacts: {len(unified_ledger.contact_registry)}")
            logger.info(f"  Platforms: {', '.join(sorted(set(m.platform for m in unified_ledger.messages)))}")
            
            # Analytics
            platform_counts = unified_ledger.get_platform_counts()
            if platform_counts:
                logger.info(f"\nMessages by platform:")
                for platform, count in sorted(platform_counts.items(), key=lambda x: x[1], reverse=True):
                    logger.info(f"  {platform}: {count:,}")
            
            top_contacts = unified_ledger.get_top_contacts(10)
            if top_contacts:
                logger.info(f"\nTop 10 contacts:")
                for contact, count in top_contacts:
                    logger.info(f"  {contact}: {count:,}")
            
        except Exception as e:
            logger.error(f"Failed to export unified ledger: {e}")
    
    logger.info("=" * 80)
    logger.info("Extraction complete!")
    logger.info("=" * 80)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"  - Raw data: {raw_dir}")
    if not args.raw_only:
        logger.info(f"  - Unified ledger: {unified_dir}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
