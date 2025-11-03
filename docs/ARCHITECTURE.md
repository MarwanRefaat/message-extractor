# Repository Architecture

## Directory Structure

```
message-extractor/
├── src/                          # Core library code
│   ├── __init__.py               # Package initialization
│   ├── schema.py                 # Data models (Message, Contact, UnifiedLedger)
│   ├── constants.py              # Configuration constants
│   ├── exceptions.py             # Custom exceptions
│   │
│   ├── extractors/               # Platform-specific extractors
│   │   ├── __init__.py
│   │   ├── imessage_extractor.py
│   │   ├── gmail_extractor.py
│   │   ├── gcal_extractor.py
│   │   ├── google_takeout_*.py   # Various Google Takeout extractors
│   │   ├── llm_extractor.py      # LLM-based extraction
│   │   └── ocr_extractor.py      # OCR extraction
│   │
│   └── utils/                    # Utility modules
│       ├── __init__.py
│       ├── logger.py             # Logging utilities
│       ├── validators.py         # JSON/data validation
│       ├── contacts.py           # Contact management
│       └── progress.py           # Progress tracking
│
├── scripts/                      # Executable scripts
│   ├── extract.py                # Main extraction script
│   ├── create_database.py        # Database creation & import
│   └── import_whatsapp.py        # WhatsApp import
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           # This file
│   ├── DATABASE.md               # Database documentation
│   ├── EXTRACTION.md             # Extraction guides
│   ├── JSON_SCHEMA.md            # JSON format spec
│   ├── SQL_SCHEMA.md             # SQL schema documentation
│   └── LLM_EXTRACTION.md         # LLM usage guide
│
├── tests/                        # Test suite
│   ├── test_extractors.py
│   ├── test_validators.py
│   └── test_llm_extractor.py
│
├── data/                         # All data (gitignored)
│   ├── raw/                      # Raw platform exports
│   ├── unified/                  # Processed unified data
│   ├── exports/                  # Archived exports
│   └── database/                 # SQLite databases
│       ├── chats.db              # Main database
│       ├── *.md                  # Schema docs
│       └── *.sql                 # Migration scripts
│
├── _archived_exports/            # Archived export data
│   ├── IMESSAGE_EXPORT/
│   ├── CONTACTS_EXPORT/
│   └── raw_originals/
│
├── _archived_tools/              # Archived external tools
│   ├── gmail-exporter/
│   ├── imessage-exporter/
│   └── WhatsApp-Chat-Exporter/
│
├── README.md                     # Main project overview
├── QUICKSTART.md                 # Quick start guide
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                       # MIT License
├── requirements.txt              # Python dependencies
├── setup.py                      # Package setup
├── install.sh                    # Installation script
└── run.sh                        # Main runner script
```

## Key Principles

### 1. Separation of Concerns
- **src/** - Pure library code, no execution
- **scripts/** - Executable scripts that use src/
- **docs/** - All documentation organized by topic
- **data/** - All data files in one place (gitignored)
- **tests/** - Test suite separate from code

### 2. No Redundancy
- Single source of truth for each file
- No duplicate databases
- One location for data
- Clear import paths

### 3. Clear Entry Points
```bash
# Extract messages
./run.sh --extract-all

# Create database
python scripts/create_database.py

# Import WhatsApp
python scripts/import_whatsapp.py
```

### 4. Git-friendly
- All personal data in `data/` (gitignored)
- Code and docs tracked
- Archives preserved but gitignored
- Clean commit history

## Data Flow

### Extraction Flow
```
Platform → Extractor → Raw JSON → Unified Ledger → Database
```

### Import Flow
```
Export Files → Parser → Contact Matching → SQLite Database
```

## Module Responsibilities

### Core (src/)
- **schema.py** - Data models and structures
- **constants.py** - Configuration
- **exceptions.py** - Error handling

### Extractors (src/extractors/)
- Platform-specific extraction logic
- Convert platform format → unified schema
- Handle authentication and API calls

### Utils (src/utils/)
- Cross-cutting concerns
- Logging, validation, progress
- No business logic

### Scripts (scripts/)
- Main entry points
- Orchestrate extractors
- Handle CLI arguments
- Use core library

## Import Pattern

All scripts use the same import pattern:

```python
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Import from src
from schema import UnifiedLedger
from extractors import GmailExtractor
from utils.logger import get_logger
```

## File Naming Conventions

- **snake_case** - Python files
- **UPPERCASE** - Constants
- **PascalCase** - Classes
- **Descriptive** - Clear, explicit names

## Testing Structure

- Mirror src/ structure in tests/
- One test file per module
- Fixtures in tests/fixtures/
- Integration tests for workflows

## Documentation Organization

- **ARCHITECTURE.md** - This file (overview)
- **DATABASE.md** - Database schema and usage
- **EXTRACTION.md** - How extraction works
- **JSON_SCHEMA.md** - Unified JSON format
- **SQL_SCHEMA.md** - Database schema
- **LLM_EXTRACTION.md** - LLM features

## Extension Points

### Adding a New Extractor
1. Create `src/extractors/new_platform_extractor.py`
2. Implement extractor class
3. Add to `src/extractors/__init__.py`
4. Update scripts/extract.py if needed

### Adding a New Script
1. Create `scripts/new_script.py`
2. Add shebang and imports
3. Follow existing patterns
4. Document in README

### Adding Documentation
1. Add to `docs/`
2. Update `docs/ARCHITECTURE.md` index
3. Link from main README if appropriate

## Benefits

✅ **Maintainable** - Clear structure, easy to navigate
✅ **Testable** - Clean separation, easy to test
✅ **Extensible** - Simple to add features
✅ **Documented** - Comprehensive docs
✅ **Clean** - No redundancy, single source of truth

