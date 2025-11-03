"""
Logging utilities for the message extractor
"""
import logging
import sys


def get_logger(name: str, level: int = logging.INFO, use_colors: bool = True) -> logging.Logger:
    """
    Create and configure a logger with nice formatting
    
    Args:
        name: Logger name
        level: Logging level
        use_colors: Whether to use colored output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Create formatter with colors
    if use_colors:
        class ColoredFormatter(logging.Formatter):
            """Custom formatter with colors"""
            COLORS = {
                'DEBUG': '\033[36m',      # Cyan
                'INFO': '\033[32m',       # Green
                'WARNING': '\033[33m',    # Yellow
                'ERROR': '\033[31m',      # Red
                'CRITICAL': '\033[35m',   # Magenta
                'RESET': '\033[0m'
            }
            
            def format(self, record):
                log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
                record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
                return super().format(record)
        
        formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

