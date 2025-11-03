"""
Progress bar utilities for the message extractor
"""
import sys
from typing import Optional


class ProgressBar:
    """
    Simple progress bar for console output
    """
    def __init__(self, total: int, description: str = "", width: int = 50):
        """
        Initialize progress bar
        
        Args:
            total: Total number of items
            description: Description text
            width: Width of progress bar
        """
        self.total = total
        self.description = description
        self.width = width
        self.current = 0
    
    def update(self, increment: int = 1):
        """Update progress"""
        self.current = min(self.current + increment, self.total)
        self._display()
    
    def set_current(self, value: int):
        """Set current progress to specific value"""
        self.current = max(0, min(value, self.total))
        self._display()
    
    def _display(self):
        """Display progress bar"""
        if self.total == 0:
            percentage = 100
        else:
            percentage = int(100 * self.current / self.total)
        
        filled = int(self.width * self.current / self.total) if self.total > 0 else self.width
        bar = '█' * filled + '░' * (self.width - filled)
        
        # Build status line
        status = f"\r{self.description} [{bar}] {percentage}% ({self.current}/{self.total})"
        
        sys.stdout.write(status)
        sys.stdout.flush()
        
        if self.current >= self.total:
            print()  # New line when complete
    
    def close(self):
        """Close progress bar"""
        if self.current < self.total:
            self.set_current(self.total)
        print()

