"""
Logging utilities for the message extractor
Enhanced with file logging and better organization
"""
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def get_logger(
    name: str,
    level: int = logging.INFO,
    use_colors: bool = True,
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None
) -> logging.Logger:
    """
    Create and configure a logger with nice formatting and optional file logging
    
    Args:
        name: Logger name
        level: Logging level
        use_colors: Whether to use colored output (only for console)
        log_file: Optional log file path (if None, uses name.log)
        log_dir: Optional log directory (default: logs/)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist (unless forcing new file handler)
    if logger.handlers and not log_file:
        return logger
    
    logger.setLevel(level)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
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
        
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler (always add if not exists)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler (if requested)
    if log_file or log_dir:
        try:
            if log_dir:
                log_dir_path = Path(log_dir)
                log_dir_path.mkdir(parents=True, exist_ok=True)
                if log_file:
                    log_file_path = log_dir_path / log_file
                else:
                    # Generate log file name from logger name
                    log_file_path = log_dir_path / f"{name.replace('.', '_')}.log"
            else:
                log_file_path = Path(log_file)
                log_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)  # More detailed in files
            file_handler.setFormatter(detailed_formatter)
            logger.addHandler(file_handler)
            
            logger.debug(f"File logging enabled: {log_file_path}")
            
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")
    
    return logger

