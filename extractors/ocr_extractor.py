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


def extract_text_from_image(image_path: str, max_length: int = 500) -> Optional[str]:
    """
    Extract text from an image using Tesseract OCR
    
    Args:
        image_path: Path to image file
        max_length: Maximum length of extracted text
        
    Returns:
        Extracted text or None if extraction fails
    """
    if not _check_ocr_available():
        return None
    
    if not os.path.exists(image_path):
        return None
    
    try:
        from PIL import Image
        
        image = Image.open(image_path)
        text = _pytesseract.image_to_string(image, config='--psm 6')  # Uniform block of text
        
        if text:
            # Clean up text - remove extra whitespace
            text = ' '.join(text.split())
            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."
            return text.strip() if text.strip() else None
    except Exception as e:
        logger.debug(f"OCR extraction failed for {image_path}: {e}")
    
    return None


def extract_from_attachment_path(attachment_path: str, max_length: int = 500) -> Optional[str]:
    """
    Extract text from attachment if it's an image
    
    Args:
        attachment_path: Path to attachment file
        max_length: Maximum length of extracted text
        
    Returns:
        Extracted text or None
    """
    if not attachment_path:
        return None
    
    # Check if file exists
    if not os.path.exists(attachment_path):
        # Try relative to common attachment locations
        possible_paths = [
            attachment_path,
            os.path.join(os.path.expanduser("~"), "Library/Messages/Attachments", attachment_path),
        ]
        attachment_path = None
        for path in possible_paths:
            if os.path.exists(path):
                attachment_path = path
                break
        
        if not attachment_path:
            return None
    
    # Check if it's an image
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    ext = Path(attachment_path).suffix.lower()
    
    if ext in image_extensions:
        return extract_text_from_image(attachment_path, max_length)
    
    return None

