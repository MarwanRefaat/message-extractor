"""
Google Takeout Contacts extraction module
Extracts contacts from .vcf files for contact resolution
"""
import os
from typing import List, Dict
import re

from schema import Contact
from utils.logger import get_logger

logger = get_logger(__name__)


class GoogleTakeoutContactsExtractor:
    """Extract contacts from Google Takeout .vcf files"""
    
    def __init__(self, takeout_path: str = "raw_originals/Takeout/Contacts"):
        """
        Initialize Google Takeout Contacts extractor
        
        Args:
            takeout_path: Path to Google Takeout Contacts directory
        """
        self.takeout_path = takeout_path
        
        if not os.path.exists(self.takeout_path):
            raise FileNotFoundError(f"Google Takeout Contacts directory not found at: {self.takeout_path}")
    
    def extract_all(self) -> List[Contact]:
        """
        Extract all contacts from .vcf files
        
        Returns:
            List of Contact objects
        """
        contacts = []
        
        try:
            # Find all .vcf files
            vcf_files = []
            for root, dirs, files in os.walk(self.takeout_path):
                for file in files:
                    if file.endswith('.vcf'):
                        vcf_files.append(os.path.join(root, file))
            
            logger.info(f"Found {len(vcf_files)} contact file(s) to process")
            
            for vcf_file in vcf_files:
                file_contacts = self._parse_vcf_file(vcf_file)
                contacts.extend(file_contacts)
            
            logger.info(f"Extracted {len(contacts)} contacts")
        
        except Exception as error:
            logger.error(f'An error occurred extracting contacts: {error}')
            raise
        
        return contacts
    
    def _parse_vcf_file(self, vcf_file: str) -> List[Contact]:
        """Parse a .vcf file and return list of contacts"""
        contacts = []
        
        try:
            with open(vcf_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Split into individual vCard entries
            vcards = re.split(r'BEGIN:VCARD', content)
            
            for vcard in vcards[1:]:  # Skip first empty split
                try:
                    contact = self._parse_vcard(vcard)
                    if contact:
                        contacts.append(contact)
                except Exception as e:
                    logger.debug(f"Error parsing vCard: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Error parsing .vcf file {vcf_file}: {e}")
        
        return contacts
    
    def _parse_vcard(self, vcard: str) -> Contact:
        """Parse a single vCard entry"""
        name = None
        email = None
        phone = None
        
        # Extract FN (Full Name)
        fn_match = re.search(r'FN:(.+?)(?:\n|$)', vcard)
        if fn_match:
            name = fn_match.group(1).strip().strip('"')
        
        # Extract N (Name components)
        if not name:
            n_match = re.search(r'N:(.+?)(?:\n|$)', vcard)
            if n_match:
                name_parts = n_match.group(1).split(';')
                name = ' '.join([p for p in name_parts if p and p != '']).strip()
        
        # Extract EMAIL
        email_match = re.search(r'EMAIL[^:]*:(.+?)(?:\n|$)', vcard, re.IGNORECASE)
        if email_match:
            email = email_match.group(1).strip()
        
        # Extract TEL (phone)
        tel_match = re.search(r'TEL[^:]*:(.+?)(?:\n|$)', vcard, re.IGNORECASE)
        if tel_match:
            phone = tel_match.group(1).strip()
        
        # Only create contact if we have at least email or phone
        if email or phone:
            platform_id = email if email else phone if phone else str(hash(name or ''))
            
            return Contact(
                name=name if name else None,
                email=email if email else None,
                phone=phone if phone else None,
                platform_id=platform_id,
                platform="googletakeoutcontacts"
            )
        
        return None

