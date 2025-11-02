# JSON Schema Documentation

## Overview

This document defines the standardized JSON structure for all message extraction outputs. The schema is **Mutually Exclusive and Collectively Exhaustive (MECE)**, ensuring no data overlap and complete coverage.

## Top-Level Structure

### Unified Ledger Export (`unified_ledger.json`)

```json
{
  "total_messages": 160674,
  "platforms": ["imessage", "whatsapp", "gmail", "gcal"],
  "unique_contacts": 3576,
  "messages": [...]
}
```

**Field Definitions:**
- `total_messages` (integer, required): Total number of messages in ledger
- `platforms` (array of strings, required): List of source platforms
- `unique_contacts` (integer, required): Number of unique contacts
- `messages` (array, required): Chronologically sorted message objects

## Message Object

### Basic Structure

```json
{
  "message_id": "imessage:ABC123-DEF456",
  "platform": "imessage",
  "timestamp": "2024-01-01T12:00:00.123456",
  "timezone": null,
  "sender": {...},
  "recipients": [...],
  "participants": [...],
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
  "raw_data": {...}
}
```

### Field Definitions

#### Identifiers
- **`message_id`** (string, required, unique): Format `{platform}:{unique_id}`
  - Examples: `imessage:ABC123`, `gmail:msg-12345`, `whatsapp:msg-67890`
  - Regex: `^[a-z]+:[a-zA-Z0-9_-]+$`

- **`platform`** (string, required): Source platform
  - Valid values: `imessage`, `whatsapp`, `gmail`, `gcal`
  - Regex: `^(imessage|whatsapp|gmail|gcal)$`

#### Time
- **`timestamp`** (string, required): ISO 8601 timestamp
  - Format: `YYYY-MM-DDTHH:MM:SS.microseconds` or with timezone
  - Examples: `2024-01-01T12:00:00`, `2024-01-01T12:00:00.123456`, `2024-01-01T12:00:00+05:00`
  - Regex: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$`

- **`timezone`** (string or null): Timezone identifier
  - Examples: `America/New_York`, `UTC`, `+05:00`

#### People
- **`sender`** (Contact object, required): Who sent the message
- **`recipients`** (array of Contact objects, required): All recipients (to/cc/bcc)
- **`participants`** (array of Contact objects, required): All unique people involved

#### Content
- **`subject`** (string or null): Message subject (emails, calendar)
- **`body`** (string, required): Message content
  - **Never empty** - at minimum contains label like `[Tapback: Liked]` or `[Attachment]`
  - Max length: 100KB
  - Sanitized: null bytes removed

- **`attachments`** (array of strings): File references
  - Empty array if no attachments
  - Examples: `["photo.jpg", "document.pdf"]`

#### Metadata
- **`thread_id`** (string or null): Conversation thread identifier
- **`is_read`** (boolean or null): Read status
- **`is_starred`** (boolean or null): Starred/favorited status
- **`is_reply`** (boolean or null): Is this a reply?
- **`original_message_id`** (string or null): ID of replied-to message

#### Calendar-Specific
- **`event_start`** (string or null): ISO 8601 timestamp
- **`event_end`** (string or null): ISO 8601 timestamp
- **`event_location`** (string or null): Event location
- **`event_status`** (string or null): `confirmed`, `tentative`, `cancelled`

#### Platform-Specific
- **`raw_data`** (object, required): Platform-specific raw data
  - Structure varies by platform
  - Contains original database/API fields

## Contact Object

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "platform_id": "+1234567890",
  "platform": "imessage"
}
```

### Field Definitions
- **`name`** (string or null): Display name
- **`email`** (string or null): Email address
  - Regex: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
  - Validated if present

- **`phone`** (string or null): Phone number
  - Regex: `^\+?[\d\s\-()]+$`
  - Validated if present

- **`platform_id`** (string, required): Original platform identifier
- **`platform`** (string, required): Source platform

## Validation Rules

### MECE Principles

1. **Mutually Exclusive**: No field overlaps with another
2. **Collectively Exhaustive**: All possible message data is captured

### Validation Rules

1. All required fields must be present
2. All IDs must follow format regex patterns
3. All emails/phones must match regex if present
4. All timestamps must be valid ISO 8601
5. Body must never be empty
6. Message IDs must be unique
7. `total_messages` must match actual count
8. All strings are sanitized (null bytes removed, max lengths enforced)

## Platform-Specific Differences

### iMessage
- `body` special labels:
  - `[Tapback: Liked]`, `[Tapback: Disliked]`, `[Tapback: Emphasized]`, etc.
  - `[Tapback: 😂]` for custom emojis
  - `[Attachment]`, `[Apple Pay Payment]`, `[Sticker]`, `[App Share]`, `[Location]`

### WhatsApp
- `body` special labels:
  - `[Media]`, `[Location]`, `[Contact]`, `[Link]`

### Gmail
- `subject` always present
- `thread_id` corresponds to Gmail thread ID
- `body` contains email body

### Google Calendar
- `subject` is event title
- `event_start`/`event_end` always present
- `body` contains event description

## Examples

### Text Message
```json
{
  "message_id": "imessage:ABC123",
  "platform": "imessage",
  "timestamp": "2024-01-01T12:00:00",
  "timezone": null,
  "sender": {
    "name": null,
    "email": null,
    "phone": "+1234567890",
    "platform_id": "+1234567890",
    "platform": "imessage"
  },
  "recipients": [{
    "name": "Me",
    "email": null,
    "phone": null,
    "platform_id": "me",
    "platform": "imessage"
  }],
  "participants": [{
    "name": null,
    "email": null,
    "phone": "+1234567890",
    "platform_id": "+1234567890",
    "platform": "imessage"
  }, {
    "name": "Me",
    "email": null,
    "phone": null,
    "platform_id": "me",
    "platform": "imessage"
  }],
  "subject": null,
  "body": "Hello!",
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
  "raw_data": {
    "guid": "ABC123",
    "rowid": 12345,
    "is_from_me": 0,
    "cache_has_attachments": 0,
    "phone_email": "+1234567890"
  }
}
```

### Tapback/Reaction
```json
{
  "message_id": "imessage:TAP001",
  "platform": "imessage",
  "timestamp": "2024-01-01T12:05:00",
  "timezone": null,
  "sender": {
    "name": null,
    "email": null,
    "phone": "+1234567890",
    "platform_id": "+1234567890",
    "platform": "imessage"
  },
  "recipients": [{
    "name": "Me",
    "email": null,
    "phone": null,
    "platform_id": "me",
    "platform": "imessage"
  }],
  "participants": [{
    "name": null,
    "email": null,
    "phone": "+1234567890",
    "platform_id": "+1234567890",
    "platform": "imessage"
  }, {
    "name": "Me",
    "email": null,
    "phone": null,
    "platform_id": "me",
    "platform": "imessage"
  }],
  "subject": null,
  "body": "[Tapback: Liked]",
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
  "raw_data": {
    "guid": "TAP001",
    "rowid": 12346,
    "is_from_me": 0,
    "cache_has_attachments": 0,
    "phone_email": "+1234567890"
  }
}
```

### Calendar Event
```json
{
  "message_id": "gcal:EVT001",
  "platform": "gcal",
  "timestamp": "2024-01-01T10:00:00",
  "timezone": "America/New_York",
  "sender": {
    "name": "Organizer",
    "email": "organizer@example.com",
    "phone": null,
    "platform_id": "organizer@example.com",
    "platform": "gcal"
  },
  "recipients": [{
    "name": "Me",
    "email": "me@example.com",
    "phone": null,
    "platform_id": "me@example.com",
    "platform": "gcal"
  }],
  "participants": [{
    "name": "Organizer",
    "email": "organizer@example.com",
    "phone": null,
    "platform_id": "organizer@example.com",
    "platform": "gcal"
  }, {
    "name": "Me",
    "email": "me@example.com",
    "phone": null,
    "platform_id": "me@example.com",
    "platform": "gcal"
  }],
  "subject": "Team Meeting",
  "body": "Discussion of Q1 plans",
  "attachments": [],
  "thread_id": null,
  "is_read": null,
  "is_starred": null,
  "is_reply": null,
  "original_message_id": null,
  "event_start": "2024-01-01T10:00:00-05:00",
  "event_end": "2024-01-01T11:00:00-05:00",
  "event_location": "Conference Room A",
  "event_status": "confirmed",
  "raw_data": {
    "event_id": "EVT001",
    "calendar_id": "primary"
  }
}
```

## Data Quality Guarantees

1. **No empty bodies** - Every message has content or a label
2. **No null bytes** - All strings sanitized
3. **Consistent types** - All fields match expected types
4. **Valid IDs** - All IDs follow regex patterns
5. **Valid emails/phones** - Format-validated if present
6. **Valid timestamps** - All ISO 8601 compliant
7. **Unique messages** - No duplicate message IDs
8. **MECE structure** - No overlap, complete coverage

