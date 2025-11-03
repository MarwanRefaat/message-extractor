-- ============================================================================
-- ALIGN CALENDAR_EVENTS SCHEMA
-- ============================================================================
-- 
-- Run this in Supabase SQL Editor to add missing columns to calendar_events
-- These columns match the local SQLite schema
--
-- ============================================================================

-- Add missing columns to calendar_events table
ALTER TABLE calendar_events 
ADD COLUMN IF NOT EXISTS event_timezone TEXT,
ADD COLUMN IF NOT EXISTS calendar_name TEXT,
ADD COLUMN IF NOT EXISTS organizer_email TEXT,
ADD COLUMN IF NOT EXISTS attendee_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS has_video_conference BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS video_conference_url TEXT,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Add updated_at trigger
CREATE TRIGGER IF NOT EXISTS update_calendar_events_updated_at 
BEFORE UPDATE ON calendar_events 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMPLETE!
-- ============================================================================
-- 
-- After running this, re-run the upload script to migrate calendar data:
-- python scripts/upload_to_supabase.py
--

