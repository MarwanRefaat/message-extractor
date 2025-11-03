# Error Handling & Robustness Guide

This guide documents the comprehensive error handling system designed to make the message extractor robust against common edge cases and failures.

## Common Failure Patterns

### 1. **Import Errors**
**Problem:** Incorrect module imports (like `email.message.message_from_bytes`)
**Solution:** Always test imports, use explicit imports from correct module level

### 2. **File I/O Errors**
**Problem:** Missing files, permission errors, disk full, corrupted files
**Solution:** Use `safe_file_open()`, validate paths, handle exceptions gracefully

### 3. **Subprocess Errors**
**Problem:** Timeouts, command not found, permission denied, process crashes
**Solution:** Use `safe_subprocess_run()` with retry logic and timeout handling

### 4. **Database Errors**
**Problem:** Locked databases, connection timeouts, query errors, corruption
**Solution:** Use `safe_db_connection()` context manager with proper cleanup

### 5. **Data Parsing Errors**
**Problem:** Invalid JSON, malformed dates, encoding issues, unexpected formats
**Solution:** Use `safe_json_parse()`, `validate_date_string()` with fallbacks

### 6. **Network/API Errors**
**Problem:** Timeouts, rate limits, authentication failures, connection issues
**Solution:** Use retry decorators with exponential backoff

### 7. **Resource Cleanup**
**Problem:** Open file handles, database connections, memory leaks
**Solution:** Use context managers, ResourceManager for multiple resources

### 8. **Memory Issues**
**Problem:** Large files causing OOM, unbounded processing
**Solution:** Process in batches, use generators, set max_results limits

### 9. **Interruption Handling**
**Problem:** User Ctrl+C causes data loss, incomplete processing
**Solution:** Checkpoint progress, handle KeyboardInterrupt gracefully

### 10. **Concurrent Access**
**Problem:** Multiple processes accessing same resource, race conditions
**Solution:** Use file locks, atomic operations, proper synchronization

## Error Handling Utilities

### Import Validation

```python
from utils.error_handling import safe_import

# Test imports before using
try:
    from email import message_from_bytes
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    logger.warning("email module not available")
```

### File Operations

```python
from utils.error_handling import safe_file_open, safe_file_read, safe_file_write

# Reading with error handling
content = safe_file_read("data.json", default="{}")

# Writing with backup and directory creation
safe_file_write("output.json", data, create_dirs=True, backup=True)

# Context manager for complex operations
with safe_file_open("large_file.txt", "r") as f:
    # Process file
    pass
```

### Subprocess Operations

```python
from utils.error_handling import safe_subprocess_run

# Run command with automatic retry
result = safe_subprocess_run(
    ["gmail-exporter", "labels"],
    timeout=60,
    retries=2
)

if result and result.returncode == 0:
    print(result.stdout)
```

### Database Operations

```python
from utils.error_handling import safe_db_connection, safe_db_query

# Automatic connection management
with safe_db_connection("chat.db") as conn:
    results = safe_db_query(
        conn,
        "SELECT * FROM messages WHERE date > ?",
        params=(timestamp,)
    )
```

### Retry Logic

```python
from utils.error_handling import retry_with_backoff

@retry_with_backoff(
    max_attempts=3,
    initial_delay=1.0,
    exceptions=(ConnectionError, TimeoutError)
)
def fetch_data():
    # Network call that might fail
    return api_call()
```

### Progress Tracking

```python
from utils.error_handling import ProgressTracker

tracker = ProgressTracker(checkpoint_file="progress.json")

for item_id, data in items:
    if tracker.is_processed(item_id):
        continue
    
    try:
        process_item(data)
        tracker.mark_processed(item_id)
        tracker.save_checkpoint()  # Save periodically
    except Exception as e:
        logger.error(f"Failed {item_id}: {e}")
        continue
```

### Error Recovery Decorators

```python
from utils.error_handling import handle_extraction_error

@handle_extraction_error(
    item_identifier=lambda self, eml_path: eml_path.name,
    continue_on_error=True
)
def parse_email(self, eml_path):
    # Process email
    return message
```

### Resource Management

```python
from utils.error_handling import ResourceManager

with ResourceManager() as resources:
    file1 = resources.add(open("file1.txt"))
    file2 = resources.add(open("file2.txt"))
    db = resources.add(sqlite3.connect("db.sqlite"))
    # All resources automatically closed on exit
```

## Best Practices

### 1. Always Use Context Managers

```python
# ❌ Bad
f = open("file.txt")
data = f.read()
f.close()  # Might be skipped on exception

# ✅ Good
with safe_file_open("file.txt") as f:
    data = f.read()
```

### 2. Validate Inputs Early

```python
# ✅ Good
def extract_from_path(path: str):
    validated_path = validate_path(path, must_exist=True, must_be_file=True)
    # Continue with validated path
```

### 3. Provide Defaults for Optional Operations

```python
# ✅ Good
data = safe_json_parse(json_str, default={})
date = validate_date_string(date_str, formats=[...]) or datetime.now()
```

### 4. Log Errors Appropriately

```python
# ✅ Good
try:
    process_item(item)
except SpecificError as e:
    logger.warning(f"Known issue with {item}: {e}")
    continue  # Recover gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise  # Re-raise unexpected errors
```

### 5. Handle Interruptions Gracefully

```python
# ✅ Good
try:
    for item in items:
        process_item(item)
except KeyboardInterrupt:
    logger.info(f"Interrupted. Processed {count} items.")
    save_checkpoint()
    raise  # Re-raise to allow cleanup
```

### 6. Use Retries for Transient Failures

```python
# ✅ Good
@retry_with_backoff(
    max_attempts=3,
    exceptions=(ConnectionError, TimeoutError)
)
def network_call():
    # This will retry on connection/timeout errors
    return api.fetch_data()
```

### 7. Batch Processing for Large Datasets

```python
# ✅ Good
BATCH_SIZE = 100
for i in range(0, len(items), BATCH_SIZE):
    batch = items[i:i+BATCH_SIZE]
    try:
        process_batch(batch)
    except Exception as e:
        logger.error(f"Batch {i} failed: {e}")
        continue  # Continue with next batch
```

## Integration Examples

### Updated Gmail Extractor Pattern

```python
from utils.error_handling import (
    safe_subprocess_run,
    safe_file_open,
    validate_path,
    handle_extraction_error,
    ProgressTracker
)

class GmailExtractor:
    def __init__(self, ...):
        # Validate paths early
        self.gmail_exporter_path = validate_path(
            gmail_exporter_path,
            must_exist=True,
            must_be_file=True
        )
    
    @retry_with_backoff(max_attempts=2, exceptions=(subprocess.TimeoutExpired,))
    def _run_gmail_exporter(self):
        result = safe_subprocess_run(
            [self.gmail_exporter_path, "export", ...],
            timeout=3600
        )
        return result.returncode == 0
    
    @handle_extraction_error(continue_on_error=True)
    def _parse_eml_file(self, eml_path):
        with safe_file_open(eml_path, 'rb') as f:
            msg = message_from_bytes(f.read())
        return self._convert_to_message(msg)
```

## Testing Error Handling

```python
# Test file not found
with pytest.raises(FileNotFoundError):
    validate_path("/nonexistent", must_exist=True)

# Test retry logic
@retry_with_backoff(max_attempts=3)
def flaky_function():
    if attempts < 3:
        raise ConnectionError()
    return "success"

# Test resource cleanup
with ResourceManager() as rm:
    f = rm.add(open("test.txt"))
# File automatically closed
```

## Monitoring & Logging

All error handling utilities integrate with the logging system:

- **INFO**: Normal operations, progress updates
- **WARNING**: Recoverable errors, retries
- **ERROR**: Critical failures, missing resources
- **DEBUG**: Detailed execution traces

## Checklist for New Extractors

- [ ] Validate all input paths with `validate_path()`
- [ ] Use `safe_file_open()` for all file operations
- [ ] Use `safe_db_connection()` for database access
- [ ] Use `safe_subprocess_run()` for external commands
- [ ] Add retry logic for network/API calls
- [ ] Handle `KeyboardInterrupt` gracefully
- [ ] Use context managers for resource cleanup
- [ ] Log errors at appropriate levels
- [ ] Provide default values for optional operations
- [ ] Test with missing files, invalid data, interruptions

