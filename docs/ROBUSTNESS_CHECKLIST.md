# Robustness Checklist

Use this checklist to ensure extractors and utilities are robust against edge cases.

## Pre-Execution Validation

- [ ] **Path Validation**: All file/directory paths validated before use
  ```python
  path = validate_path(input_path, must_exist=True, must_be_file=True)
  ```

- [ ] **Import Checks**: Optional dependencies checked before use
  ```python
  try:
      import optional_module
      MODULE_AVAILABLE = True
  except ImportError:
      MODULE_AVAILABLE = False
  ```

- [ ] **Resource Availability**: Check disk space, permissions, network connectivity
- [ ] **Configuration Validation**: Verify required config files exist and are valid

## File Operations

- [ ] **Use Context Managers**: All file operations use `safe_file_open()` or context managers
- [ ] **Error Handling**: Catch `FileNotFoundError`, `PermissionError`, `OSError`
- [ ] **Backup Strategy**: Critical writes use backup option
- [ ] **Directory Creation**: Parent directories created automatically when needed
- [ ] **Encoding Handling**: Specify encoding explicitly, handle encoding errors gracefully

## Database Operations

- [ ] **Connection Management**: Use `safe_db_connection()` context manager
- [ ] **Transaction Handling**: Proper commit/rollback on errors
- [ ] **Query Validation**: Validate SQL queries, handle malformed queries
- [ ] **Timeout Handling**: Set appropriate timeouts for database operations
- [ ] **Connection Pooling**: For high-volume operations

## Subprocess Operations

- [ ] **Timeout Protection**: All subprocess calls have timeouts
- [ ] **Retry Logic**: Use `safe_subprocess_run()` with retries
- [ ] **Error Checking**: Check return codes, handle stderr
- [ ] **Path Validation**: Verify executable exists before calling
- [ ] **Permission Checks**: Handle permission errors gracefully

## Data Processing

- [ ] **Input Validation**: Validate data format before processing
- [ ] **Batch Processing**: Process large datasets in batches
- [ ] **Memory Management**: Use generators for large files, avoid loading all into memory
- [ ] **Progress Tracking**: Track progress with checkpoints for long operations
- [ ] **Incremental Processing**: Support resume from checkpoints

## Error Recovery

- [ ] **Retry Logic**: Retry transient failures (network, timeouts)
- [ ] **Graceful Degradation**: Continue processing other items when one fails
- [ ] **Error Logging**: Log errors at appropriate levels with context
- [ ] **User Feedback**: Provide clear error messages and recovery suggestions
- [ ] **Partial Results**: Return partial results when possible

## Resource Cleanup

- [ ] **Context Managers**: Use for all resources (files, DB, network)
- [ ] **ResourceManager**: Use for managing multiple resources
- [ ] **Exception Safety**: Cleanup happens even on exceptions
- [ ] **Memory Leaks**: Check for unclosed resources, memory leaks

## Interruption Handling

- [ ] **KeyboardInterrupt**: Handle gracefully, save state
- [ ] **Checkpoints**: Save progress periodically
- [ ] **Resume Support**: Can resume from last checkpoint
- [ ] **State Persistence**: Save processing state before exit

## Concurrency Safety

- [ ] **File Locks**: Prevent concurrent access to shared files
- [ ] **Atomic Operations**: Use atomic file operations when needed
- [ ] **Thread Safety**: If using threads, ensure thread-safe operations
- [ ] **Race Conditions**: Check for and prevent race conditions

## Data Validation

- [ ] **Date Parsing**: Use `validate_date_string()` with multiple formats
- [ ] **JSON Parsing**: Use `safe_json_parse()` with defaults
- [ ] **Type Checking**: Validate data types before use
- [ ] **Range Checking**: Validate numeric ranges, string lengths
- [ ] **Format Validation**: Validate expected formats (emails, URLs, etc.)

## Logging & Monitoring

- [ ] **Progress Logging**: Log progress every N items or time intervals
- [ ] **Error Context**: Include context in error messages (file name, line number, etc.)
- [ ] **Statistics**: Track processed/skipped/failed counts
- [ ] **Performance Metrics**: Log processing time, throughput
- [ ] **Debug Mode**: Support verbose logging for troubleshooting

## Testing

- [ ] **Missing Files**: Test with missing input files
- [ ] **Invalid Data**: Test with malformed/corrupted data
- [ ] **Permission Errors**: Test with read-only directories
- [ ] **Timeouts**: Test timeout handling
- [ ] **Interruptions**: Test KeyboardInterrupt handling
- [ ] **Large Files**: Test with very large files
- [ ] **Network Issues**: Test network failure scenarios
- [ ] **Concurrent Access**: Test multiple processes accessing same resource

## Documentation

- [ ] **Error Handling**: Document expected errors and recovery
- [ ] **Dependencies**: Document required/optional dependencies
- [ ] **Limitations**: Document known limitations and edge cases
- [ ] **Usage Examples**: Provide examples with error handling

