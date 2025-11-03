# Chunked Processing & Incremental Saving

This guide explains how to use the chunked processing system that saves progress incrementally and allows resuming from interruptions.

## Overview

The chunked processing system addresses key robustness issues:

1. **Incremental Saving**: Results saved in small chunks, not all at once
2. **Resume Capability**: Can pick up where it left off after interruptions
3. **Isolated Failures**: One item failure doesn't stop entire process
4. **Progress Tracking**: Detailed statistics and checkpointing
5. **Better Logging**: File logging with detailed progress

## Core Components

### ChunkedProcessor

Processes items in batches with automatic saving:

```python
from utils.chunked_processor import ChunkedProcessor

processor = ChunkedProcessor(
    chunk_size=100,              # Process 100 items per chunk
    checkpoint_dir="checkpoints", # Where to save progress
    result_file="results.jsonl",  # Where to save results incrementally
    get_item_id=lambda x: str(x), # Function to get unique ID
    save_interval=10,             # Save results every 10 items
    isolated_errors=True         # Continue on individual failures
)

# Process items
results = processor.process_chunked(
    items=my_items,
    process_func=process_single_item,
    total_items=len(my_items),
    resume=True  # Skip already processed items
)
```

### IsolatedLLMProcessor

Wraps LLM calls to prevent crashes:

```python
from utils.chunked_processor import IsolatedLLMProcessor

isolated_llm = IsolatedLLMProcessor(
    llm_func=my_llm_function,
    fallback_func=regex_fallback,  # Optional fallback
    max_retries=2,
    continue_on_error=True  # Return None instead of crashing
)

# Use it - failures are isolated
result = isolated_llm(item)  # Returns None on failure, doesn't crash
```

## Usage Examples

### Gmail Extractor with Chunked Processing

The Gmail extractor now uses chunked processing by default:

```python
from extractors.gmail_extractor import GmailExtractor

extractor = GmailExtractor()
ledger = extractor.extract_all(
    max_results=1000,
    use_chunked=True,      # Enable chunked processing
    chunk_size=50          # Process 50 emails per chunk
)

# Progress is saved to:
# - gmail_export/checkpoints/progress.json (checkpoint)
# - gmail_export/results.jsonl (incremental results)
```

**Benefits:**
- If interrupted, can resume from last checkpoint
- Results saved incrementally (every 10 items + after each chunk)
- Individual email failures don't stop processing

### Custom Chunked Processing

```python
from utils.chunked_processor import ChunkedProcessor
from pathlib import Path

def process_email_file(eml_path: Path):
    """Process a single EML file"""
    # Your processing logic
    return message_object

# Create processor
processor = ChunkedProcessor(
    chunk_size=50,
    checkpoint_dir="checkpoints",
    result_file="results.jsonl",
    get_item_id=lambda p: str(p)  # Use file path as ID
)

# Get list of files to process
eml_files = list(Path("emails").rglob("*.eml"))

# Process with resume capability
results = processor.process_chunked(
    items=eml_files,
    process_func=process_email_file,
    total_items=len(eml_files),
    resume=True  # Will skip already processed files
)

# Get statistics
stats = processor.get_stats()
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Processed: {stats['successful']}/{stats['total_items']}")
```

### LLM Processing with Isolation

```python
from utils.chunked_processor import IsolatedLLMProcessor

# Wrap your LLM function
isolated_llm = IsolatedLLMProcessor(
    llm_func=lambda data: my_llm.generate(data),
    fallback_func=lambda data: regex_extract(data),  # Fallback
    max_retries=2,
    continue_on_error=True
)

# Process items - failures won't crash
for item in items:
    result = isolated_llm(item)
    if result:
        # Only process successful results
        process_result(result)
    # Failed items are skipped automatically
```

## File Structure

When using chunked processing, you'll see:

```
gmail_export/
├── messages/           # EML files from gmail-exporter
├── messages.xlsx      # Spreadsheet summary
├── checkpoints/
│   └── progress.json  # Processing progress (auto-saved)
└── results.jsonl      # Incremental results (JSONL format)
```

**progress.json** contains:
```json
{
  "total_items": 1000,
  "processed_items": 450,
  "successful_items": 420,
  "failed_items": 10,
  "skipped_items": 20,
  "processed_ids": ["file1.eml", "file2.eml", ...],
  "failed_ids": ["bad_file.eml"],
  "last_save_time": "2025-11-02T21:30:00"
}
```

**results.jsonl** contains:
```
{"message_id": "gmail:1", "platform": "gmail", ...}
{"message_id": "gmail:2", "platform": "gmail", ...}
...
```

## Resuming Interrupted Processing

If processing is interrupted (Ctrl+C, crash, etc.):

1. **Progress is saved** to checkpoint file
2. **Results are saved** incrementally to results.jsonl
3. **On resume**, already processed items are skipped
4. **Only unprocessed items** are handled

```python
# First run (interrupted at item 450)
processor.process_chunked(items, process_func, resume=True)

# Second run (resumes from item 451)
processor.process_chunked(items, process_func, resume=True)
# Will skip first 450 items automatically
```

## Enhanced Logging

Enable file logging for detailed tracking:

```python
from utils.logger import get_logger

# Logger with file output
logger = get_logger(
    'gmail_extraction',
    log_dir='logs',        # Creates logs/ directory
    log_file='gmail.log'  # Optional specific filename
)

# Logs go to:
# - Console (colored, INFO level)
# - File (detailed, DEBUG level)
```

## Configuration

### Chunk Size

**Small chunks (10-50):**
- ✅ More frequent saves
- ✅ Less data loss on interruption
- ✅ Better progress visibility
- ❌ More I/O overhead

**Large chunks (100-500):**
- ✅ Less I/O overhead
- ✅ Faster processing
- ❌ Less frequent saves
- ❌ More data loss on interruption

**Recommended:** 50-100 for email processing

### Save Interval

How often to save results within a chunk:

- **Small (5-10)**: Very frequent saves, more safety
- **Medium (10-20)**: Balanced
- **Large (50+)**: Less I/O, but more risk

**Recommended:** 10 items

## Error Isolation

The system ensures:

1. **Item-level isolation**: One item failure doesn't affect others
2. **Chunk-level isolation**: One chunk failure doesn't stop processing
3. **LLM isolation**: LLM failures are caught and logged, not propagated
4. **Graceful degradation**: Continue processing even with some failures

## Statistics

Get detailed statistics:

```python
stats = processor.get_stats()

print(f"Total items: {stats['total_items']}")
print(f"Successful: {stats['successful']}")
print(f"Failed: {stats['failed']}")
print(f"Skipped: {stats['skipped']}")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Current chunk: {stats['current_chunk']}/{stats['total_chunks']}")
```

## Best Practices

1. **Always use chunked processing** for large datasets
2. **Enable resume** for long-running operations
3. **Set appropriate chunk sizes** based on item processing time
4. **Monitor checkpoints** to track progress
5. **Use isolated LLM processing** for LLM calls
6. **Enable file logging** for debugging
7. **Check statistics** after processing

## Integration Status

✅ **Gmail Extractor**: Uses chunked processing by default
✅ **LLM Extractor**: Uses isolated LLM processing
🔄 **Other Extractors**: Can be updated to use chunked processing

## Troubleshooting

### Checkpoint not loading
- Check file permissions
- Verify JSON is valid
- Check checkpoint file exists

### Results not saving
- Check disk space
- Verify write permissions
- Check result_file path

### Processing too slow
- Increase chunk_size
- Increase save_interval
- Reduce logging verbosity

