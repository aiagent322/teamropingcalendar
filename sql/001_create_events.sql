-- TeamRopingCalendar.com Events Table
-- Migration 001: Create events table
-- Preserves all fields from teamroping.ai events.json + new OCR pipeline columns

CREATE TABLE IF NOT EXISTS events (
  -- Primary key
  id TEXT PRIMARY KEY,

  -- Core event fields
  title TEXT NOT NULL,
  description TEXT,
  event_date DATE,
  end_date DATE,
  start_time TEXT,

  -- Venue fields
  venue TEXT,
  address TEXT,
  venue_city TEXT,
  venue_state TEXT,
  zip TEXT,
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,

  -- Classification
  category TEXT,
  event_type TEXT,
  is_series BOOLEAN DEFAULT FALSE,

  -- Entry / competition details
  entry_fee TEXT,
  runs TEXT,
  prize_money TEXT,
  rp INTEGER,

  -- Contact
  phone TEXT,
  email TEXT,
  website TEXT,

  -- Sparse / optional fields (from existing data)
  meta JSONB DEFAULT '{}'::jsonb,

  -- NEW: Flyer pipeline columns
  flyer_id TEXT,
  flyer_url TEXT,
  source TEXT DEFAULT 'manual' CHECK (source IN ('manual', 'ocr_auto', 'ocr_reviewed')),
  confidence DOUBLE PRECISION DEFAULT 1.0,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_events_event_date ON events (event_date);
CREATE INDEX idx_events_venue_city ON events (venue_city);
CREATE INDEX idx_events_venue_state ON events (venue_state);
CREATE INDEX idx_events_category ON events (category);
CREATE INDEX idx_events_source ON events (source);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_updated_at
  BEFORE UPDATE ON events
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at();

-- RLS: anon = read-only, service key = full access
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
  ON events FOR SELECT
  USING (true);

CREATE POLICY "Service key write access"
  ON events FOR ALL
  USING (auth.role() = 'service_role');
