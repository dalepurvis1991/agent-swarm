-- Migration: RFQ Sessions for Specification Clarification
-- Creates table to track user specification clarification sessions

CREATE TABLE rfq_sessions (
    id SERIAL PRIMARY KEY,
    spec_json JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add index on status for faster queries
CREATE INDEX idx_rfq_sessions_status ON rfq_sessions(status);

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_rfq_sessions_updated_at
    BEFORE UPDATE ON rfq_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 