# Database Entity Relationship Diagram

## Mermaid ERD

```mermaid
erDiagram
    contacts ||--o{ messages : sends
    contacts ||--o{ conversation_participants : "participates in"
    conversations ||--o{ messages : "contains"
    conversations ||--o{ conversation_participants : "has participants"
    messages ||--o{ messages : "replies to"
    messages ||--|| calendar_events : "may have"
    messages ||--o{ message_tags : "tagged with"
    
    contacts {
        int contact_id PK
        text display_name
        text email
        text phone
        text platform
        text platform_id
        timestamp first_seen
        timestamp last_seen
        int message_count
        boolean is_me
        boolean is_validated
    }
    
    conversations {
        int conversation_id PK
        text conversation_name
        text platform
        text thread_id
        timestamp first_message_at
        timestamp last_message_at
        int message_count
        boolean is_group
        int participant_count
        boolean is_important
        text category
    }
    
    messages {
        int message_id PK
        text platform
        text platform_message_id UK
        int conversation_id FK
        int sender_id FK
        timestamp timestamp
        text timezone
        text body
        text subject
        boolean is_read
        boolean is_starred
        boolean is_sent
        boolean is_deleted
        boolean is_reply
        int reply_to_message_id FK
        boolean has_attachment
        boolean is_tapback
        text tapback_type
        json raw_data
        timestamp created_at
        timestamp updated_at
    }
    
    conversation_participants {
        int participant_id PK
        int conversation_id FK
        int contact_id FK
        text role
        timestamp joined_at
        timestamp left_at
        int message_count
    }
    
    calendar_events {
        int event_id PK
        int message_id FK
        timestamp event_start
        timestamp event_end
        int event_duration_seconds
        text event_location
        text event_status
        boolean is_recurring
        text recurrence_pattern
    }
    
    message_tags {
        int tag_id PK
        int message_id FK
        text tag_name
        text tag_value
        timestamp created_at
    }
```

## Relationship Details

### Primary Relationships

1. **contacts** → **messages** (1:N)
   - One contact can send many messages
   - Foreign key: `messages.sender_id` → `contacts.contact_id`

2. **conversations** → **messages** (1:N)
   - One conversation contains many messages
   - Foreign key: `messages.conversation_id` → `conversations.conversation_id`

3. **conversations** ↔ **contacts** (M:N)
   - Many-to-many relationship via junction table
   - Junction table: `conversation_participants`
   - Foreign keys: 
     - `conversation_participants.conversation_id` → `conversations.conversation_id`
     - `conversation_participants.contact_id` → `contacts.contact_id`

4. **messages** → **messages** (self-referencing 1:N)
   - One message can have many replies
   - Foreign key: `messages.reply_to_message_id` → `messages.message_id`

5. **messages** → **calendar_events** (1:0..1)
   - One message may have one calendar event
   - Foreign key: `calendar_events.message_id` → `messages.message_id`

6. **messages** → **message_tags** (1:N)
   - One message can have many tags
   - Foreign key: `message_tags.message_id` → `messages.message_id`

## Key Design Patterns

### Normalization
- **No data duplication**: Contacts stored once, referenced by ID
- **Referential integrity**: Foreign keys ensure data consistency
- **Junction table**: Enables many-to-many relationships

### Performance
- **Indexes**: On all foreign keys and common query patterns
- **Views**: Pre-computed aggregations for common queries
- **Triggers**: Automatic maintenance of statistics

### Scalability
- **Platform agnostic**: Same schema for all platforms (iMessage, WhatsApp, etc.)
- **Extensible**: Easy to add new platforms or features
- **JSON fields**: Store platform-specific raw data

## Data Flow Example

```
iMessage Import:
  1. Create/Update CONTACTS (phone numbers, names)
  2. Create CONVERSATION (thread)
  3. Insert MESSAGES (link to conversation and sender)
  4. Auto-create CONVERSATION_PARTICIPANTS (via trigger)
  5. Auto-update timestamps and statistics (via triggers)

WhatsApp Import:
  1. Reuse existing CONTACTS (if phone matches)
  2. Create new CONVERSATION for WhatsApp chat
  3. Insert WhatsApp MESSAGES
  4. Cross-platform contact linking (same phone = same person)

Query Across Platforms:
  1. Use CONTACTS as join point
  2. Filter MESSAGES by platform
  3. Aggregate via VIEWS
  4. Return unified timeline
```

## Platform Support

Current platforms stored in database:
- ✅ **iMessage** (`platform = 'imessage'`)
- ✅ **WhatsApp** (`platform = 'whatsapp'`)
- 🔜 **Gmail** (`platform = 'gmail'`)
- 🔜 **Google Calendar** (`platform = 'gcal'`)

Each platform uses identical schema, differentiated only by the `platform` field.

## Views for Quick Access

1. **recent_conversations**: Sorted by last message, includes participant names
2. **contact_statistics**: Per-contact messaging stats and counts
3. **platform_summary**: High-level stats per platform

## Automatic Maintenance

Triggers handle:
- ✅ Timestamp updates on conversation last_message_at
- ✅ Message count aggregation
- ✅ Contact statistics (first_seen, last_seen, message_count)
- ✅ Group conversation detection (participant_count > 2)

## Supabase Compatibility

This schema is PostgreSQL-compatible and can be migrated to Supabase using the migration script in `database/supabase_migration.sql`.

Key differences in PostgreSQL:
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `TIMESTAMP` → `TIMESTAMPTZ` (timezone-aware)
- `JSON` → `JSONB` (binary JSON, faster queries)
- `GROUP_CONCAT` → `STRING_AGG`

