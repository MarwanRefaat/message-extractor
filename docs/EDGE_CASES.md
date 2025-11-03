# Edge Cases & Robustness System

This document outlines the comprehensive system for handling edge cases and ensuring robustness across the entire message extractor project.

## System Overview

We've implemented a multi-layered error handling system that addresses:

1. **Import Errors** - Module availability checking
2. **File I/O Errors** - Safe file operations with cleanup
3. **Subprocess Errors** - Retry logic and timeout handling
4. **Database Errors** - Connection management and query safety
5. **Data Parsing Errors** - Validation and fallback mechanisms
6. **Network/API Errors** - Exponential backoff retries
7. **Resource Management** - Automatic cleanup and context managers
8. **Interruption Handling** - Graceful shutdown and checkpointing
9. **Memory Management** - Batch processing and limits
10. **Concurrency Issues** - Safe resource access

## Key Components

### 1. Error Handling Utilities (`src/utils/error_handling.py`)

Provides reusable utilities for common operations:

- **Safe File Operations**: `safe_file_open()`, `safe_file_read()`, `safe_file_write()`
- **Safe Database Operations**: `safe_db_connection()`, `safe_db_query()`
- **Safe Subprocess Execution**: `safe_subprocess_run()` with retries
- **Retry Logic**: `retry_with_backoff()` decorator
- **Path Validation**: `validate_path()` with comprehensive checks
- **Data Validation**: `validate_date_string()`, `safe_json_parse()`
- **Progress Tracking**: `ProgressTracker` with checkpoint support
- **Resource Management**: `ResourceManager` context manager

### 2. Enhanced Exception Hierarchy (`src/exceptions.py`)

Extended custom exceptions:

- `MessageExtractorError` - Base exception
- `ExtractionError` - Extraction failures
- `AuthenticationError` - Auth issues
- `DatabaseError` - Database problems
- `DataFormatError` - Data parsing issues
- `RetryableError` - Errors that can be retried
- `ResourceError` - Resource access issues
- `ValidationError` - Input validation failures

### 3. Documentation

- `ERROR_HANDLING_GUIDE.md` - Usage guide with examples
- `ROBUSTNESS_CHECKLIST.md` - Checklist for developers
- `EDGE_CASES.md` - This document

## Specific Edge Cases Handled

### Import Errors

**Problem**: Incorrect module imports cause AttributeError
**Example**: `email.message.message_from_bytes` doesn't exist
**Solution**: 
- Use explicit imports: `from email import message_from_bytes`
- Test imports before use
- Handle ImportError gracefully with optional dependencies

```python
try:
    from email import message_from_bytes
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
```

### File Not Found

**Problem**: Missing files cause crashes
**Solution**: Validate paths early, use safe_file_read with defaults

```python
path = validate_path(input_path, must_exist=True)
content = safe_file_read(file_path, default="{}")
```

### Permission Errors

**Problem**: Insufficient permissions for file/directory access
**Solution**: Catch PermissionError, provide clear error messages

```python
try:
    with safe_file_open(path, 'w') as f:
        f.write(data)
except PermissionError:
    raise ExtractionError(f"Permission denied: {path}")
```

### Subprocess Timeouts

**Problem**: Long-running commands hang indefinitely
**Solution**: Use safe_subprocess_run with timeouts

```python
result = safe_subprocess_run(
    ["long-running-command"],
    timeout=3600,  # 1 hour
    retries=2
)
```

### Database Locks

**Problem**: Multiple processes accessing same database
**Solution**: Use safe_db_connection with timeout, proper transaction handling

```python
with safe_db_connection(db_path, timeout=30) as conn:
    # Automatic commit/rollback
    results = safe_db_query(conn, query, params)
```

### Data Parsing Failures

**Problem**: Invalid JSON, malformed dates cause crashes
**Solution**: Use safe parsers with fallbacks

```python
data = safe_json_parse(json_str, default={})
date = validate_date_string(date_str) or datetime.now()
```

### Network Timeouts

**Problem**: API calls timeout, network issues
**Solution**: Retry with exponential backoff

```python
@retry_with_backoff(
    max_attempts=3,
    exceptions=(ConnectionError, TimeoutError)
)
def api_call():
    return fetch_from_api()
```

### Memory Issues

**Problem**: Large files cause out-of-memory errors
**Solution**: Process in batches, use generators, set limits

```python
for i in range(0, len(items), BATCH_SIZE):
    batch = items[i:i+BATCH_SIZE]
    process_batch(batch)
```

### Interruptions

**Problem**: Ctrl+C loses progress
**Solution**: Save checkpoints, handle KeyboardInterrupt gracefully

```python
try:
    for item in items:
        process_item(item)
        tracker.mark_processed(item.id)
        if count % 100 == 0:
            tracker.save_checkpoint()
except KeyboardInterrupt:
    tracker.save_checkpoint()
    logger.info("Progress saved")
    raise
```

### Resource Leaks

**Problem**: Open file handles, DB connections not closed
**Solution**: Use context managers everywhere

```python
with safe_file_open(path) as f:
    # Auto-closed on exit
    data = f.read()
```

### Concurrent Access

**Problem**: Multiple processes writing to same file
**Solution**: Use atomic operations, file locks (future enhancement)

## Integration Strategy

### Phase 1: Critical Paths (Done)
- ✅ Gmail extractor email parsing fix
- ✅ Error handling utilities created
- ✅ Exception hierarchy extended

### Phase 2: High-Impact Updates (Next)
1. Update Gmail extractor to use new utilities
2. Update iMessage extractor for database safety
3. Update all Google Takeout extractors for file safety

### Phase 3: Comprehensive Coverage
1. Add retry logic to all network/API calls
2. Add progress tracking to all long-running operations
3. Add checkpoint support for all extractors
4. Add comprehensive validation

### Phase 4: Testing & Monitoring
1. Test all edge cases
2. Add performance monitoring
3. Add error rate tracking
4. Create health checks

## Quick Reference

### For New Extractors

```python
from utils.error_handling import (
    validate_path,
    safe_file_open,
    safe_subprocess_run,
    retry_with_backoff,
    handle_extraction_error,
    ProgressTracker
)

class MyExtractor:
    def __init__(self, path):
        # Validate early
        self.path = validate_path(path, must_exist=True)
    
    @retry_with_backoff(max_attempts=3)
    def _call_external_tool(self):
        return safe_subprocess_run([...], timeout=300)
    
    @handle_extraction_error(continue_on_error=True)
    def _process_item(self, item):
        with safe_file_open(item.path) as f:
            return self.parse(f.read())
```

### Error Handling Patterns

**Always validate inputs:**
```python
path = validate_path(input_path, must_exist=True, must_be_file=True)
```

**Always use context managers:**
```python
with safe_file_open(path) as f:
    data = f.read()
```

**Always handle interruptions:**
```python
try:
    process_all()
except KeyboardInterrupt:
    save_checkpoint()
    raise
```

**Always provide defaults:**
```python
data = safe_json_parse(json_str, default={})
date = validate_date_string(date_str) or datetime.now()
```

## Benefits

1. **Robustness**: System continues working even when individual items fail
2. **Recoverability**: Can resume from checkpoints after interruptions
3. **Debugging**: Better error messages with context
4. **Performance**: Retry logic handles transient failures
5. **Reliability**: Resource cleanup prevents leaks
6. **User Experience**: Graceful error messages, progress tracking

## Future Enhancements

- File locking for concurrent access
- Distributed progress tracking (for multi-machine processing)
- Automatic error recovery suggestions
- Health check endpoints
- Metrics collection and monitoring
- Circuit breaker pattern for failing services

