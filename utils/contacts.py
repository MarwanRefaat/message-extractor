"""
Contact name resolution for macOS
Uses AppleScript to query the Contacts app for reliability across macOS versions
"""
import subprocess
from typing import Optional, Dict

from utils.logger import get_logger

logger = get_logger(__name__)


# Cache contact lookups to avoid repeated queries
_contact_cache: Dict[str, Optional[str]] = {}


def get_contact_name(phone_number: str) -> Optional[str]:
    """
    Get contact name from macOS Contacts using phone number
    
    Args:
        phone_number: Phone number to look up (e.g., '+14159408750')
        
    Returns:
        Contact name if found, None otherwise
    """
    # Check cache first
    if phone_number in _contact_cache:
        return _contact_cache[phone_number]
    
    try:
        name = _query_contacts_via_apple_script(phone_number)
        _contact_cache[phone_number] = name
        return name
    except Exception as e:
        logger.debug(f"Failed to resolve contact name for {phone_number}: {e}")
        _contact_cache[phone_number] = None
        return None


def _query_contacts_via_apple_script(phone_number: str) -> Optional[str]:
    """
    Query Contacts using AppleScript (most reliable cross-platform method)
    
    Returns first matching contact name
    """
    # Normalize phone number: remove common formatting
    normalized = phone_number.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    
    # AppleScript to search Contacts
    script = f'''
    tell application "Contacts"
        try
            set foundPeople to (people whose value of phones contains "{normalized}")
            if (count of foundPeople) > 0 then
                set firstPerson to first item of foundPeople
                set firstName to first name of firstPerson
                set lastName to last name of firstPerson
                
                if firstName is not missing value and lastName is not missing value then
                    return firstName & " " & lastName
                else if firstName is not missing value then
                    return firstName
                else if lastName is not missing value then
                    return lastName
                else
                    return ""
                end if
            end if
        on error
            return ""
        end try
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0 and result.stdout.strip():
            name = result.stdout.strip()
            return name if name else None
    except subprocess.TimeoutExpired:
        logger.debug(f"AppleScript timeout for {phone_number}")
    except FileNotFoundError:
        logger.debug("osascript not found")
    except Exception as e:
        logger.debug(f"AppleScript error: {e}")
    
    return None


def get_email_contact_name(email: str) -> Optional[str]:
    """
    Get contact name from macOS Contacts using email address
    
    Args:
        email: Email address to look up
        
    Returns:
        Contact name if found, None otherwise
    """
    # Check cache first
    if email in _contact_cache:
        return _contact_cache[email]
    
    # AppleScript to search Contacts by email
    script = f'''
    tell application "Contacts"
        try
            set foundPeople to (people whose value of emails contains "{email}")
            if (count of foundPeople) > 0 then
                set firstPerson to first item of foundPeople
                set firstName to first name of firstPerson
                set lastName to last name of firstPerson
                
                if firstName is not missing value and lastName is not missing value then
                    return firstName & " " & lastName
                else if firstName is not missing value then
                    return firstName
                else if lastName is not missing value then
                    return lastName
                else
                    return ""
                end if
            end if
        on error
            return ""
        end try
    end tell
    '''
    
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        if result.returncode == 0 and result.stdout.strip():
            name = result.stdout.strip()
            _contact_cache[email] = name if name else None
            return _contact_cache[email]
    except subprocess.TimeoutExpired:
        logger.debug(f"AppleScript timeout for {email}")
    except FileNotFoundError:
        logger.debug("osascript not found")
    except Exception as e:
        logger.debug(f"AppleScript error: {e}")
    
    _contact_cache[email] = None
    return None


def clear_cache():
    """Clear the contact lookup cache"""
    global _contact_cache
    _contact_cache = {}


def get_cache_size() -> int:
    """Get number of cached contacts"""
    return len(_contact_cache)

