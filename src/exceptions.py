"""
Custom exceptions for the message extractor
"""
from typing import Optional


class MessageExtractorError(Exception):
    """Base exception for message extractor"""
    pass


class ConfigurationError(MessageExtractorError):
    """Configuration or setup error"""
    pass


class ExtractionError(MessageExtractorError):
    """Error during extraction"""
    pass


class AuthenticationError(MessageExtractorError):
    """Authentication error"""
    pass


class DatabaseError(MessageExtractorError):
    """Database access error"""
    pass


class PlatformNotSupportedError(MessageExtractorError):
    """Platform not supported error"""
    pass


class DataFormatError(MessageExtractorError):
    """Error parsing or formatting data"""
    pass

