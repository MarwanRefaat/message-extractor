"""
Chunked processing system with incremental saving and resume capability
Processes items in batches and saves progress incrementally to prevent data loss
"""
import json
import time
from pathlib import Path
from typing import List, Iterator, Callable, Optional, Any, Dict, TypeVar
from dataclasses import dataclass, asdict
from datetime import datetime
import threading

from exceptions import ExtractionError
from utils.logger import get_logger
from utils.error_handling import safe_file_write, safe_json_parse, safe_file_read

logger = get_logger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class ChunkProgress:
    """Progress tracking for chunked processing"""
    total_items: int = 0
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    current_chunk: int = 0
    total_chunks: int = 0
    processed_ids: List[str] = None
    failed_ids: List[str] = None
    last_save_time: Optional[str] = None
    start_time: Optional[str] = None
    
    def __post_init__(self):
        if self.processed_ids is None:
            self.processed_ids = []
        if self.failed_ids is None:
            self.failed_ids = []


class ChunkedProcessor:
    """
    Process items in chunks with automatic saving and resume capability
    
    Features:
    - Processes items in configurable batch sizes
    - Saves progress after each chunk
    - Can resume from last saved position
    - Isolated error handling per item
    - Saves results incrementally
    """
    
    def __init__(
        self,
        chunk_size: int = 100,
        checkpoint_dir: Optional[Path] = None,
        result_file: Optional[Path] = None,
        get_item_id: Optional[Callable[[T], str]] = None,
        save_interval: int = 10,  # Save every N items
        isolated_errors: bool = True  # Continue on individual item failures
    ):
        """
        Initialize chunked processor
        
        Args:
            chunk_size: Number of items to process before saving
            checkpoint_dir: Directory for checkpoint files
            result_file: File to save results incrementally
            get_item_id: Function to extract unique ID from item
            save_interval: Save results every N items (in addition to chunks)
            isolated_errors: If True, item failures don't stop processing
        """
        self.chunk_size = chunk_size
        self.save_interval = save_interval
        self.isolated_errors = isolated_errors
        
        # Setup paths
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.checkpoint_dir = Path("checkpoints")
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoint_file = self.checkpoint_dir / "progress.json"
        self.result_file = Path(result_file) if result_file else None
        
        # Item ID extraction
        if get_item_id:
            self.get_item_id = get_item_id
        else:
            self.get_item_id = lambda x: str(hash(x))
        
        # Progress tracking
        self.progress = ChunkProgress()
        self.results: List[Any] = []
        self.lock = threading.Lock()  # For thread-safe saves
        
        # Load existing progress
        self.load_checkpoint()
    
    def load_checkpoint(self):
        """Load progress from checkpoint file"""
        if not self.checkpoint_file.exists():
            logger.info("No checkpoint found, starting fresh")
            return
        
        try:
            data = safe_json_parse(safe_file_read(self.checkpoint_file), {})
            if data:
                self.progress = ChunkProgress(**data)
                logger.info(
                    f"Loaded checkpoint: {self.progress.processed_items}/{self.progress.total_items} items "
                    f"({self.progress.successful_items} successful, {self.progress.failed_items} failed)"
                )
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
    
    def save_checkpoint(self, force: bool = False):
        """Save progress to checkpoint file"""
        try:
            self.progress.last_save_time = datetime.now().isoformat()
            data = asdict(self.progress)
            
            with self.lock:
                safe_file_write(
                    self.checkpoint_file,
                    json.dumps(data, indent=2),
                    create_dirs=True
                )
            
            if not force:  # Don't log on every save
                logger.debug(f"Checkpoint saved: {self.progress.processed_items} items")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def save_results(self, results_batch: List[Any], append: bool = True):
        """Save results incrementally"""
        if not self.result_file:
            return
        
        try:
            mode = 'a' if append and self.result_file.exists() else 'w'
            
            with self.lock:
                with open(self.result_file, mode, encoding='utf-8') as f:
                    for result in results_batch:
                        f.write(json.dumps(result, default=str) + '\n')
            
            logger.debug(f"Saved {len(results_batch)} results to {self.result_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def process_chunked(
        self,
        items: Iterator[T],
        process_func: Callable[[T], R],
        total_items: Optional[int] = None,
        resume: bool = True
    ) -> List[R]:
        """
        Process items in chunks with automatic saving
        
        Args:
            items: Iterator over items to process
            process_func: Function to process each item (item) -> result
            total_items: Total number of items (for progress display)
            resume: Whether to skip already processed items
        
        Returns:
            List of successful results
        """
        # Initialize progress
        if not self.progress.start_time:
            self.progress.start_time = datetime.now().isoformat()
        
        if total_items:
            self.progress.total_items = total_items
        
        # Convert to list for resumable processing (if needed)
        items_list = list(items) if resume else items
        processed_set = set(self.progress.processed_ids) if resume else set()
        
        if total_items:
            self.progress.total_chunks = (total_items + self.chunk_size - 1) // self.chunk_size
        
        chunk_results: List[R] = []
        current_chunk: List[R] = []
        item_count = 0
        
        logger.info(
            f"Starting chunked processing: "
            f"chunk_size={self.chunk_size}, "
            f"total_items={total_items or 'unknown'}, "
            f"resume={resume}"
        )
        
        try:
            for i, item in enumerate(items_list):
                # Skip if already processed (resume mode)
                item_id = self.get_item_id(item)
                if resume and item_id in processed_set:
                    self.progress.skipped_items += 1
                    continue
                
                # Process item with isolation
                try:
                    result = process_func(item)
                    
                    if result is not None:
                        current_chunk.append(result)
                        chunk_results.append(result)
                        self.progress.successful_items += 1
                        self.progress.processed_ids.append(item_id)
                        
                        # Save incrementally
                        if len(current_chunk) >= self.save_interval:
                            self.save_results([current_chunk[-self.save_interval:]])
                            current_chunk = []
                    else:
                        self.progress.skipped_items += 1
                    
                    self.progress.processed_items += 1
                    item_count += 1
                    
                except KeyboardInterrupt:
                    logger.warning("Interrupted by user")
                    self.save_checkpoint(force=True)
                    self.save_results(current_chunk)
                    raise
                    
                except Exception as e:
                    self.progress.failed_items += 1
                    self.progress.failed_ids.append(item_id)
                    self.progress.processed_items += 1
                    
                    if self.isolated_errors:
                        logger.warning(
                            f"Item {item_id} failed (continuing): {e}",
                            exc_info=False
                        )
                        continue
                    else:
                        logger.error(f"Item {item_id} failed: {e}")
                        self.save_checkpoint(force=True)
                        raise ExtractionError(f"Processing failed at item {item_id}: {e}") from e
                
                # Save checkpoint and results after chunk
                if item_count >= self.chunk_size:
                    self.progress.current_chunk += 1
                    logger.info(
                        f"Chunk {self.progress.current_chunk}/{self.progress.total_chunks or '?'} complete: "
                        f"{self.progress.processed_items} processed, "
                        f"{self.progress.successful_items} successful, "
                        f"{self.progress.failed_items} failed"
                    )
                    
                    self.save_checkpoint()
                    if current_chunk:
                        self.save_results(current_chunk)
                        current_chunk = []
                    
                    item_count = 0
            
            # Save final chunk
            if current_chunk:
                self.save_results(current_chunk)
            
            # Final checkpoint
            self.save_checkpoint(force=True)
            
            logger.info(
                f"Processing complete: "
                f"{self.progress.successful_items} successful, "
                f"{self.progress.failed_items} failed, "
                f"{self.progress.skipped_items} skipped"
            )
            
            return chunk_results
            
        except Exception as e:
            # Save state before re-raising
            self.save_checkpoint(force=True)
            if current_chunk:
                self.save_results(current_chunk)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'total_items': self.progress.total_items,
            'processed': self.progress.processed_items,
            'successful': self.progress.successful_items,
            'failed': self.progress.failed_items,
            'skipped': self.progress.skipped_items,
            'success_rate': (
                self.progress.successful_items / self.progress.processed_items 
                if self.progress.processed_items > 0 else 0
            ),
            'current_chunk': self.progress.current_chunk,
            'total_chunks': self.progress.total_chunks,
            'last_save': self.progress.last_save_time,
        }


class IsolatedLLMProcessor:
    """
    Wrapper for LLM operations that isolates failures
    
    Ensures LLM errors don't crash the entire extraction process
    """
    
    def __init__(
        self,
        llm_func: Callable[[Any], Any],
        fallback_func: Optional[Callable[[Any], Any]] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        continue_on_error: bool = True
    ):
        """
        Initialize isolated LLM processor
        
        Args:
            llm_func: LLM processing function
            fallback_func: Fallback function if LLM fails
            max_retries: Maximum retry attempts
            timeout: Timeout per LLM call (not yet implemented)
            continue_on_error: If True, return None on failure instead of raising
        """
        self.llm_func = llm_func
        self.fallback_func = fallback_func
        self.max_retries = max_retries
        self.timeout = timeout
        self.continue_on_error = continue_on_error
        self.logger = get_logger(f"{__name__}.IsolatedLLMProcessor")
    
    def __call__(self, item: Any) -> Optional[Any]:
        """
        Process item with LLM, isolated from failures
        
        Returns:
            Result or None if all attempts fail (or raises if continue_on_error=False)
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Try LLM processing
                result = self.llm_func(item)
                if result:
                    return result
                    
            except KeyboardInterrupt:
                raise  # Don't catch interrupts
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    self.logger.debug(
                        f"LLM processing failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying: {e}"
                    )
                    time.sleep(1)  # Brief pause before retry
                    continue
                else:
                    self.logger.warning(
                        f"LLM processing failed after {self.max_retries + 1} attempts: {e}"
                    )
        
        # Try fallback if available
        if self.fallback_func:
            try:
                self.logger.debug("Attempting fallback processing")
                return self.fallback_func(item)
            except Exception as e:
                self.logger.warning(f"Fallback also failed: {e}")
        
        # Handle final failure
        if self.continue_on_error:
            # Return None if all attempts fail (don't crash)
            self.logger.debug(f"LLM processing failed for item, continuing: {last_error}")
            return None
        else:
            # Re-raise the error
            raise last_error or Exception("LLM processing failed")


def create_chunked_processor(
    chunk_size: int = 100,
    checkpoint_dir: Optional[str] = None,
    result_file: Optional[str] = None
) -> ChunkedProcessor:
    """Factory function to create chunked processor"""
    return ChunkedProcessor(
        chunk_size=chunk_size,
        checkpoint_dir=Path(checkpoint_dir) if checkpoint_dir else None,
        result_file=Path(result_file) if result_file else None
    )

