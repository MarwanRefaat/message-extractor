# Repository Reorganization Plan

## Current Problems

1. **Cluttered root** - Too many files at top level
2. **Duplicate databases** - chats.db, sample_chats.db, database/chats.db
3. **Duplicate documentation** - Multiple summary files saying similar things
4. **Scattered scripts** - Import scripts not organized
5. **Unclear separation** - Core code vs scripts vs output
6. **Redundant exports** - IMESSAGE_EXPORT_TEMP at root + archived
7. **Multiple log files** - import.log, import_all.log scattered
8. **Confusing entry points** - main.py, create_chat_database.py, import_whatsapp.py

## Proposed Structure

```
message-extractor/
├── README.md                          # Main overview
├── QUICKSTART.md                      # Quick start guide
├── requirements.txt                   # Dependencies
├── setup.py                           # Package setup
├── .gitignore                         # Git ignore rules
│
├── src/                              # Core library code
│   ├── __init__.py
│   ├── schema.py                     # Data models
│   ├── constants.py                  # Constants
│   ├── exceptions.py                 # Custom exceptions
│   │
│   ├── extractors/                   # Extraction modules
│   │   ├── __init__.py
│   │   ├── imessage_extractor.py
│   │   ├── whatsapp_extractor.py
│   │   ├── gmail_extractor.py
│   │   ├── gcal_extractor.py
│   │   ├── google_takeout_*.py
│   │   ├── llm_extractor.py
│   │   └── ocr_extractor.py
│   │
│   └── utils/                        # Utilities
│       ├── __init__.py
│       ├── logger.py
│       ├── validators.py
│       ├── contacts.py
│       └── progress.py
│
├── scripts/                          # Executable scripts
│   ├── extract.py                    # Main extraction script
│   ├── create_database.py            # Database creation
│   ├── import_whatsapp.py            # WhatsApp import
│   └── generate_report.py            # Report generation
│
├── database/                         # Database workspace
│   ├── README.md                     # Database docs
│   ├── schema_diagram.md             # Visual schema
│   ├── database_erd.md               # ERD diagram
│   └── .gitignore                    # Ignore .db files
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # Architecture overview
│   ├── DATABASE.md                   # Database docs
│   ├── EXTRACTION.md                 # Extraction guide
│   ├── API.md                        # API reference
│   └── examples/                     # Usage examples
│
├── tests/                            # Test suite
│   ├── test_extractors.py
│   ├── test_validators.py
│   ├── test_database.py
│   └── fixtures/                     # Test data
│
├── data/                             # Data directories
│   ├── raw/                          # Raw exports (gitignored)
│   │   ├── imessage/
│   │   ├── whatsapp/
│   │   ├── gmail/
│   │   └── gcal/
│   │
│   ├── unified/                      # Processed data (gitignored)
│   │   ├── unified_ledger.json
│   │   └── unified_timeline.txt
│   │
│   ├── exports/                      # Archived exports (gitignored)
│   │   ├── imessage/
│   │   ├── contacts/
│   │   └── takeout/
│   │
│   └── database/                     # Database files (gitignored)
│       ├── chats.db
│       └── backups/
│
└── .github/                          # GitHub config
    ├── workflows/                    # CI/CD
    └── ISSUE_TEMPLATE/               # Issue templates
```

## Key Changes

### 1. Core Code to `src/`
- Move schema.py, constants.py, exceptions.py to src/
- Move extractors/ and utils/ to src/
- Makes it a proper Python package

### 2. Scripts to `scripts/`
- `main.py` → `scripts/extract.py` (main extraction)
- `create_chat_database.py` → `scripts/create_database.py`
- `import_whatsapp_to_database.py` → `scripts/import_whatsapp.py`
- Make them executable with shebangs

### 3. Organize Data
- All data goes to `data/` (gitignored)
- Clear separation: raw, unified, exports, database
- No more scattered .db files at root

### 4. Clean Documentation
- Merge duplicate summaries
- Organize by topic in `docs/`
- Keep QUICKSTART.md and README.md at root

### 5. Archive External Tools
- Keep `_archived_tools/` for reference
- Don't delete, but clearly mark as archived

### 6. Single Database Location
- All databases in `data/database/`
- Backups in `data/database/backups/`

### 7. Clear Entry Points
```bash
# Extraction
python -m scripts.extract --extract-all

# Database
python -m scripts.create_database

# Import
python -m scripts.import_whatsapp
```

## Migration Steps

1. Create new directory structure
2. Move files systematically
3. Update all imports
4. Update documentation
5. Update .gitignore
6. Test everything works
7. Remove old files

## Benefits

✅ **Clear separation** - Code, scripts, docs, data
✅ **Proper package** - Python package structure
✅ **No redundancy** - Single source of truth
✅ **Easy to navigate** - Logical grouping
✅ **Better imports** - Package imports work
✅ **Clearer docs** - Organized by topic
✅ **Clean root** - Only essential files

