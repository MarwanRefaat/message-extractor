-- Supabase/PostgreSQL Migration Script
-- Converts SQLite schema to PostgreSQL compatible schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. CONTACTS TABLE
CREATE TABLE contacts (
    contact_id SERIAL PRIMARY KEY,
    display_name TEXT,
    email TEXT,
    phone TEXT,
    platform TEXT NOT NULL,
    platform_id TEXT NOT NULL,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    is_me BOOLEAN DEFAULT FALSE,
    is_validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_platform_contact UNIQUE(platform, platform_id)
);

-- Indexes for contacts
CREATE INDEX idx_contacts_platform ON contacts(platform, platform_id);
CREATE INDEX idx_contacts_email ON contacts(email) WHERE email IS NOT NULL;
CREATE INDEX idx_contacts_phone ON contacts(phone) WHERE phone IS NOT NULL;

-- 2. CONVERSATIONS TABLE
CREATE TABLE conversations (
    conversation_id SERIAL PRIMARY KEY,
    conversation_name TEXT,
    platform TEXT NOT NULL,
    thread_id TEXT,
    first_message_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    is_group BOOLEAN DEFAULT FALSE,
    participant_count INTEGER DEFAULT 2,
    is_important BOOLEAN DEFAULT FALSE,
    category TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_platform ON conversations(platform, thread_id);
CREATE INDEX idx_conversations_last_message ON conversations(last_message_at DESC);

-- 3. MESSAGES TABLE
CREATE TABLE messages (
    message_id SERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_message_id TEXT NOT NULL,
    conversation_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timezone TEXT,
    body TEXT NOT NULL,
    subject TEXT,
    is_read BOOLEAN,
    is_starred BOOLEAN,
    is_sent BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_reply BOOLEAN DEFAULT FALSE,
    reply_to_message_id INTEGER,
    has_attachment BOOLEAN DEFAULT FALSE,
    is_tapback BOOLEAN DEFAULT FALSE,
    tapback_type TEXT,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_platform_message UNIQUE(platform, platform_message_id),
    CONSTRAINT fk_conversation FOREIGN KEY(conversation_id) 
        REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    CONSTRAINT fk_sender FOREIGN KEY(sender_id) 
        REFERENCES contacts(contact_id) ON DELETE CASCADE,
    CONSTRAINT fk_reply_to FOREIGN KEY(reply_to_message_id) 
        REFERENCES messages(message_id) ON DELETE SET NULL
);

-- Indexes for messages
CREATE INDEX idx_messages_timestamp ON messages(timestamp DESC);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, timestamp DESC);
CREATE INDEX idx_messages_sender ON messages(sender_id, timestamp DESC);
CREATE INDEX idx_messages_platform ON messages(platform, platform_message_id);
CREATE INDEX idx_messages_raw_data ON messages USING GIN (raw_data);

-- 4. CONVERSATION_PARTICIPANTS TABLE
CREATE TABLE conversation_participants (
    participant_id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMPTZ,
    left_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_conversation_contact UNIQUE(conversation_id, contact_id),
    CONSTRAINT fk_conversation_participant FOREIGN KEY(conversation_id) 
        REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    CONSTRAINT fk_contact_participant FOREIGN KEY(contact_id) 
        REFERENCES contacts(contact_id) ON DELETE CASCADE
);

CREATE INDEX idx_participants_contact ON conversation_participants(contact_id);
CREATE INDEX idx_participants_conversation ON conversation_participants(conversation_id);

-- 5. CALENDAR_EVENTS TABLE
CREATE TABLE calendar_events (
    event_id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    event_start TIMESTAMPTZ NOT NULL,
    event_end TIMESTAMPTZ,
    event_duration_seconds INTEGER,
    event_location TEXT,
    event_status TEXT,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_message_event UNIQUE(message_id),
    CONSTRAINT fk_message_event FOREIGN KEY(message_id) 
        REFERENCES messages(message_id) ON DELETE CASCADE
);

-- 6. MESSAGE_TAGS TABLE
CREATE TABLE message_tags (
    tag_id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    tag_value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_message_tag FOREIGN KEY(message_id) 
        REFERENCES messages(message_id) ON DELETE CASCADE
);

CREATE INDEX idx_tags_message ON message_tags(message_id);
CREATE INDEX idx_tags_name ON message_tags(tag_name);

-- TRIGGERS

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers to main tables
CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON contacts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update conversation timestamps
CREATE OR REPLACE FUNCTION update_conversation_timestamps()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations 
    SET 
        last_message_at = NEW.timestamp,
        message_count = message_count + 1,
        updated_at = NOW()
    WHERE conversation_id = NEW.conversation_id;
    
    UPDATE conversations 
    SET first_message_at = COALESCE(first_message_at, NEW.timestamp)
    WHERE conversation_id = NEW.conversation_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_conversation_timestamps_trigger
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION update_conversation_timestamps();

-- Update contact statistics
CREATE OR REPLACE FUNCTION update_contact_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE contacts 
    SET 
        last_seen = GREATEST(COALESCE(last_seen, '1970-01-01'::timestamptz), NEW.timestamp),
        first_seen = LEAST(COALESCE(first_seen, '9999-12-31'::timestamptz), NEW.timestamp),
        message_count = message_count + 1,
        updated_at = NOW()
    WHERE contact_id = NEW.sender_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_contact_stats_trigger
    AFTER INSERT ON messages
    FOR EACH ROW EXECUTE FUNCTION update_contact_stats();

-- Detect group conversations
CREATE OR REPLACE FUNCTION detect_group_conversation()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET 
        is_group = (
            SELECT COUNT(*) FROM conversation_participants 
            WHERE conversation_id = NEW.conversation_id
        ) > 2,
        participant_count = (
            SELECT COUNT(*) FROM conversation_participants 
            WHERE conversation_id = NEW.conversation_id
        ),
        updated_at = NOW()
    WHERE conversation_id = NEW.conversation_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER detect_group_conversation_trigger
    AFTER INSERT ON conversation_participants
    FOR EACH ROW EXECUTE FUNCTION detect_group_conversation();

-- VIEWS

-- Recent conversations view
CREATE OR REPLACE VIEW recent_conversations AS
SELECT 
    c.conversation_id,
    c.conversation_name,
    c.platform,
    c.last_message_at,
    c.message_count,
    c.is_group,
    c.participant_count,
    STRING_AGG(co.display_name, ', ' ORDER BY co.display_name) AS participant_names
FROM conversations c
LEFT JOIN conversation_participants cp ON c.conversation_id = cp.conversation_id
LEFT JOIN contacts co ON cp.contact_id = co.contact_id
WHERE co.is_me = FALSE OR co.is_me IS NULL
GROUP BY c.conversation_id, c.conversation_name, c.platform, 
         c.last_message_at, c.message_count, c.is_group, c.participant_count
ORDER BY c.last_message_at DESC NULLS LAST;

-- Contact statistics view
CREATE OR REPLACE VIEW contact_statistics AS
SELECT 
    co.contact_id,
    co.display_name,
    co.email,
    co.phone,
    co.platform,
    COUNT(DISTINCT m.message_id) AS total_messages,
    COUNT(DISTINCT CASE WHEN m.is_sent = TRUE THEN m.message_id END) AS sent_count,
    COUNT(DISTINCT CASE WHEN m.is_sent = FALSE THEN m.message_id END) AS received_count,
    COUNT(DISTINCT m.conversation_id) AS conversation_count,
    MIN(m.timestamp) AS first_message,
    MAX(m.timestamp) AS last_message
FROM contacts co
LEFT JOIN messages m ON co.contact_id = m.sender_id
GROUP BY co.contact_id, co.display_name, co.email, co.phone, co.platform
ORDER BY total_messages DESC;

-- Platform summary view
CREATE OR REPLACE VIEW platform_summary AS
SELECT 
    platform,
    COUNT(DISTINCT message_id) AS total_messages,
    COUNT(DISTINCT conversation_id) AS total_conversations,
    COUNT(DISTINCT sender_id) AS unique_contacts,
    MIN(timestamp) AS first_message,
    MAX(timestamp) AS last_message,
    AVG(LENGTH(body)) AS avg_message_length,
    SUM(CASE WHEN is_starred = TRUE THEN 1 ELSE 0 END) AS starred_count
FROM messages
GROUP BY platform;

-- ROW LEVEL SECURITY (RLS) - Optional for Supabase
-- Enable if you want to add user-based access control

-- ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE conversation_participants ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE message_tags ENABLE ROW LEVEL SECURITY;

-- Example RLS Policies (uncomment if needed)
-- CREATE POLICY "Users can only see their own contacts"
--     ON contacts FOR SELECT
--     USING (auth.uid()::text = user_id);

-- COMMENTS (Documentation)
COMMENT ON TABLE contacts IS 'All unique contacts across all platforms';
COMMENT ON TABLE conversations IS 'Message threads/conversations with metadata';
COMMENT ON TABLE messages IS 'Individual messages from all platforms';
COMMENT ON TABLE conversation_participants IS 'Many-to-many relationship between conversations and contacts';
COMMENT ON TABLE calendar_events IS 'Calendar-specific event data linked to messages';
COMMENT ON TABLE message_tags IS 'Custom categorization tags for messages';

-- Migration complete!

