"""
OCR extractor for image attachments
Uses local OCR models to extract text from images
"""
import os
from typing import Optional, List
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)


class OCRExtractor:
    """
    Extract text from images using local OCR models
    
    Supports multiple OCR backends:
    - EasyOCR (recommended, best accuracy)
    - pytesseract (Tesseract, lightweight)
    """
    
    def __init__(self, backend: str = "easyocr"):
        """
        Initialize OCR extractor
        
        Args:
            backend: OCR backend to use ('easyocr' or 'tesseract')
        """
        self.backend = backend
        self.easyocr_reader = None
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the selected OCR backend"""
        if self.backend == "easyocr":
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                logger.info("Initialized EasyOCR")
            except ImportError:
                logger.warning("EasyOCR not installed. Install with: pip install easyocr")
                logger.warning("Falling back to pytesseract")
                self._initialize_tesseract()
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                logger.warning("Falling back to pytesseract")
                self._initialize_tesseract()
        elif self.backend == "tesseract":
            self._initialize_tesseract()
    
    def _initialize_tesseract(self):
        """Initialize Tesseract OCR"""
        try:
            import pytesseract
            # Check if tesseract is installed
            from PIL import Image
            try:
                pytesseract.get_tesseract_version()
                logger.info("Initialized pytesseract (Tesseract)")
            except Exception:
                logger.warning("Tesseract not found in system PATH")
                logger.warning("Install Tesseract: brew install tesseract (macOS)")
                logger.warning("OCR functionality will be disabled")
        except ImportError:
            logger.warning("pytesseract not installed. Install with: pip install pytesseract pillow")
            logger.warning("OCR functionality will be disabled")
    
    def extract_text_from_image(self, image_path: str) -> Optional[str]:
        """
        Extract text from an image file
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text or None if extraction fails
        """
        if not os.path.exists(image_path):
            logger.warning(f"Image not found: {image_path}")
            return None
        
        try:
            if self.backend == "easyocr" and self.easyocr_reader:
                return self._extract_with_easyocr(image_path)
            elif self.backend == "tesseract":
                return self._extract_with_tesseract(image_path)
            else:
                logger.warning("No OCR backend available")
                return None
        except Exception as e:
            logger.error(f"OCR extraction failed for {image_path}: {e}")
            return None
    
    def _extract_with_easyocr(self, image_path: str) -> Optional[str]:
        """Extract text using EasyOCR"""
        if not self.easyocr_reader:
            return None
        
        try:
            results = self.easyocr_reader.readtext(image_path, detail=0)
            text = "\n".join(results)
            return text if text else None
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return None
    
    def _extract_with_tesseract(self, image_path: str) -> Optional[str]:
        """Extract text using Tesseract"""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip() if text.strip() else None
        except Exception as e:
            logger.error(f"Tesseract failed: {e}")
            return None
    
    def extract_from_directory(self, directory: str) -> List[tuple]:
        """
        Extract text from all images in a directory
        
        Args:
            directory: Directory containing images
            
        Returns:
            List of (filename, extracted_text) tuples
        """
        results = []
        
        if not os.path.exists(directory):
            logger.warning(f"Directory not found: {directory}")
            return results
        
        # Supported image formats
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        
        for file_path in Path(directory).rglob('*'):
            if file_path.suffix.lower() in image_extensions:
                text = self.extract_text_from_image(str(file_path))
                if text:
                    results.append((file_path.name, text))
        
        return results


def get_image_description(image_path: str) -> Optional[str]:
    """
    Get a description of image content
    Useful for providing context about what's in the image
    
    Args:
        image_path: Path to image file
        
    Returns:
        Brief description or OCR text
    """
    try:
        extractor = OCRExtractor()
        text = extractor.extract_text_from_image(image_path)
        
        if text:
            # Return first 500 chars of extracted text
            return text[:500] + "..." if len(text) > 500 else text
        else:
            # No text found, return generic description
            return "[Image - no text detected]"
    except Exception as e:
        logger.error(f"Failed to get image description: {e}")
        return "[Image - extraction failed]"


