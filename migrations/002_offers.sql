-- Create supplier offers table for storing quote responses
CREATE TABLE IF NOT EXISTS supplier_offers (
  id SERIAL PRIMARY KEY,
  supplier_name TEXT,
  supplier_email TEXT,
  spec TEXT NOT NULL,
  price NUMERIC,
  currency TEXT,
  lead_time INTEGER,
  lead_time_unit TEXT,
  email_body TEXT,
  parsed_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index for querying offers by spec
CREATE INDEX IF NOT EXISTS idx_supplier_offers_spec ON supplier_offers(spec);

-- Index for querying offers by supplier
CREATE INDEX IF NOT EXISTS idx_supplier_offers_supplier ON supplier_offers(supplier_email); 