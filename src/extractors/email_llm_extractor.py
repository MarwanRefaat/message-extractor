"""
LLM-based email extraction module
Uses local LLM to intelligently parse emails from various sources (EML, JSON, raw text)
and extract structured message data robustly
"""
import json
import re
import email
import email.utils
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from schema import Message, Contact, UnifiedLedger
from utils.logger import get_logger
from utils.validators import validate_message, sanitize_json_data
from constants import FILTER_START_DATE

logger = get_logger(__name__)


class EmailLLMExtractor:
    """
    Extract emails using LLM for intelligent parsing
    
    This extractor can handle:
    - EML files
    - JSON email data
    - Raw email text
    - Apple Mail exports
    - Gmail API responses
    """
    
    def __init__(self, model_name: str = "gpt4all", temperature: float = 0.0):
        """
        Initialize LLM email extractor
        
        Args:
            model_name: Name of local LLM to use
            temperature: Sampling temperature (0.0 for deterministic)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.llm = None
        self.start_date = FILTER_START_DATE
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the local LLM"""
        try:
            from gpt4all import GPT4All
            fast_models = ["orca-mini-3b-gguf2-q4_0.gguf", "ggml-gpt4all-j-v1.3-groovy.bin", "gpt4all"]
            model_initialized = False
            
            for model in fast_models:
                try:
                    self.llm = GPT4All(model_name=model, allow_download=True, device='cpu')
                    logger.info(f"Initialized LLM model: {model}")
                    model_initialized = True
                    break
                except Exception:
                    continue
            
            if not model_initialized:
                self.llm = GPT4All(model_name=self.model_name, allow_download=True, device='cpu')
                logger.info(f"Initialized {self.model_name}")
        except ImportError:
            logger.warning("GPT4All not installed. Install with: pip install gpt4all")
            logger.warning("Falling back to rule-based extraction")
            self.llm = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
    
    def extract_from_file(self, file_path: str) -> UnifiedLedger:
        """
        Extract emails from a file (EML, JSON, or text)
        
        Args:
            file_path: Path to email file
            
        Returns:
            UnifiedLedger with extracted messages
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return ledger
        
        # Determine file type and extract
        if file_path.suffix.lower() == '.eml':
            messages = self._extract_from_eml(file_path)
        elif file_path.suffix.lower() == '.json' or file_path.suffix.lower() == '.jsonl':
            messages = self._extract_from_json(file_path)
        else:
            # Try to extract as raw text
            messages = self._extract_from_text(file_path)
        
        # Add messages to ledger
        for msg in messages:
            try:
                ledger.add_message(msg)
            except Exception as e:
                logger.warning(f"Failed to add message: {e}")
        
        return ledger
    
    def extract_from_directory(self, directory: str, max_files: Optional[int] = None) -> UnifiedLedger:
        """
        Extract emails from all files in a directory
        
        Args:
            directory: Directory containing email files
            max_files: Maximum number of files to process
            
        Returns:
            UnifiedLedger with extracted messages
        """
        ledger = UnifiedLedger(start_date=self.start_date)
        directory = Path(directory)
        
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return ledger
        
        # Find all email files
        email_files = []
        email_files.extend(directory.rglob("*.eml"))
        email_files.extend(directory.rglob("*.json"))
        email_files.extend(directory.rglob("*.jsonl"))
        
        if max_files:
            email_files = email_files[:max_files]
        
        logger.info(f"Found {len(email_files)} email files to process")
        
        for idx, email_file in enumerate(email_files, 1):
            if idx % 100 == 0:
                logger.info(f"Processing {idx}/{len(email_files)} files...")
            
            try:
                file_ledger = self.extract_from_file(str(email_file))
                for msg in file_ledger.messages:
                    ledger.add_message(msg)
            except Exception as e:
                logger.warning(f"Error processing {email_file}: {e}")
                continue
        
        logger.info(f"Extracted {len(ledger.messages)} emails from directory")
        return ledger
    
    def _extract_from_eml(self, eml_path: Path) -> List[Message]:
        """Extract messages from EML file using LLM for robust parsing"""
        try:
            with open(eml_path, 'rb') as f:
                msg = email.message_from_bytes(f.read())
            
            # Convert EML to text representation for LLM
            eml_text = self._eml_to_text(msg)
            
            # Use LLM to extract structured data
            if self.llm:
                message_dict = self._extract_with_llm(eml_text, "eml")
                if message_dict:
                    message = self._dict_to_message(message_dict)
                    return [message]
            
            # Fallback to rule-based extraction
            parsed = self._parse_eml_rule_based(msg, eml_path)
            return [parsed] if parsed else []
            
        except Exception as e:
            logger.warning(f"Error extracting from EML {eml_path}: {e}")
            return []
    
    def _extract_from_json(self, json_path: Path) -> List[Message]:
        """Extract messages from JSON/JSONL file"""
        messages = []
        
        try:
            if json_path.suffix.lower() == '.jsonl':
                # JSONL format - one JSON object per line
                with open(json_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            if self.llm:
                                message_dict = self._extract_with_llm(json.dumps(data), "json")
                            else:
                                message_dict = self._parse_json_rule_based(data)
                            
                            if message_dict:
                                message = self._dict_to_message(message_dict)
                                messages.append(message)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON on line {line_num} of {json_path}: {e}")
                            continue
            else:
                # Regular JSON file
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, list):
                    email_list = data
                elif isinstance(data, dict) and 'messages' in data:
                    email_list = data['messages']
                elif isinstance(data, dict):
                    email_list = [data]
                else:
                    logger.warning(f"Unexpected JSON structure in {json_path}")
                    return []
                
                for email_data in email_list:
                    if self.llm:
                        message_dict = self._extract_with_llm(json.dumps(email_data), "json")
                    else:
                        message_dict = self._parse_json_rule_based(email_data)
                    
                    if message_dict:
                        message = self._dict_to_message(message_dict)
                        messages.append(message)
            
            return messages
            
        except Exception as e:
            logger.warning(f"Error extracting from JSON {json_path}: {e}")
            return []
    
    def _extract_from_text(self, text_path: Path) -> List[Message]:
        """Extract messages from raw text file using LLM"""
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            if self.llm:
                # Use LLM to extract emails from text
                messages_dict = self._extract_batch_with_llm(text_content)
                return [self._dict_to_message(md) for md in messages_dict if md]
            else:
                logger.warning("LLM not available for text extraction")
                return []
                
        except Exception as e:
            logger.warning(f"Error extracting from text {text_path}: {e}")
            return []
    
    def _eml_to_text(self, msg: email.message.Message) -> str:
        """Convert EML message to text representation for LLM"""
        lines = []
        lines.append("=== EMAIL HEADERS ===")
        
        # Headers
        for key in ['From', 'To', 'Cc', 'Bcc', 'Subject', 'Date', 'Message-ID', 
                    'In-Reply-To', 'References', 'Thread-Topic', 'Thread-Index']:
            value = msg.get(key, '')
            if value:
                lines.append(f"{key}: {value}")
        
        lines.append("\n=== EMAIL BODY ===")
        
        # Body
        body = self._extract_body_from_eml(msg)
        lines.append(body)
        
        return '\n'.join(lines)
    
    def _extract_body_from_eml(self, msg: email.message.Message) -> str:
        """Extract plain text body from EML message, cleaning HTML and signatures"""
        body = ""
        
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
                            body = self._html_to_text(html_body)
                            break
                        except:
                            pass
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        body = payload.decode('utf-8', errors='ignore')
                    except:
                        pass
            elif content_type == "text/html":
                payload = msg.get_payload(decode=True)
                if payload:
                    try:
                        html_body = payload.decode('utf-8', errors='ignore')
                        body = self._html_to_text(html_body)
                    except:
                        pass
        
        # Clean up signatures and quoted text
        body = self._clean_email_body(body)
        return body.strip()
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text with better formatting"""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Replace common HTML elements with text equivalents
        html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'<p[^>]*>', '\n\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<div[^>]*>', '\n', html, flags=re.IGNORECASE)
        html = re.sub(r'</div>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<li[^>]*>', '\n• ', html, flags=re.IGNORECASE)
        
        # Remove all remaining HTML tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Decode HTML entities
        html = html.replace('&nbsp;', ' ')
        html = html.replace('&amp;', '&')
        html = html.replace('&lt;', '<')
        html = html.replace('&gt;', '>')
        html = html.replace('&quot;', '"')
        html = html.replace('&#39;', "'")
        
        # Clean up whitespace
        html = re.sub(r'\n\s*\n\s*\n+', '\n\n', html)  # Multiple newlines to double
        html = html.strip()
        
        return html
    
    def _clean_email_body(self, body: str) -> str:
        """Clean email body by removing signatures and quoted text"""
        if not body:
            return ""
        
        lines = body.split('\n')
        cleaned_lines = []
        in_quoted = False
        
        # Common signature/quote indicators
        quote_patterns = [
            r'^>+\s*',  # > quoted text
            r'^On .+ wrote:',  # "On ... wrote:"
            r'^From:',
            r'^Sent:',
            r'^To:',
            r'^Subject:',
            r'^-----Original Message-----',
            r'^________________________________',
            r'^-- ?$',  # Signature separator
        ]
        
        for line in lines:
            # Check if we're entering a quoted section
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in quote_patterns):
                in_quoted = True
            
            # Stop at signature separators (usually indicates end of message)
            if re.match(r'^--\s*$', line.strip()):
                # Keep this line if we haven't seen much content yet
                if len(cleaned_lines) < 5:
                    cleaned_lines.append(line)
                break
            
            if not in_quoted:
                cleaned_lines.append(line)
            elif line.strip() == '':
                # Empty line might end the quote
                in_quoted = False
        
        return '\n'.join(cleaned_lines)
    
    def _extract_with_llm(self, email_content: str, source_type: str) -> Optional[Dict[str, Any]]:
        """Use LLM to extract structured email data"""
        if not self.llm:
            return None
        
        prompt = self._build_email_extraction_prompt(email_content, source_type)
        
        try:
            response = self.llm.generate(
                prompt,
                max_tokens=4096,
                temp=self.temperature
            )
            
            # Parse LLM response
            message_dict = self._parse_llm_response(response)
            return message_dict
            
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            return None
    
    def _extract_batch_with_llm(self, text_content: str) -> List[Dict[str, Any]]:
        """Extract multiple emails from text content using LLM"""
        if not self.llm:
            return []
        
        # Split content into chunks if too large
        max_chunk_size = 8000
        if len(text_content) > max_chunk_size:
            # Try to split on email boundaries
            chunks = re.split(r'\n(?=From:|Subject:|Date:)', text_content)
        else:
            chunks = [text_content]
        
        all_messages = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            
            prompt = self._build_email_extraction_prompt(chunk, "text")
            try:
                response = self.llm.generate(
                    prompt,
                    max_tokens=4096,
                    temp=self.temperature
                )
                
                messages = self._parse_llm_response_list(response)
                all_messages.extend(messages)
            except Exception as e:
                logger.warning(f"LLM batch extraction failed: {e}")
                continue
        
        return all_messages
    
    def _build_email_extraction_prompt(self, email_content: str, source_type: str) -> str:
        """Build prompt for LLM to extract email data"""
        prompt = f"""Extract email information from the following {source_type} data and return a single JSON object.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON - no markdown, no code blocks, no explanations
2. Extract ALL email addresses from From, To, Cc, Bcc fields (parse name and email separately)
3. Parse timestamp from Date header (convert to ISO 8601 format: YYYY-MM-DDTHH:MM:SS)
4. Extract message body text with these rules:
   - Remove ALL HTML tags and convert to plain text
   - Remove email signatures (content after "--" or common signature patterns)
   - Remove quoted/replied text (lines starting with ">", "On ... wrote:", etc.)
   - Keep only the original message content
   - If body is empty after cleaning, use "[No content]" or "[Attachment only]"
5. Identify thread relationships using In-Reply-To or References headers
   - Set is_reply=true if In-Reply-To or References exist
   - Extract original_message_id from In-Reply-To header
   - Use first message ID from References as thread_id
6. Extract attachments list if present (from Content-Disposition headers or attachment parts)
7. The 'sender' and 'recipients' MUST be objects with: name, email, phone (null), platform_id (email address), platform ("email" or "gmail")
8. 'participants' is ALL unique people (sender + all recipients combined, no duplicates)
9. 'message_id' format: "email:message-id-header" or "email:unique-id" if no Message-ID
10. 'platform' should be "email" or "gmail" based on source
11. 'body' CANNOT be empty - use "[Attachment]", "[No content]", or "[Email signature only]" if no real content
12. NO unusual Unicode characters (no LS \\u2028 or PS \\u2029 line separators)
13. All string fields must be sanitized and safe for JSON
14. Subject line should be extracted and cleaned (remove "Re:", "Fwd:", etc. prefixes are OK but keep them)

Output Format:
{{
  "message_id": "email:unique_id",
  "platform": "email",
  "timestamp": "2024-01-01T12:00:00",
  "timezone": null,
  "sender": {{
    "name": "Sender Name",
    "email": "sender@example.com",
    "phone": null,
    "platform_id": "sender@example.com",
    "platform": "email"
  }},
  "recipients": [{{
    "name": "Recipient Name",
    "email": "recipient@example.com",
    "phone": null,
    "platform_id": "recipient@example.com",
    "platform": "email"
  }}],
  "participants": [
    {{"name": "Sender Name", "email": "sender@example.com", "phone": null, "platform_id": "sender@example.com", "platform": "email"}},
    {{"name": "Recipient Name", "email": "recipient@example.com", "phone": null, "platform_id": "recipient@example.com", "platform": "email"}}
  ],
  "subject": "Email Subject",
  "body": "Email body text here (cleaned, no HTML, no signatures)",
  "attachments": ["file1.pdf", "file2.jpg"],
  "thread_id": "message-id-if-thread",
  "is_read": null,
  "is_starred": null,
  "is_reply": false,
  "original_message_id": null,
  "event_start": null,
  "event_end": null,
  "event_location": null,
  "event_status": null,
  "raw_data": {{}}
}}

Now extract email from this data:

{email_content[:4000]}

Return ONLY the JSON object:"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response to extract JSON object"""
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'(\{.*\})', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        
        try:
            message_dict = json.loads(response)
            if isinstance(message_dict, dict):
                return message_dict
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Response: {response[:500]}")
            return None
    
    def _parse_llm_response_list(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response to extract JSON array"""
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        
        try:
            messages = json.loads(response)
            if isinstance(messages, list):
                return messages
            elif isinstance(messages, dict):
                return [messages]
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}")
            return []
    
    def _parse_eml_rule_based(self, msg: email.message.Message, eml_path: Path) -> Optional[Message]:
        """Rule-based EML parsing (fallback when LLM unavailable)"""
        # Parse Message-ID
        msg_id = msg.get("Message-ID", "")
        if not msg_id:
            msg_id = eml_path.stem
        
        # Parse timestamp
        date_str = msg.get("Date", "")
        if date_str:
            try:
                timestamp_tuple = email.utils.parsedate_tz(date_str)
                if timestamp_tuple:
                    timestamp = datetime.fromtimestamp(email.utils.mktime_tz(timestamp_tuple))
                else:
                    timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
            except (ValueError, TypeError):
                timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
        else:
            timestamp = datetime.fromtimestamp(eml_path.stat().st_mtime)
        
        # Filter by date
        if timestamp < self.start_date:
            logger.debug(f"Skipping email from {timestamp} (before filter date)")
            return None
        
        # Parse sender
        from_field = msg.get("From", "")
        name, email_addr = email.utils.parseaddr(from_field)
        
        # Ensure we have a valid email address for sender
        if not email_addr:
            logger.warning(f"No sender email found in {eml_path}, skipping")
            return None
        sender = Contact(
            name=name if name else None,
            email=email_addr,
            phone=None,
            platform_id=email_addr,
            platform="email"
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
                            platform="email"
                        ))
        
        participants = [sender] + recipients
        
        # Parse subject
        subject = msg.get("Subject", "")
        
        # Parse body
        body = self._extract_body_from_eml(msg)
        if not body:
            body = "[No content]"
        
        # Parse attachments
        attachments = []
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                attachments.append(filename)
        
        # Thread detection
        in_reply_to = msg.get("In-Reply-To", "")
        references = msg.get("References", "")
        is_reply = bool(in_reply_to or references)
        
        # Extract thread ID
        thread_id = None
        if references:
            ref_match = re.search(r'<(.*?)>', references.split()[0] if references else "")
            if ref_match:
                thread_id = ref_match.group(1)
        
        message = Message(
            message_id=f"email:{msg_id}",
            platform="email",
            timestamp=timestamp,
            timezone=None,
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=subject,
            body=body,
            attachments=attachments,
            thread_id=thread_id,
            is_read=None,
            is_starred=None,
            is_reply=is_reply,
            original_message_id=in_reply_to if in_reply_to else None,
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data={"eml_path": str(eml_path)}
        )
        
        return message
    
    def _parse_json_rule_based(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Rule-based JSON parsing (fallback when LLM unavailable)"""
        try:
            # Extract basic fields
            msg_id = data.get('id') or data.get('message_id') or data.get('Message-ID', '')
            if not msg_id:
                msg_id = f"email_{hash(str(data))}"
            
            # Parse timestamp
            timestamp_str = data.get('date') or data.get('timestamp') or data.get('Date', '')
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_str)
                    else:
                        timestamp = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                except:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            # Parse sender
            from_field = data.get('from') or data.get('From', {})
            if isinstance(from_field, dict):
                sender_email = from_field.get('email') or from_field.get('address', '')
                sender_name = from_field.get('name', '')
            else:
                name, email_addr = email.utils.parseaddr(str(from_field))
                sender_name = name
                sender_email = email_addr
            
            # Parse recipients
            recipients = []
            for field in ['to', 'To', 'cc', 'Cc', 'bcc', 'Bcc']:
                if field in data:
                    field_data = data[field]
                    if isinstance(field_data, list):
                        for item in field_data:
                            if isinstance(item, dict):
                                recipients.append(item.get('email') or item.get('address', ''))
                            else:
                                recipients.append(str(item))
                    elif isinstance(field_data, dict):
                        recipients.append(field_data.get('email') or field_data.get('address', ''))
                    else:
                        addrs = email.utils.getaddresses([str(field_data)])
                        recipients.extend([addr[1] for addr in addrs if addr[1]])
            
            # Build message dict
            body = data.get('body') or data.get('text') or data.get('content', '')
            if not body:
                body = "[No content]"
            
            return {
                'message_id': f"email:{msg_id}",
                'platform': 'email',
                'timestamp': timestamp.isoformat(),
                'sender': {
                    'name': sender_name,
                    'email': sender_email,
                    'phone': None,
                    'platform_id': sender_email,
                    'platform': 'email'
                },
                'recipients': [{
                    'name': None,
                    'email': r,
                    'phone': None,
                    'platform_id': r,
                    'platform': 'email'
                } for r in set(recipients) if r],
                'participants': [{
                    'name': sender_name,
                    'email': sender_email,
                    'phone': None,
                    'platform_id': sender_email,
                    'platform': 'email'
                }] + [{
                    'name': None,
                    'email': r,
                    'phone': None,
                    'platform_id': r,
                    'platform': 'email'
                } for r in set(recipients) if r],
                'subject': data.get('subject') or data.get('Subject', ''),
                'body': body,
                'attachments': data.get('attachments', []) or [],
                'thread_id': data.get('thread_id') or data.get('threadId'),
                'is_reply': bool(data.get('in_reply_to') or data.get('In-Reply-To')),
                'original_message_id': data.get('in_reply_to') or data.get('In-Reply-To')
            }
        except Exception as e:
            logger.warning(f"Error in rule-based JSON parsing: {e}")
            return None
    
    def _dict_to_message(self, msg_dict: Dict[str, Any]) -> Message:
        """Convert dictionary to Message object"""
        # Sanitize first
        msg_dict = sanitize_json_data({'messages': [msg_dict]})['messages'][0]
        
        # Validate
        errors = validate_message(msg_dict)
        if errors:
            logger.warning(f"Message validation errors: {errors[:3]}")
        
        # Parse timestamp
        timestamp = datetime.fromisoformat(msg_dict['timestamp'].replace('Z', '+00:00'))
        
        # Parse sender
        sender_dict = msg_dict['sender']
        sender = Contact(
            name=sender_dict.get('name'),
            email=sender_dict.get('email'),
            phone=sender_dict.get('phone'),
            platform_id=sender_dict['platform_id'],
            platform=sender_dict['platform']
        )
        
        # Parse recipients
        recipients = []
        for r in msg_dict.get('recipients', []):
            recipients.append(Contact(
                name=r.get('name'),
                email=r.get('email'),
                phone=r.get('phone'),
                platform_id=r['platform_id'],
                platform=r['platform']
            ))
        
        # Parse participants
        if 'participants' in msg_dict and msg_dict['participants']:
            participants = []
            for p in msg_dict['participants']:
                participants.append(Contact(
                    name=p.get('name'),
                    email=p.get('email'),
                    phone=p.get('phone'),
                    platform_id=p['platform_id'],
                    platform=p['platform']
                ))
        else:
            participants = [sender] + recipients
        
        # Create message
        message = Message(
            message_id=msg_dict['message_id'],
            platform=msg_dict.get('platform', 'email'),
            timestamp=timestamp,
            timezone=msg_dict.get('timezone'),
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=msg_dict.get('subject'),
            body=msg_dict.get('body', '[No content]'),
            attachments=msg_dict.get('attachments', []),
            thread_id=msg_dict.get('thread_id'),
            is_read=msg_dict.get('is_read'),
            is_starred=msg_dict.get('is_starred'),
            is_reply=msg_dict.get('is_reply', False),
            original_message_id=msg_dict.get('original_message_id'),
            event_start=None,
            event_end=None,
            event_location=None,
            event_status=None,
            raw_data=msg_dict.get('raw_data', {})
        )
        
        return message

