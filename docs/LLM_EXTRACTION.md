# LLM-Based Extraction

## Overview

The LLM extractor provides an intelligent alternative to direct database extraction. It uses a local LLM (like GPT4All) to parse raw data and structure it into our standardized JSON format with automatic validation and sanitization.

## Why LLM Extraction?

1. **Intelligent Parsing**: Can handle unstructured or semi-structured data
2. **Format Adaptation**: Works with various input formats
3. **Quality Guaranteed**: Built-in validation and sanitization
4. **Privacy**: Everything runs locally

## Setup

Install GPT4All (or another local LLM):

```bash
pip install gpt4all
```

## Usage

```python
from extractors.llm_extractor import LLMExtractor

# Initialize extractor
extractor = LLMExtractor(model_name="gpt4all-j-v1.3-groovy")

# Extract from raw data
ledger = extractor.extract_all("path/to/raw_data.txt")

# Or pass raw data string directly
ledger = extractor.extract_all("Raw message data here...")

# Export results
ledger.export_to_json("output.json")
```

## How It Works

1. **Prompt Construction**: Builds a detailed prompt with exact JSON schema requirements
2. **LLM Generation**: Sends prompt to local LLM and receives structured response
3. **Response Parsing**: Extracts JSON from various formats (code blocks, markdown, etc.)
4. **Sanitization**: Removes null bytes, unusual line terminators, limits lengths
5. **Validation**: Validates all fields against regex patterns
6. **Object Creation**: Converts to Message objects and adds to ledger

## Prompt Engineering

The LLM is given a strict prompt that:
- Demands valid JSON only (no markdown, no explanations)
- Specifies exact field structure
- Requires ISO 8601 timestamps
- Forbids empty bodies or missing platform_ids
- Prevents unusual Unicode characters
- Includes example output format

## Validation & Sanitization

All LLM output is:
- **Sanitized**: Null bytes removed, line terminators normalized, lengths limited
- **Validated**: Regex checks for IDs, emails, phones, timestamps
- **Verified**: Message structure validated before adding to ledger

## Example

```python
from extractors.llm_extractor import LLMExtractor

extractor = LLMExtractor()

raw_data = """
Message from +1234567890 on 2024-01-01 12:00:00:
Hello! This is a test message.
"""

ledger = extractor.extract_all(raw_data)

# Results in:
# {
#   "message_id": "imessage:auto_123",
#   "platform": "imessage",
#   "timestamp": "2024-01-01T12:00:00",
#   "sender": {
#     "phone": "+1234567890",
#     "platform_id": "+1234567890"
#   },
#   "body": "Hello! This is a test message.",
#   ...
# }
```

## Fallback

If GPT4All is not installed, the extractor logs a warning and returns an empty ledger. Other local LLM backends (like llama-cpp-python) can be added as alternatives.

## Testing

Run tests:

```bash
python3 tests/test_llm_extractor.py
```

## Advantages

- **Robust**: Handles unexpected formats gracefully
- **Validated**: All output passes strict validation
- **Private**: No data leaves your machine
- **Flexible**: Works with various input formats

## Limitations

- Requires local LLM setup
- Slower than direct extraction
- Model quality affects accuracy
- GPU recommended for performance

