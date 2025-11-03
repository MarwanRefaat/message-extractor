"""
Comprehensive error handling utilities for robust extraction
Handles common edge cases: retries, resource cleanup, validation, etc.
"""
import os
import sys
import time
import functools
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TypeVar, Any, Union, List
from contextlib import contextmanager
import sqlite3
import subprocess

from exceptions import MessageExtractorError, ExtractionError
from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


# ============================================================================
# Retry Logic
# ============================================================================

def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry a function with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function(retry_exception, attempt_number)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    if on_retry:
                        on_retry(e, attempt)
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            raise last_exception  # Should never reach here, but type checker
        return wrapper
    return decorator


# ============================================================================
# File I/O Utilities
# ============================================================================

@contextmanager
def safe_file_open(
    file_path: Union[str, Path],
    mode: str = 'r',
    encoding: Optional[str] = 'utf-8',
    errors: str = 'replace',
    create_dirs: bool = False,
    backup: bool = False
):
    """
    Safe file opening with automatic cleanup and error handling
    
    Args:
        file_path: Path to file
        mode: File mode ('r', 'w', 'rb', etc.)
        encoding: Text encoding (None for binary)
        errors: Error handling for encoding
        create_dirs: Create parent directories if they don't exist
        backup: Backup existing file before writing
    
    Yields:
        File handle
    """
    file_path = Path(file_path)
    backup_path = None
    file_handle = None
    
    try:
        # Create directories if needed
        if create_dirs and file_path.parent:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup existing file if writing
        if 'w' in mode or 'a' in mode:
            if backup and file_path.exists():
                backup_path = file_path.with_suffix(file_path.suffix + '.bak')
                file_path.rename(backup_path)
                logger.debug(f"Backed up {file_path} to {backup_path}")
        
        # Validate path for reading
        if 'r' in mode and not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Open file
        if encoding and 'b' not in mode:
            file_handle = open(file_path, mode, encoding=encoding, errors=errors)
        else:
            file_handle = open(file_path, mode)
        
        yield file_handle
        
    except PermissionError as e:
        raise ExtractionError(f"Permission denied accessing {file_path}: {e}") from e
    except OSError as e:
        raise ExtractionError(f"OS error accessing {file_path}: {e}") from e
    except Exception as e:
        # Restore backup on failure
        if backup_path and backup_path.exists() and file_path.exists():
            file_path.unlink()
            backup_path.rename(file_path)
            logger.debug(f"Restored backup {backup_path} due to error")
        raise
    finally:
        if file_handle:
            try:
                file_handle.close()
            except Exception:
                pass


def safe_file_read(
    file_path: Union[str, Path],
    encoding: Optional[str] = 'utf-8',
    errors: str = 'replace',
    default: Any = None
) -> Optional[str]:
    """
    Safely read a file with error handling
    
    Returns:
        File contents or default value on error
    """
    try:
        with safe_file_open(file_path, 'r', encoding=encoding, errors=errors) as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Failed to read {file_path}: {e}")
        return default


def safe_file_write(
    file_path: Union[str, Path],
    content: str,
    encoding: str = 'utf-8',
    errors: str = 'replace',
    create_dirs: bool = True,
    backup: bool = False
) -> bool:
    """
    Safely write to a file with error handling
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with safe_file_open(
            file_path, 'w', encoding=encoding, errors=errors,
            create_dirs=create_dirs, backup=backup
        ) as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write {file_path}: {e}")
        return False


# ============================================================================
# Database Utilities
# ============================================================================

@contextmanager
def safe_db_connection(db_path: Union[str, Path], timeout: float = 30.0):
    """
    Safe database connection with automatic cleanup
    
    Args:
        db_path: Path to database
        timeout: Connection timeout in seconds
    
    Yields:
        Database connection
    """
    conn = None
    try:
        db_path = Path(db_path)
        
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        conn = sqlite3.connect(str(db_path), timeout=timeout)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise ExtractionError(f"Database error: {e}") from e
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def safe_db_query(
    conn: sqlite3.Connection,
    query: str,
    params: Optional[tuple] = None,
    fetch_all: bool = True
) -> Optional[List]:
    """
    Safely execute a database query
    
    Returns:
        Query results or None on error
    """
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch_all:
            return cursor.fetchall()
        else:
            return cursor.fetchone()
    except sqlite3.Error as e:
        logger.warning(f"Database query failed: {e}")
        return None


# ============================================================================
# Subprocess Utilities
# ============================================================================

def safe_subprocess_run(
    cmd: List[str],
    cwd: Optional[Union[str, Path]] = None,
    timeout: Optional[float] = None,
    check: bool = False,
    capture_output: bool = True,
    retries: int = 2
) -> Optional[subprocess.CompletedProcess]:
    """
    Safely run a subprocess with retry logic
    
    Returns:
        CompletedProcess or None on error
    """
    @retry_with_backoff(
        max_attempts=retries + 1,
        exceptions=(subprocess.TimeoutExpired, subprocess.SubprocessError, OSError)
    )
    def _run():
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
            text=True
        )
    
    try:
        return _run()
    except subprocess.TimeoutExpired as e:
        logger.error(f"Subprocess {cmd[0]} timed out after {timeout}s")
        return None
    except FileNotFoundError as e:
        logger.error(f"Command not found: {cmd[0]}")
        return None
    except PermissionError as e:
        logger.error(f"Permission denied running: {cmd[0]}")
        return None
    except Exception as e:
        logger.error(f"Subprocess error: {e}")
        return None


# ============================================================================
# Data Validation
# ============================================================================

def validate_path(
    path: Union[str, Path],
    must_exist: bool = True,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    create_if_missing: bool = False
) -> Path:
    """
    Validate and normalize a file path
    
    Returns:
        Path object
        
    Raises:
        FileNotFoundError: If path doesn't exist and must_exist=True
        ValueError: If path type doesn't match requirements
    """
    path = Path(path).expanduser().resolve()
    
    if not path.exists():
        if must_exist:
            raise FileNotFoundError(f"Path does not exist: {path}")
        elif create_if_missing:
            if must_be_dir:
                path.mkdir(parents=True, exist_ok=True)
            elif must_be_file:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
    
    if must_be_file and path.exists() and not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
    
    if must_be_dir and path.exists() and not path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
    
    return path


def validate_date_string(date_str: str, formats: Optional[List[str]] = None):
    """
    Safely parse a date string
    
    Returns:
        datetime object or None if parsing fails
    """
    from datetime import datetime
    
    if not date_str:
        return None
    
    formats = formats or [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%d %H:%M:%S%z',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    # Try dateutil as fallback
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except (ImportError, ValueError):
        pass
    
    logger.warning(f"Could not parse date string: {date_str}")
    return None


def safe_json_parse(json_str: str, default: Any = None) -> Any:
    """
    Safely parse JSON with error handling
    
    Returns:
        Parsed JSON or default value on error
    """
    import json
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")
        return default
    except Exception as e:
        logger.warning(f"Unexpected error parsing JSON: {e}")
        return default


def safe_json_dump(obj: Any, default: Any = None) -> Optional[str]:
    """
    Safely serialize object to JSON
    
    Returns:
        JSON string or None on error
    """
    import json
    
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"JSON serialize error: {e}")
        return default


# ============================================================================
# Resource Management
# ============================================================================

class ResourceManager:
    """Context manager for managing multiple resources"""
    
    def __init__(self):
        self.resources: List[Any] = []
    
    def add(self, resource: Any, cleanup: Optional[Callable[[Any], None]] = None):
        """Add a resource to manage"""
        self.resources.append((resource, cleanup))
        return resource
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up resources in reverse order
        for resource, cleanup in reversed(self.resources):
            try:
                if cleanup:
                    cleanup(resource)
                elif hasattr(resource, 'close'):
                    resource.close()
            except Exception as e:
                logger.warning(f"Error cleaning up resource: {e}")
        return False


# ============================================================================
# Progress Tracking
# ============================================================================

class ProgressTracker:
    """Track progress with checkpoint support"""
    
    def __init__(self, checkpoint_file: Optional[Union[str, Path]] = None):
        self.checkpoint_file = Path(checkpoint_file) if checkpoint_file else None
        self.processed: set = set()
        self.load_checkpoint()
    
    def load_checkpoint(self):
        """Load progress from checkpoint file"""
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return
        
        try:
            data = safe_json_parse(safe_file_read(self.checkpoint_file), {})
            self.processed = set(data.get('processed', []))
            logger.info(f"Loaded checkpoint: {len(self.processed)} items processed")
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
    
    def save_checkpoint(self):
        """Save progress to checkpoint file"""
        if not self.checkpoint_file:
            return
        
        try:
            data = {'processed': list(self.processed)}
            safe_file_write(
                self.checkpoint_file,
                safe_json_dump(data),
                create_dirs=True
            )
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def is_processed(self, item_id: str) -> bool:
        """Check if item has been processed"""
        return item_id in self.processed
    
    def mark_processed(self, item_id: str):
        """Mark item as processed"""
        self.processed.add(item_id)
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        return {
            'processed': len(self.processed)
        }


# ============================================================================
# Error Recovery
# ============================================================================

def handle_extraction_error(
    func: Callable[..., T],
    item_identifier: Optional[str] = None,
    continue_on_error: bool = True,
    log_traceback: bool = False
) -> Callable[..., Optional[T]]:
    """
    Decorator to handle extraction errors gracefully
    
    Args:
        func: Function to wrap
        item_identifier: Identifier for the item being processed (for logging)
        continue_on_error: Continue processing other items if this one fails
        log_traceback: Whether to log full traceback
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Optional[T]:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            logger.warning("Interrupted by user")
            raise
        except MessageExtractorError:
            # Re-raise custom exceptions
            raise
        except Exception as e:
            identifier = item_identifier or str(args[0] if args else 'unknown')
            error_msg = f"Error processing {identifier}: {e}"
            
            if log_traceback:
                logger.error(error_msg, exc_info=True)
            else:
                logger.error(error_msg)
            
            if continue_on_error:
                return None
            else:
                raise ExtractionError(error_msg) from e
    
    return wrapper

