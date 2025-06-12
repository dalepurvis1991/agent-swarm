-- Create enum type for offer status
CREATE TYPE offer_status AS ENUM (
    'open',
    'countered',
    'final',
    'needs_user',
    'ordered'
);

-- Add new columns to offers table
ALTER TABLE offers
ADD COLUMN status offer_status DEFAULT 'open',
ADD COLUMN thread_id UUID DEFAULT gen_random_uuid(),
ADD COLUMN counter_price DECIMAL(10,2),
ADD COLUMN counter_round INTEGER DEFAULT 0,
ADD COLUMN last_counter_at TIMESTAMP WITH TIME ZONE;

-- Add index for faster lookups
CREATE INDEX idx_offers_status ON offers(status);
CREATE INDEX idx_offers_thread_id ON offers(thread_id);

-- Add trigger to update last_counter_at
CREATE OR REPLACE FUNCTION update_offer_counter_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'countered' THEN
        NEW.last_counter_at = CURRENT_TIMESTAMP;
        NEW.counter_round = COALESCE(OLD.counter_round, 0) + 1;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_offer_counter_timestamp
    BEFORE UPDATE ON offers
    FOR EACH ROW
    EXECUTE FUNCTION update_offer_counter_timestamp(); 