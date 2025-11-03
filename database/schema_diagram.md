# Database Schema Diagram

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CONTACTS                                       │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ contact_id (PK)             INTEGER PRIMARY KEY                   │    │
│  │ display_name                TEXT                                  │    │
│  │ email                        TEXT                                  │    │
│  │ phone                        TEXT                                  │    │
│  │ platform                     TEXT NOT NULL                         │    │
│  │ platform_id                  TEXT NOT NULL                         │    │
│  │ first_seen                   TIMESTAMP                             │    │
│  │ last_seen                    TIMESTAMP                             │    │
│  │ message_count                INTEGER DEFAULT 0                     │    │
│  │ is_me                        BOOLEAN DEFAULT 0                     │    │
│  │ is_validated                 BOOLEAN DEFAULT 0                     │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│  UNIQUE(platform, platform_id)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ sender_id
                                        │
         ┌──────────────────────────────┴──────────────────────────────────┐
         │                                                                  │
         │                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MESSAGES                                       │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ message_id (PK)             INTEGER PRIMARY KEY                   │    │
│  │ platform                     TEXT NOT NULL                         │    │
│  │ platform_message_id          TEXT NOT NULL                         │    │
│  │ conversation_id (FK)         INTEGER NOT NULL                      │    │
│  │ sender_id (FK)               INTEGER NOT NULL                      │    │
│  │ timestamp                    TIMESTAMP NOT NULL                    │    │
│  │ timezone                     TEXT                                  │    │
│  │ body                         TEXT NOT NULL                         │    │
│  │ subject                      TEXT                                  │    │
│  │ is_read                      BOOLEAN                               │    │
│  │ is_starred                   BOOLEAN                               │    │
│  │ is_sent                      BOOLEAN DEFAULT 1                     │    │
│  │ is_deleted                   BOOLEAN DEFAULT 0                     │    │
│  │ is_reply                     BOOLEAN DEFAULT 0                     │    │
│  │ reply_to_message_id (FK)     INTEGER                              │    │
│  │ has_attachment               BOOLEAN DEFAULT 0                     │    │
│  │ is_tapback                   BOOLEAN DEFAULT 0                     │    │
│  │ tapback_type                 TEXT                                  │    │
│  │ raw_data                     JSON                                  │    │
│  │ created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP   │    │
│  │ updated_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP   │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│  UNIQUE(platform, platform_message_id)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
         │                          │                          │
         │ conversation_id          │ reply_to_message_id      │ message_id
         │                          │                          │
         ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CONVERSATIONS                                      │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ conversation_id (PK)         INTEGER PRIMARY KEY                   │    │
│  │ conversation_name            TEXT                                  │    │
│  │ platform                     TEXT NOT NULL                         │    │
│  │ thread_id                    TEXT                                  │    │
│  │ first_message_at             TIMESTAMP                             │    │
│  │ last_message_at              TIMESTAMP                             │    │
│  │ message_count                INTEGER DEFAULT 0                     │    │
│  │ is_group                     BOOLEAN DEFAULT 0                     │    │
│  │ participant_count            INTEGER DEFAULT 2                     │    │
│  │ is_important                 BOOLEAN DEFAULT 0                     │    │
│  │ category                     TEXT                                  │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ conversation_id
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONVERSATION_PARTICIPANTS                               │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ participant_id (PK)          INTEGER PRIMARY KEY                   │    │
│  │ conversation_id (FK)         INTEGER NOT NULL                      │    │
│  │ contact_id (FK)              INTEGER NOT NULL                      │    │
│  │ role                         TEXT DEFAULT 'member'                 │    │
│  │ joined_at                    TIMESTAMP                             │    │
│  │ left_at                      TIMESTAMP                             │    │
│  │ message_count                INTEGER DEFAULT 0                     │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│  UNIQUE(conversation_id, contact_id)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ contact_id
                                        │
                                        ▼
                            (back to CONTACTS table)
```

## Extended Tables

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CALENDAR_EVENTS                                    │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ event_id (PK)                INTEGER PRIMARY KEY                   │    │
│  │ message_id (FK)              INTEGER NOT NULL                      │    │
│  │ event_start                  TIMESTAMP NOT NULL                    │    │
│  │ event_end                    TIMESTAMP                             │    │
│  │ event_duration_seconds       INTEGER                               │    │
│  │ event_location               TEXT                                  │    │
│  │ event_status                 TEXT                                  │    │
│  │ is_recurring                 BOOLEAN DEFAULT 0                     │    │
│  │ recurrence_pattern           TEXT                                  │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│  UNIQUE(message_id)                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ message_id
         │
         ▼
    MESSAGES table

┌─────────────────────────────────────────────────────────────────────────────┐
│                            MESSAGE_TAGS                                     │
│  ┌───────────────────────────────────────────────────────────────────┐    │
│  │ tag_id (PK)                  INTEGER PRIMARY KEY                   │    │
│  │ message_id (FK)              INTEGER NOT NULL                      │    │
│  │ tag_name                     TEXT NOT NULL                         │    │
│  │ tag_value                    TEXT                                  │    │
│  │ created_at                   TIMESTAMP DEFAULT CURRENT_TIMESTAMP   │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ message_id
         │
         ▼
    MESSAGES table
```

## Relationship Summary

### One-to-Many Relationships

1. **Contact → Messages**: One contact can send many messages (via `sender_id`)
2. **Conversation → Messages**: One conversation contains many messages
3. **Message → Replies**: One message can have many replies (self-referencing via `reply_to_message_id`)
4. **Conversation → Participants**: One conversation has many participants (via junction table)
5. **Contact → Participations**: One contact can participate in many conversations (via junction table)
6. **Message → Calendar Events**: One message can have one calendar event
7. **Message → Tags**: One message can have many tags

### Junction Table

**CONVERSATION_PARTICIPANTS** is a many-to-many relationship table connecting:
- Conversations ↔ Contacts

This allows:
- Multiple contacts per conversation (group chats)
- Multiple conversations per contact

## Indexes

### Contacts
- `idx_contacts_platform` on (platform, platform_id)
- `idx_contacts_email` on email WHERE email IS NOT NULL
- `idx_contacts_phone` on phone WHERE phone IS NOT NULL

### Conversations
- `idx_conversations_platform` on (platform, thread_id)
- `idx_conversations_last_message` on last_message_at DESC

### Messages
- `idx_messages_timestamp` on timestamp DESC
- `idx_messages_conversation` on (conversation_id, timestamp DESC)
- `idx_messages_sender` on (sender_id, timestamp DESC)
- `idx_messages_platform` on (platform, platform_message_id)

### Participants
- `idx_participants_contact` on contact_id
- `idx_participants_conversation` on conversation_id

## Views

### recent_conversations
- Shows most active conversations
- Includes participant names
- Sorted by last message timestamp

### contact_statistics
- Per-contact messaging statistics
- Sent/received counts
- Conversation counts

### platform_summary
- High-level stats per platform
- Message counts, conversation counts
- First/last message dates
- Average message length
- Starred message counts

## Triggers

### update_conversation_timestamps
- Automatically updates `last_message_at` when messages are inserted
- Updates `message_count` counter
- Sets `first_message_at` on first message

### update_contact_stats
- Updates contact statistics when messages are inserted
- Tracks `last_seen`, `first_seen`
- Updates `message_count` counter

### detect_group_conversation
- Detects group conversations based on participant count
- Updates `is_group` flag
- Updates `participant_count` counter

## Data Flow Example

```
1. Import iMessage
   → Create/Update CONTACTS
   → Create CONVERSATION
   → Insert MESSAGE
   → Auto-create CONVERSATION_PARTICIPANTS (via trigger)
   → Auto-update timestamps and counts (via triggers)

2. Import WhatsApp
   → Reuse existing CONTACTS (if phone matches)
   → Create new CONVERSATION for WhatsApp chat
   → Insert WhatsApp MESSAGES
   → Link to existing contacts where possible

3. Query across platforms
   → Use CONTACTS as join point
   → Query MESSAGES filtered by platform
   → Use CONVERSATIONS to group related messages
   → Use VIEWS for aggregated statistics
```

## Platform Support

Current platforms:
- ✅ iMessage
- ✅ WhatsApp
- 🔜 Gmail (in progress)
- 🔜 Google Calendar (in progress)

Each platform uses the same unified schema, differentiated by the `platform` field.

## Normalization Benefits

✅ **No Data Duplication**: Contacts stored once, referenced by ID  
✅ **Referential Integrity**: Foreign keys ensure data consistency  
✅ **Efficient Queries**: Indexes on all common access patterns  
✅ **Cross-Platform Queries**: Easy to query across platforms  
✅ **Automatic Maintenance**: Triggers keep statistics current  
✅ **Scalable**: Schema handles millions of messages efficiently  

