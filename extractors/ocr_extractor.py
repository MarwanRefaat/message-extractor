"""
Lightweight OCR extractor for attachments
Uses Tesseract for fast, coarse OCR extraction
"""
import os
from typing import Optional
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)

_ocr_available = None
_pytesseract = None


def _check_ocr_available():
    """Check if OCR is available"""
    global _ocr_available, _pytesseract
    
    if _ocr_available is not None:
        return _ocr_available
    
    try:
        import pytesseract
        from PIL import Image
        
        # Try to get version to verify it's installed
        try:
            pytesseract.get_tesseract_version()
            _pytesseract = pytesseract
            _ocr_available = True
            return True
        except Exception:
            logger.debug("Tesseract not found in PATH")
            _ocr_available = False
            return False
    except ImportError:
        logger.debug("pytesseract or PIL not installed")
        _ocr_available = False
        return False


def extract_text_from_image(image_path: str, max_length: int = 300, max_file_size_mb: int = 5) -> Optional[str]:
    """
    Extract text from an image using Tesseract OCR (fast, optimized for speed)
    
    Args:
        image_path: Path to image file
        max_length: Maximum length of extracted text
        max_file_size_mb: Skip files larger than this (MB) for speed
        
    Returns:
        Extracted text or None if extraction fails/skipped
    """
    if not _check_ocr_available():
        return None
    
    if not os.path.exists(image_path):
        return None
    
    # Skip large files for speed
    try:
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            return None  # Skip large files
    except Exception:
        pass
    
    try:
        from PIL import Image
        
        # Quick size check before processing
        image = Image.open(image_path)
        width, height = image.size
        # Skip very large images (>10MP) for speed
        if width * height > 10_000_000:
            return None
        
        # Fast OCR with minimal config for speed
        text = _pytesseract.image_to_string(image, config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?@#$%&*()_+-=[]{}|;:,.<>?/~`')  # Quick config
        
        if text:
            # Quick cleanup - remove extra whitespace
            text = ' '.join(text.split())
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            return text.strip() if text.strip() else None
    except Exception as e:
        logger.debug(f"OCR extraction failed for {image_path}: {e}")
    
    return None


def extract_from_attachment_path(attachment_path: str, max_length: int = 300, max_file_size_mb: int = 5) -> Optional[str]:
    """
    Extract text from attachment if it's an image (fast, optimized for speed)
    
    Args:
        attachment_path: Path to attachment file
        max_length: Maximum length of extracted text
        max_file_size_mb: Skip files larger than this (MB) for speed
        
    Returns:
        Extracted text or None
    """
    if not attachment_path:
        return None
    
    # Check if file exists
    actual_path = None
    if os.path.exists(attachment_path):
        actual_path = attachment_path
    else:
        # Try relative to common attachment locations (quick check)
        possible_paths = [
            os.path.join(os.path.expanduser("~"), "Library/Messages/Attachments", os.path.basename(attachment_path)),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                actual_path = path
                break
        
        if not actual_path:
            return None
    
    # Quick size check - skip large files immediately for speed
    try:
        file_size_mb = os.path.getsize(actual_path) / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            return None  # Skip large files
    except Exception:
        return None
    
    # Check if it's an image
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    ext = Path(actual_path).suffix.lower()
    
    if ext in image_extensions:
        return extract_text_from_image(actual_path, max_length, max_file_size_mb)
    
    return None

