# Robustness System Summary

This document summarizes the comprehensive robustness system implemented across the message extractor project.

## System Components

### 1. Chunked Processing (`src/utils/chunked_processor.py`)

**Purpose**: Process items in small batches with incremental saving and resume capability

**Key Features:**
- ✅ Processes items in configurable chunks (default: 100 items)
- ✅ Saves results incrementally (every N items + after each chunk)
- ✅ Creates checkpoints for resumable processing
- ✅ Isolates individual item failures
- ✅ Tracks detailed statistics (processed/successful/failed/skipped)
- ✅ Thread-safe saves

**Use Cases:**
- Large dataset processing (emails, messages)
- Long-running extractions
- Network-dependent operations
- Any operation where failures shouldn't stop everything

### 2. Isolated LLM Processing (`IsolatedLLMProcessor`)

**Purpose**: Prevent LLM failures from crashing the entire extraction

**Key Features:**
- ✅ Automatic retry on LLM failures
- ✅ Optional fallback processing
- ✅ Continues processing even if LLM fails for some items
- ✅ Detailed logging of failures
- ✅ Configurable retry attempts

**Use Cases:**
- LLM-based extraction
- API calls that might timeout
- External service integrations

### 3. Enhanced Error Handling (`src/utils/error_handling.py`)

**Purpose**: Comprehensive utilities for safe operations

**Key Features:**
- Safe file I/O with automatic cleanup
- Safe database operations with transaction handling
- Safe subprocess execution with retries
- Path validation
- Data validation with fallbacks
- Retry logic with exponential backoff

### 4. Enhanced Logging (`src/utils/logger.py`)

**Purpose**: Better logging with file output

**Key Features:**
- ✅ Console logging (colored, formatted)
- ✅ File logging (detailed, DEBUG level)
- ✅ Automatic log directory creation
- ✅ Per-module log files
- ✅ Thread-safe logging

## Integration Examples

### Gmail Extractor

Now uses chunked processing by default:

```python
extractor = GmailExtractor()
ledger = extractor.extract_all(
    max_results=1000,
    use_chunked=True,   # Default: True
    chunk_size=50      # Process 50 emails per chunk
)
```

**What happens:**
1. Exports emails using gmail-exporter
2. Processes EML files in chunks of 50
3. Saves results incrementally (every 10 items + after each chunk)
4. Creates checkpoints for resume capability
5. If interrupted, can resume from last checkpoint

**Files created:**
- `gmail_export/checkpoints/progress.json` - Checkpoint file
- `gmail_export/results.jsonl` - Incremental results
- `logs/gmail_extractor.log` - Detailed log file (if enabled)

### LLM Extractor

Now uses isolated LLM processing:

```python
extractor = LLMExtractor()
ledger = extractor.extract_all(raw_data)

# Each LLM call is isolated:
# - Retries on failure
# - Returns None instead of crashing
# - Continues with next item
```

**What happens:**
1. LLM calls wrapped in `IsolatedLLMProcessor`
2. Failures logged but don't stop processing
3. Batch processing continues even if chunks fail
4. Individual message processing failures isolated

## Benefits

### Data Safety
- ✅ **Incremental Saving**: Results saved as they're processed, not all at once
- ✅ **Checkpointing**: Progress saved periodically
- ✅ **Resume Capability**: Can continue after interruption
- ✅ **No Data Loss**: Already processed items saved before interruption

### Robustness
- ✅ **Isolated Failures**: One item failure doesn't stop everything
- ✅ **Graceful Degradation**: Continues processing with partial failures
- ✅ **Error Recovery**: Automatic retries for transient failures
- ✅ **Resource Safety**: Automatic cleanup prevents leaks

### Observability
- ✅ **Progress Tracking**: Detailed statistics and progress logs
- ✅ **File Logging**: Detailed logs saved to files
- ✅ **Error Context**: Clear error messages with context
- ✅ **Performance Metrics**: Track success rates, processing time

## File Structure

```
project/
├── checkpoints/           # Processing checkpoints
│   └── progress.json
├── logs/                  # Log files
│   ├── gmail_extractor.log
│   └── llm_extractor.log
├── gmail_export/
│   ├── messages/          # EML files
│   ├── checkpoints/
│   │   └── progress.json
│   └── results.jsonl      # Incremental results
└── [other exports]/
```

## Configuration

### Chunked Processing

```python
processor = ChunkedProcessor(
    chunk_size=100,              # Items per chunk
    checkpoint_dir="checkpoints",
    result_file="results.jsonl",
    save_interval=10,            # Save every N items
    isolated_errors=True         # Continue on failures
)
```

### Logging

```python
logger = get_logger(
    'module_name',
    log_dir='logs',              # Log directory
    log_file='custom.log'        # Optional filename
)
```

## Migration Guide

### Updating Existing Extractors

**Before:**
```python
for item in items:
    result = process(item)
    results.append(result)
```

**After:**
```python
from utils.chunked_processor import ChunkedProcessor

processor = ChunkedProcessor(chunk_size=50)
results = processor.process_chunked(
    items=items,
    process_func=process,
    resume=True
)
```

### Adding LLM Isolation

**Before:**
```python
for item in items:
    result = llm.process(item)  # Crashes on failure
    results.append(result)
```

**After:**
```python
from utils.chunked_processor import IsolatedLLMProcessor

isolated = IsolatedLLMProcessor(llm_func=llm.process)
for item in items:
    result = isolated(item)  # Returns None on failure
    if result:
        results.append(result)
```

## Status

✅ **Implemented:**
- Chunked processing system
- Isolated LLM processing
- Enhanced error handling utilities
- Enhanced logging with file output
- Gmail extractor integration
- LLM extractor integration

🔄 **Ready for Integration:**
- iMessage extractor
- Google Takeout extractors
- All other extractors

## Testing

Test the system:

```python
# Test chunked processing
from utils.chunked_processor import ChunkedProcessor

def process_item(item):
    return f"processed_{item}"

processor = ChunkedProcessor(chunk_size=10)
results = processor.process_chunked(
    items=range(100),
    process_func=process_item,
    total_items=100
)
```

## Troubleshooting

**Q: Checkpoint not resuming?**
- Check checkpoint file exists and is valid JSON
- Verify item IDs match between runs
- Check file permissions

**Q: Results not saving?**
- Check disk space
- Verify write permissions
- Check result_file path

**Q: LLM still crashing?**
- Verify `IsolatedLLMProcessor` is used
- Check `continue_on_error=True`
- Verify max_retries > 0

