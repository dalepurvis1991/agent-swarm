-- Migration: RFQ Sessions for Specification Clarification
-- Creates table to track user specification clarification sessions

CREATE TABLE IF NOT EXISTS rfq_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    original_spec TEXT NOT NULL,
    spec_json JSONB,
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'complete', 'abandoned')),
    messages JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_rfq_sessions_session_id ON rfq_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_rfq_sessions_status ON rfq_sessions(status);
CREATE INDEX IF NOT EXISTS idx_rfq_sessions_created_at ON rfq_sessions(created_at);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_rfq_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_rfq_sessions_updated_at
    BEFORE UPDATE ON rfq_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_rfq_sessions_updated_at(); 