"""
LLM-based extraction module
Uses local LLM to extract and structure messages from raw data
"""
import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from schema import Message, Contact, UnifiedLedger
from utils.logger import get_logger
from utils.validators import validate_message, sanitize_json_data

logger = get_logger(__name__)


class LLMExtractor:
    """
    Extract and structure messages using local LLM
    
    This module uses a local LLM to intelligently extract and structure
    messages from raw data sources, ensuring validated JSON output.
    """
    
    def __init__(self, model_name: str = "gpt4all", temperature: float = 0.0):
        """
        Initialize LLM extractor
        
        Args:
            model_name: Name of local LLM to use
            temperature: Sampling temperature (0.0 for deterministic)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the local LLM"""
        try:
            # Try to import GPT4All or other local LLM
            from gpt4all import GPT4All
            # Use a small, fast model for speed
            # Try smaller models first for speed, fall back to default
            fast_models = ["orca-mini-3b-gguf2-q4_0.gguf", "ggml-gpt4all-j-v1.3-groovy.bin", "gpt4all"]
            model_initialized = False
            
            for model in fast_models:
                try:
                    self.llm = GPT4All(model_name=model, allow_download=True, device='cpu')
                    logger.info(f"Initialized fast LLM model: {model}")
                    model_initialized = True
                    break
                except Exception:
                    continue
            
            if not model_initialized:
                # Fall back to default
                self.llm = GPT4All(model_name=self.model_name, allow_download=True, device='cpu')
                logger.info(f"Initialized {self.model_name}")
        except ImportError:
            logger.warning("GPT4All not installed. Install with: pip install gpt4all")
            logger.warning("Falling back to manual extraction")
            self.llm = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
    
    def extract_all(self, raw_data_source: str) -> UnifiedLedger:
        """
        Extract messages from raw data using LLM
        
        Args:
            raw_data_source: Path to raw data file or string containing raw data
            
        Returns:
            UnifiedLedger with extracted messages
        """
        ledger = UnifiedLedger()
        
        if not self.llm:
            logger.error("LLM not initialized")
            return ledger
        
        # Read raw data
        try:
            with open(raw_data_source, 'r', encoding='utf-8') as f:
                raw_data = f.read()
        except:
            raw_data = raw_data_source
        
        # Process in batches if too large
        if len(raw_data) > 10000:
            logger.info("Large dataset, processing in batches...")
            messages = self._extract_batch(raw_data)
        else:
            messages = self._extract_single(raw_data)
        
        # Validate and add messages
        for msg_dict in messages:
            try:
                # Create Message object
                message = self._dict_to_message(msg_dict)
                ledger.add_message(message)
            except Exception as e:
                logger.warning(f"Failed to add message: {e}")
        
        return ledger
    
    def _extract_single(self, raw_data: str) -> List[Dict[str, Any]]:
        """Extract messages from single data chunk"""
        prompt = self._build_extraction_prompt(raw_data)
        
        # Get LLM response
        response = self.llm.generate(
            prompt,
            max_tokens=4096,
            temp=self.temperature
        )
        
        # Extract JSON from response
        return self._parse_llm_response(response)
    
    def _extract_batch(self, raw_data: str) -> List[Dict[str, Any]]:
        """Extract messages from large data in batches"""
        # Split into chunks
        chunk_size = 8000
        chunks = [raw_data[i:i+chunk_size] for i in range(0, len(raw_data), chunk_size)]
        
        all_messages = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            messages = self._extract_single(chunk)
            all_messages.extend(messages)
        
        return all_messages
    
    def _build_extraction_prompt(self, raw_data: str) -> str:
        """
        Build extraction prompt for LLM
        
        Returns a prompt that instructs the LLM to extract messages
        in the exact JSON structure we need.
        """
        prompt = f"""Extract all messages from the following data and return them in a JSON array.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON - no markdown, no code blocks, no explanations
2. Each message MUST have these fields: message_id, platform, timestamp, sender, recipients, participants, body, raw_data
3. Timestamps MUST be ISO 8601 format: YYYY-MM-DDTHH:MM:SS
4. The 'sender' and 'recipients' MUST be objects with: name, email, phone, platform_id, platform
5. 'platform_id' CANNOT be empty or null - must have a value
6. 'body' CANNOT be empty - if no text, use a label like '[Attachment]' or '[Tapback]'
7. 'participants' is a list of ALL unique people (sender + recipients combined)
8. NO unusual Unicode characters (no LS \\u2028 or PS \\u2029 line separators)
9. All string fields must be sanitized and safe for JSON

Output Format:
[
  {{
    "message_id": "platform:unique_id",
    "platform": "imessage",
    "timestamp": "2024-01-01T12:00:00",
    "timezone": null,
    "sender": {{
      "name": null,
      "email": null,
      "phone": "+1234567890",
      "platform_id": "+1234567890",
      "platform": "imessage"
    }},
    "recipients": [{{
      "name": "Me",
      "email": null,
      "phone": null,
      "platform_id": "me",
      "platform": "imessage"
    }}],
    "participants": [
      {{"name": null, "email": null, "phone": "+1234567890", "platform_id": "+1234567890", "platform": "imessage"}},
      {{"name": "Me", "email": null, "phone": null, "platform_id": "me", "platform": "imessage"}}
    ],
    "subject": null,
    "body": "Message text here",
    "attachments": [],
    "thread_id": null,
    "is_read": true,
    "is_starred": false,
    "is_reply": false,
    "original_message_id": null,
    "event_start": null,
    "event_end": null,
    "event_location": null,
    "event_status": null,
    "raw_data": {{}}
  }}
]

Now extract messages from this data:

{raw_data[:5000]}

Return ONLY the JSON array:"""
        
        return prompt
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response and extract JSON
        
        Handles various response formats:
        - Pure JSON
        - JSON in code blocks
        - JSON with markdown
        """
        # Remove markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            response = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
        
        # Try to parse JSON
        try:
            messages = json.loads(response)
            if not isinstance(messages, list):
                logger.error("LLM response is not a JSON array")
                return []
            return messages
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Response: {response[:500]}")
            return []
    
    def _dict_to_message(self, msg_dict: Dict[str, Any]) -> Message:
        """Convert dictionary to Message object"""
        # First sanitize
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
        
        # Parse participants (or generate from sender + recipients)
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
        
        # Parse optional event fields
        event_start = None
        if msg_dict.get('event_start'):
            event_start = datetime.fromisoformat(msg_dict['event_start'].replace('Z', '+00:00'))
        
        event_end = None
        if msg_dict.get('event_end'):
            event_end = datetime.fromisoformat(msg_dict['event_end'].replace('Z', '+00:00'))
        
        # Create message
        message = Message(
            message_id=msg_dict['message_id'],
            platform=msg_dict['platform'],
            timestamp=timestamp,
            timezone=msg_dict.get('timezone'),
            sender=sender,
            recipients=recipients,
            participants=participants,
            subject=msg_dict.get('subject'),
            body=msg_dict['body'],
            attachments=msg_dict.get('attachments', []),
            thread_id=msg_dict.get('thread_id'),
            is_read=msg_dict.get('is_read'),
            is_starred=msg_dict.get('is_starred'),
            is_reply=msg_dict.get('is_reply'),
            original_message_id=msg_dict.get('original_message_id'),
            event_start=event_start,
            event_end=event_end,
            event_location=msg_dict.get('event_location'),
            event_status=msg_dict.get('event_status'),
            raw_data=msg_dict.get('raw_data', {})
        )
        
        return message
    
    def export_raw(self, output_dir: str):
        """
        Export raw LLM-processed data
        
        Args:
            output_dir: Directory to save output
        """
        logger.warning("LLMExtractor.export_raw not implemented")
        pass

