# SQL Database Schema for Chat Messages

## Overview

A normalized relational database schema for storing all chat messages from multiple platforms (iMessage, WhatsApp, Gmail, Google Calendar, etc.).

## Database Design Philosophy

- **Normalized**: Avoid data duplication, maintain referential integrity
- **Scalable**: Handle millions of messages efficiently with proper indexing
- **Query-Optimized**: Support fast searches, filters, and analytics
- **Platform-Agnostic**: Unified structure for all message platforms
- **Clean**: Well-organized, documented, and type-safe

## Schema Structure

### Tables

1. **contacts** - All unique contacts across all platforms
2. **conversations** - Conversation/thread groupings
3. **messages** - Individual messages
4. **participants** - Many-to-many relationship between contacts and conversations
5. **message_recipients** - Many-to-many relationship between messages and recipients
6. **calendar_events** - Calendar-specific event data (nullable)
7. **message_tags** - Custom tags/categories for messages

## Schema Details

### 1. contacts
Stores all unique contacts across all platforms.

```sql
CREATE TABLE contacts (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity fields (at least one must be non-null)
    display_name TEXT,           -- Human-readable name
    email TEXT,                   -- Email address (unique if present)
    phone TEXT,                   -- Phone number (unique if present)
    
    -- Platform identifiers
    platform TEXT NOT NULL,       -- Source platform: imessage, whatsapp, gmail, gcal
    platform_id TEXT NOT NULL,    -- Original platform identifier
    
    -- Metadata
    first_seen TIMESTAMP,         -- First time this contact appears
    last_seen TIMESTAMP,          -- Last time this contact appears
    message_count INTEGER DEFAULT 0,  -- Total messages with this contact
    
    -- Data quality
    is_me BOOLEAN DEFAULT 0,      -- Is this the user themselves?
    is_validated BOOLEAN DEFAULT 0,  -- Has contact info been validated?
    
    -- Composite unique constraints
    UNIQUE(platform, platform_id),
    UNIQUE(email) WHERE email IS NOT NULL,
    UNIQUE(phone) WHERE phone IS NOT NULL,
    
    -- Indexes for fast lookups
    INDEX idx_contacts_email ON contacts(email) WHERE email IS NOT NULL,
    INDEX idx_contacts_phone ON contacts(phone) WHERE phone IS NOT NULL,
    INDEX idx_contacts_platform ON contacts(platform, platform_id),
    INDEX idx_contacts_display_name ON contacts(display_name)
);
```

### 2. conversations
Groups related messages into threads/conversations.

```sql
CREATE TABLE conversations (
    conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identity
    conversation_name TEXT,       -- Display name for conversation
    
    -- Platform info
    platform TEXT NOT NULL,       -- Source platform
    thread_id TEXT,               -- Platform's thread identifier
    
    -- Conversation metadata
    first_message_at TIMESTAMP,   -- First message timestamp
    last_message_at TIMESTAMP,    -- Last message timestamp
    message_count INTEGER DEFAULT 0,  -- Total messages in conversation
    
    -- Group chat info
    is_group BOOLEAN DEFAULT 0,   -- Is this a group chat?
    participant_count INTEGER DEFAULT 2,  -- Number of participants
    
    -- User categorization
    is_important BOOLEAN DEFAULT 0,  -- User-tagged as important
    category TEXT,                -- User-defined category
    
    -- Indexes
    INDEX idx_conversations_platform ON conversations(platform, thread_id),
    INDEX idx_conversations_last_message ON conversations(last_message_at DESC),
    INDEX idx_conversations_important ON conversations(is_important) WHERE is_important = 1
);
```

### 3. messages
Core table storing all individual messages.

```sql
CREATE TABLE messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Unique identifiers
    platform TEXT NOT NULL,       -- Source platform
    platform_message_id TEXT NOT NULL,  -- Original platform message ID
    UNIQUE(platform, platform_message_id),
    
    -- Relationship to conversation
    conversation_id INTEGER NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id),
    
    -- Sender
    sender_id INTEGER NOT NULL,
    FOREIGN KEY(sender_id) REFERENCES contacts(contact_id),
    
    -- Time
    timestamp TIMESTAMP NOT NULL, -- Message timestamp
    timezone TEXT,                -- Timezone info
    
    -- Content
    body TEXT NOT NULL,           -- Message content (never empty)
    subject TEXT,                 -- Subject line (for emails/events)
    
    -- Message properties
    is_read BOOLEAN,              -- Read status
    is_starred BOOLEAN,           -- Starred/favorited
    is_sent BOOLEAN DEFAULT 1,    -- Sent by user (vs received)
    is_deleted BOOLEAN DEFAULT 0, -- Soft delete flag
    is_reply BOOLEAN DEFAULT 0,   -- Is this a reply?
    reply_to_message_id INTEGER,  -- Message being replied to
    FOREIGN KEY(reply_to_message_id) REFERENCES messages(message_id),
    
    -- Message types
    has_attachment BOOLEAN DEFAULT 0,     -- Has attachments
    is_tapback BOOLEAN DEFAULT 0,         -- Is a tapback/reaction
    tapback_type TEXT,                    -- Type of tapback (like, dislike, etc.)
    
    -- Platform-specific JSON
    raw_data JSON,                -- Platform-specific fields
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for common queries
    INDEX idx_messages_timestamp ON messages(timestamp DESC),
    INDEX idx_messages_conversation ON messages(conversation_id, timestamp DESC),
    INDEX idx_messages_sender ON messages(sender_id, timestamp DESC),
    INDEX idx_messages_platform ON messages(platform, platform_message_id),
    INDEX idx_messages_reply_to ON messages(reply_to_message_id),
    FULLTEXT INDEX idx_messages_body_fulltext ON messages(body),
    INDEX idx_messages_read_starred ON messages(is_read, is_starred),
    INDEX idx_messages_date_range ON messages(timestamp, platform)
);
```

### 4. conversation_participants
Many-to-many: which contacts are in which conversations.

```sql
CREATE TABLE conversation_participants (
    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    conversation_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    
    -- Role in conversation
    role TEXT DEFAULT 'member',   -- member, admin, creator
    
    -- Timestamps
    joined_at TIMESTAMP,          -- When contact joined conversation
    left_at TIMESTAMP,            -- When contact left (for group chats)
    
    -- Stats for this conversation
    message_count INTEGER DEFAULT 0,  -- Messages from this contact in this conversation
    
    -- Constraints
    UNIQUE(conversation_id, contact_id),
    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id),
    FOREIGN KEY(contact_id) REFERENCES contacts(contact_id),
    
    INDEX idx_participants_contact ON conversation_participants(contact_id),
    INDEX idx_participants_conversation ON conversation_participants(conversation_id)
);
```

### 5. calendar_events
Calendar-specific event data (only for calendar platforms).

```sql
CREATE TABLE calendar_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    message_id INTEGER NOT NULL,
    FOREIGN KEY(message_id) REFERENCES messages(message_id),
    
    -- Event timing
    event_start TIMESTAMP NOT NULL,
    event_end TIMESTAMP,
    event_duration_seconds INTEGER,  -- Calculated duration
    
    -- Event details
    event_location TEXT,           -- Location
    event_status TEXT,             -- confirmed, tentative, cancelled
    
    -- Recurrence
    is_recurring BOOLEAN DEFAULT 0,
    recurrence_pattern TEXT,       -- RRULE string
    
    -- Constraints
    UNIQUE(message_id),
    
    INDEX idx_events_start ON calendar_events(event_start),
    INDEX idx_events_status ON calendar_events(event_status),
    INDEX idx_events_location ON calendar_events(event_location) WHERE event_location IS NOT NULL
);
```

### 6. message_tags
Custom tags for organizing messages.

```sql
CREATE TABLE message_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    message_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    tag_value TEXT,               -- Optional tag value
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(message_id) REFERENCES messages(message_id),
    
    INDEX idx_tags_message ON message_tags(message_id),
    INDEX idx_tags_name ON message_tags(tag_name)
);
```

## Views for Common Queries

### 1. Recent Conversations View
```sql
CREATE VIEW recent_conversations AS
SELECT 
    c.conversation_id,
    c.conversation_name,
    c.platform,
    c.last_message_at,
    c.message_count,
    c.is_group,
    GROUP_CONCAT(co.display_name) AS participant_names,
    (
        SELECT body 
        FROM messages m 
        WHERE m.conversation_id = c.conversation_id 
        ORDER BY m.timestamp DESC 
        LIMIT 1
    ) AS last_message_preview
FROM conversations c
LEFT JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
LEFT JOIN contacts co ON cp.contact_id = co.contact_id
WHERE co.is_me = 0
GROUP BY c.conversation_id
ORDER BY c.last_message_at DESC;
```

### 2. Contact Statistics View
```sql
CREATE VIEW contact_statistics AS
SELECT 
    co.contact_id,
    co.display_name,
    co.email,
    co.phone,
    co.platform,
    COUNT(DISTINCT m.message_id) AS total_messages,
    COUNT(DISTINCT CASE WHEN m.is_sent = 1 THEN m.message_id END) AS sent_count,
    COUNT(DISTINCT CASE WHEN m.is_sent = 0 THEN m.message_id END) AS received_count,
    COUNT(DISTINCT m.conversation_id) AS conversation_count,
    MIN(m.timestamp) AS first_message,
    MAX(m.timestamp) AS last_message
FROM contacts co
LEFT JOIN messages m ON co.contact_id = m.sender_id
GROUP BY co.contact_id
ORDER BY total_messages DESC;
```

### 3. Platform Summary View
```sql
CREATE VIEW platform_summary AS
SELECT 
    platform,
    COUNT(DISTINCT message_id) AS total_messages,
    COUNT(DISTINCT conversation_id) AS total_conversations,
    COUNT(DISTINCT sender_id) AS unique_contacts,
    MIN(timestamp) AS first_message,
    MAX(timestamp) AS last_message,
    AVG(LENGTH(body)) AS avg_message_length,
    SUM(CASE WHEN is_starred = 1 THEN 1 ELSE 0 END) AS starred_count
FROM messages
GROUP BY platform;
```

## Triggers for Data Integrity

### 1. Update Conversation Timestamps
```sql
CREATE TRIGGER update_conversation_timestamps
AFTER INSERT ON messages
BEGIN
    UPDATE conversations 
    SET 
        last_message_at = NEW.timestamp,
        message_count = message_count + 1
    WHERE conversation_id = NEW.conversation_id;
    
    UPDATE conversations 
    SET first_message_at = COALESCE(first_message_at, NEW.timestamp)
    WHERE conversation_id = NEW.conversation_id;
END;
```

### 2. Update Contact Statistics
```sql
CREATE TRIGGER update_contact_stats
AFTER INSERT ON messages
BEGIN
    UPDATE contacts 
    SET 
        last_seen = MAX(COALESCE(last_seen, '1970-01-01'), NEW.timestamp),
        first_seen = MIN(COALESCE(first_seen, '9999-12-31'), NEW.timestamp),
        message_count = message_count + 1
    WHERE contact_id = NEW.sender_id;
END;
```

### 3. Auto-detect Group Conversations
```sql
CREATE TRIGGER detect_group_conversation
AFTER INSERT ON conversation_participants
BEGIN
    UPDATE conversations
    SET 
        is_group = (SELECT COUNT(*) FROM conversation_participants WHERE conversation_id = NEW.conversation_id) > 2,
        participant_count = (SELECT COUNT(*) FROM conversation_participants WHERE conversation_id = NEW.conversation_id)
    WHERE conversation_id = NEW.conversation_id;
END;
```

## Indexing Strategy

### Primary Indexes
- All PRIMARY KEYs and FOREIGN KEYs are automatically indexed in SQLite
- Composite indexes on frequently queried combinations

### Full-Text Search
- SQLite FTS5 for message body search
- Enables fast full-text queries like "SELECT * FROM messages WHERE body MATCH 'keyword'"

### Performance Considerations
- Use covering indexes for common SELECT patterns
- Index on timestamp DESC for chronological queries
- Partial indexes for filtered queries (WHERE clause predicates)
- Consider partitioning by date if dataset is very large (>100M messages)

## Data Integrity Rules

1. **Message body**: Never empty (enforced by NOT NULL)
2. **Contacts**: At least one identifier (email, phone, or platform_id)
3. **Conversations**: Must have at least 2 participants
4. **Timestamps**: ISO 8601 format, UTC preferred
5. **Platform consistency**: All references match platform type
6. **Cascade deletes**: Deleting a conversation should handle dependencies appropriately

## Migration Notes

- Use schema versioning for future changes
- Provide migration scripts for each schema version
- Support both incremental updates and full reimport
- Handle duplicate detection and resolution
- Preserve soft-deleted records with is_deleted flag

## Example Queries

### Find all messages with a specific contact
```sql
SELECT m.*, c.display_name, c.platform
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
WHERE c.phone = '+16503873944'
   OR c.email = 'contact@example.com'
ORDER BY m.timestamp DESC
LIMIT 100;
```

### Find most active conversations
```sql
SELECT 
    conv.conversation_name,
    conv.message_count,
    conv.last_message_at,
    GROUP_CONCAT(co.display_name, ', ') AS participants
FROM recent_conversations conv
JOIN conversation_participants cp ON conv.conversation_id = cp.conversation_id
JOIN contacts co ON cp.contact_id = co.contact_id
WHERE co.is_me = 0
GROUP BY conv.conversation_id
ORDER BY conv.message_count DESC
LIMIT 20;
```

### Search messages by content
```sql
SELECT 
    m.timestamp,
    c.display_name,
    SUBSTR(m.body, 1, 100) AS preview,
    m.conversation_id
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
WHERE m.body LIKE '%keyword%'
ORDER BY m.timestamp DESC
LIMIT 50;
```

### Analytics: Messages per platform over time
```sql
SELECT 
    platform,
    DATE(timestamp) AS date,
    COUNT(*) AS message_count
FROM messages
GROUP BY platform, DATE(timestamp)
ORDER BY date DESC, platform;
```

### Find unread messages
```sql
SELECT 
    m.message_id,
    m.timestamp,
    c.display_name,
    conv.conversation_name,
    SUBSTR(m.body, 1, 200) AS preview
FROM messages m
JOIN contacts c ON m.sender_id = c.contact_id
JOIN conversations conv ON m.conversation_id = conv.conversation_id
WHERE m.is_read = 0 OR m.is_read IS NULL
ORDER BY m.timestamp DESC;
```

## Next Steps

1. Create Python script to generate SQLite database with this schema
2. Build HTML parser for iMessage exports
3. Implement LLM extraction for intelligent message parsing
4. Import data with proper validation and deduplication
5. Create reporting and analytics tools

