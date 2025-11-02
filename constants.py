"""
Constants for the message extractor project
Centralizes all configuration and magic numbers
"""
from datetime import datetime

# Date filtering
FILTER_START_DATE = datetime(2024, 1, 1)

# iMessage constants
IMESSAGE_EPOCH = datetime(2001, 1, 1)
IMESSAGE_FILTER_TIMESTAMP_NS = int((FILTER_START_DATE - IMESSAGE_EPOCH).total_seconds() * 1e9)

# WhatsApp constants
WHATSAPP_FILTER_TIMESTAMP_MS = int(FILTER_START_DATE.timestamp() * 1000)

# Gmail constants
GMAIL_FILTER_QUERY = "after:2024/1/1"

# Google Calendar constants
GCAL_FILTER_TIME_MIN = FILTER_START_DATE.isoformat() + 'Z'

# API and performance
DEFAULT_MAX_RESULTS = 10000
GMAIL_API_PAGE_SIZE = 500
GCAL_API_PAGE_SIZE = 2500

# Output structure
OUTPUT_DIR = "./output"
RAW_DIR = "raw"
UNIFIED_DIR = "unified"

# Platform identifiers
PLATFORM_IMESSAGE = "imessage"
PLATFORM_WHATSAPP = "whatsapp"
PLATFORM_GMAIL = "gmail"
PLATFORM_GCAL = "gcal"
PLATFORMS_ALL = [
    PLATFORM_IMESSAGE,
    PLATFORM_WHATSAPP,
    PLATFORM_GMAIL,
    PLATFORM_GCAL
]

# File names
RAW_IMESSAGE_FILE = "imessage_raw.jsonl"
RAW_WHATSAPP_FILE = "whatsapp_raw.jsonl"
RAW_GMAIL_FILE = "gmail_raw.jsonl"
RAW_GCAL_FILE = "gcal_raw.jsonl"

UNIFIED_LEDGER_JSON = "unified_ledger.json"
UNIFIED_TIMELINE_TXT = "unified_timeline.txt"

# Credentials
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

