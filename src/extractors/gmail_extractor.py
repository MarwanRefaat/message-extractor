"""
Gmail extraction module using gmail-exporter tool
Uses gmail-exporter to export emails as EML files, then parses them
"""
import os
import subprocess
from datetime import datetime
from typing import List, Optional
import json
import email.message
import email.utils
import re
from pathlib import Path

from schema import Message, Contact, UnifiedLedger
from constants import FILTER_START_DATE
from exceptions import ExtractionError
from utils.logger import get_logger

logger = get_logger(__name__)


class GmailExtractor:
    """Extract emails from Gmail using gmail-exporter tool"""
    
    # Email addresses to filter for
    TARGET_EMAILS = ["marwan@marwanrefaat.com", "marwan@fractalfund.com"]
    
    def __init__(self, gmail_exporter_path: Optional[str] = None, 
                 export_dir: Optional[str] = None):
        """
        Initialize Gmail extractor
        
        Args:
            gmail_exporter_path: Path to gmail-exporter binary (default: tools/gmail-exporter/gmail-exporter)
            export_dir: Directory to export emails to (default: gmail_export)
        """
        self.start_date = FILTER_START_DATE
        
        # Find gmail-exporter binary
        if gmail_exporter_path:
            self.gmail_exporter_path = gmail_exporter_path
        else:
            # Try to find it in tools directory
            # Get the project root (go up from src/extractors/)
            script_dir = Path(__file__).parent.parent.parent
            # If we're in src/, go up one more level
            if script_dir.name == "src":
                script_dir = script_dir.parent
            
            possible_paths = [
                script_dir / "tools" / "gmail-exporter" / "gmail-exporter",
                script_dir / "tools" / "gmail-exporter",
                Path("tools/gmail-exporter/gmail-exporter"),
                Path("tools/gmail-exporter"),
                Path("../tools/gmail-exporter/gmail-exporter"),
                Path("../../tools/gmail-exporter/gmail-exporter"),
            ]
            
            self.gmail_exporter_path = None
            for path in possible_paths:
                if path.exists() and os.access(path, os.X_OK):
                    self.gmail_exporter_path = str(path)
                    break
            
            if not self.gmail_exporter_path:
                # Try to build it
                build_dir = script_dir / "tools" / "gmail-exporter"
                if build_dir.exists():
                    logger.info(f"Building gmail-exporter from {build_dir}...")
                    try:
                        result = subprocess.run(
                            ["go", "build", "-o", "gmail-exporter"],
                            cwd=build_dir,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")}
                        )
                        if result.returncode == 0:
                            self.gmail_exporter_path = str(build_dir / "gmail-exporter")
                            logger.info(f"Built gmail-exporter at {self.gmail_exporter_path}")
                        else:
                            logger.warning(f"Failed to build gmail-exporter: {result.stderr}")
                    except FileNotFoundError:
                        logger.warning("Go compiler not found. Please build gmail-exporter manually.")
                    except Exception as e:
                        logger.warning(f"Error building gmail-exporter: {e}")
        
        if not self.gmail_exporter_path:
            raise FileNotFoundError(
                "gmail-exporter not found. Please build it first:\n"
                "  cd tools/gmail-exporter && go build -o gmail-exporter"
            )
        
        self.export_dir = Path(export_dir) if export_dir else Path("gmail_export")
        self.eml_dir = self.export_dir / "messages"
        self.spreadsheet_path = self.export_dir / "messages.xlsx"
    
    def _run_gmail_exporter(self, labels: List[str] = None) -> bool:
        """
        Run gmail-exporter to export emails
        
        Args:
            labels: Gmail labels to filter by (default: ['INBOX', 'SENT'] for main folders)
        
        Returns:
            True if export was successful
        """
        logger.info(f"Running gmail-exporter to export emails...")
        
        # Prepare command
        cmd = [
            self.gmail_exporter_path,
            "export",
            "--save-eml",
            "--eml-dir", str(self.eml_dir),
            "--out-file", str(self.spreadsheet_path),
            "--no-attachments",  # Skip attachments for now (can add later if needed)
        ]
        
        # Add labels if specified, otherwise use INBOX and SENT
        if labels:
            cmd.extend(labels)
        else:
            # Export from INBOX and SENT folders
            cmd.extend(["INBOX", "SENT"])
        
        try:
            # Set working directory to gmail-exporter's directory so it can find credentials.json and token.json
            gmail_exporter_dir = Path(self.gmail_exporter_path).parent
            
            logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                cwd=str(gmail_exporter_dir),
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                logger.error(f"gmail-exporter failed: {result.stderr}")
                return False
            
            logger.info(f"gmail-exporter completed successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("gmail-exporter timed out")
            return False
        except Exception as e:
            logger.error(f"Error running gmail-exporter: {e}")
            return False
    
    def _email_matches_target(self, msg: email.message.Message) -> bool:
        """Check if email is to/from one of our target email addresses"""
        # Get From, To, Cc, Bcc headers
        from_addr = msg.get("From", "")
        to_addr = msg.get("To", "")
        cc_addr = msg.get("Cc", "")
        bcc_addr = msg.get("Bcc", "")
        
        # Extract email addresses from headers
        all_addresses = []
        
        for header in [from_addr, to_addr, cc_addr, bcc_addr]:
            if header:
                # Parse address list
                addrs = email.utils.getaddresses([header])
                all_addresses.extend([addr[1].lower() for addr in addrs if addr[1]])
        
        # Check if any target email is in the list
        for addr in all_addresses:
            if any(target.lower() in addr for target in self.TARGET_EMAILS):
                return True
        
        return False
    
    def _parse_eml_file(self, eml_path: Path) -> Optional[Message]:
        """Parse an EML file and convert to Message"""
        try:
            with open(eml_path, 'rb') as f:
                msg = email.message.message_from_bytes(f.read())
            
            # Filter by target emails
            if not self._email_matches_target(msg):
                return None
            
            # Parse message ID
            msg_id = msg.get("Message-ID", "")
            if not msg_id:
                msg_id = eml_path.stem  # Use filename as fallback
            
            # Parse timestamp
            date_str = msg.get("Date", "")
            if date_str:
                try:
                    timestamp_tuple = email.utils.parsedate_tz(date_str)
                    if timestamp_tuple:
                        timestamp = datetime.fromtimestamp(email.utils.mktime_tz(timestamp_tuple))
                    else:
                        # Fallback
                        timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
                except (ValueError, TypeError):
                    timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
            else:
                timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
            
            # Filter by date
            if timestamp < self.start_date:
                return None
            
            # Parse sender
            from_field = msg.get("From", "")
            name, email_addr = email.utils.parseaddr(from_field)
            sender = Contact(
                name=name if name else None,
                email=email_addr,
                phone=None,
                platform_id=email_addr,
                platform="gmail"
            )
            
            # Parse recipients
            recipients = []
            for field in ["To", "Cc", "Bcc"]:
                header = msg.get(field, "")
                if header:
                    addrs = email.utils.getaddresses([header])
                    for addr_name, addr_email in addrs:
                        if addr_email:
                            recipients.append(Contact(
                                name=addr_name if addr_name else None,
                                email=addr_email,
                                phone=None,
                                platform_id=addr_email,
                                platform="gmail"
                            ))
            
            participants = [sender] + recipients
            
            # Parse subject
            subject = msg.get("Subject", "")
            
            # Parse body
            body = self._extract_body(msg)
            
            # Parse attachments
            attachments = []
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)
            
            # Get In-Reply-To for thread detection
            in_reply_to = msg.get("In-Reply-To", "")
            references = msg.get("References", "")
            original_message_id = in_reply_to if in_reply_to else (references.split()[0] if references else None)
            is_reply = original_message_id is not None
            
            # Extract thread ID from References or use message ID prefix
            thread_id = None
            if references:
                # Try to extract thread ID from first reference
                thread_match = re.search(r'<(.*?)>', references.split()[0] if references else "")
                if thread_match:
                    thread_id = thread_match.group(1)
            
            message = Message(
                message_id=f"gmail:{msg_id}",
                platform="gmail",
                timestamp=timestamp,
                timezone=None,
                sender=sender,
                recipients=recipients,
                participants=participants,
                subject=subject,
                body=body,
                attachments=attachments,
                thread_id=thread_id,
                is_read=None,  # Not available in EML
                is_starred=None,  # Not available in EML
                is_reply=is_reply,
                original_message_id=original_message_id,
                event_start=None,
                event_end=None,
                event_location=None,
                event_status=None,
                raw_data={"eml_path": str(eml_path)}
            )
            
            return message
            
        except Exception as e:
            logger.warning(f"Error parsing EML file {eml_path}: {e}")
            return None
    
    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract body text from email message"""
        body = ""
        
        # Try to get plain text first
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            body = payload.decode('utf-8', errors='ignore')
                            break
                        except:
                            pass
                elif content_type == "text/html" and not body:
                    # Fallback to HTML if no plain text
                    payload = part.get_payload(decode=True)
                    if payload:
                        try:
                            html_body = payload.decode('utf-8', errors='ignore')
                            # Simple HTML tag removal (can be enhanced)
                            body = re.sub(r'<[^>]+>', '', html_body)
                            break
                        except:
                            pass
        else:
            # Single part message
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        body = payload.decode('utf-8', errors='ignore')
                    except:
                        pass
        
        return body.strip()
    
    def extract_all(self, max_results: int = 10000) -> UnifiedLedger:
        """
        Extract all emails from Gmail using gmail-exporter
        
        Args:
            max_results: Maximum number of messages to retrieve (note: gmail-exporter may not respect this)
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        
        # Run gmail-exporter
        if not self._run_gmail_exporter():
            raise ExtractionError("Failed to export emails using gmail-exporter")
        
        # Find all EML files
        eml_files = list(self.eml_dir.rglob("*.eml"))
        logger.info(f"Found {len(eml_files)} EML files to process")
        
        # Parse EML files
        processed = 0
        for eml_path in eml_files:
            if processed >= max_results:
                break
            
            try:
                message = self._parse_eml_file(eml_path)
                if message:
                    ledger.add_message(message)
                    processed += 1
                    
                    if processed % 100 == 0:
                        logger.debug(f"Processed {processed}/{len(eml_files)} emails")
                        
            except Exception as e:
                logger.warning(f"Error processing {eml_path}: {e}")
                continue
        
        logger.info(f"Extracted {len(ledger.messages)} emails matching criteria")
        return ledger
    
    def export_raw(self, output_dir: str, max_results: int = 10000):
        """Export raw Gmail data using gmail-exporter"""
        # Set export directory to output_dir
        self.export_dir = Path(output_dir) / "gmail"
        self.eml_dir = self.export_dir / "messages"
        self.spreadsheet_path = self.export_dir / "messages.xlsx"
        
        os.makedirs(self.export_dir, exist_ok=True)
        
        # Run gmail-exporter
        if self._run_gmail_exporter():
            logger.info(f"Exported Gmail data to {self.export_dir}")
        else:
            logger.error("Failed to export Gmail data")
