#!/usr/bin/env python3
"""
Migrate events.json from teamroping.ai into Supabase events table.
Reads a COPY of events.json — does NOT touch teamroping.ai.

Usage:
  export SUPABASE_URL=https://YOUR_PROJECT.supabase.co
  export SUPABASE_SERVICE_KEY=your_service_key
  python3 migrate_events.py
"""

import json
import os
import sys
import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables")
    sys.exit(1)

# Core columns that map directly to typed table columns
CORE_COLUMNS = {
    "id", "title", "description", "event_date", "end_date", "start_time",
    "venue", "address", "venue_city", "venue_state", "zip", "lat", "lng",
    "category", "event_type", "is_series", "entry_fee", "runs", "prize_money",
    "rp", "phone", "email", "website"
}

def load_events(path="events.json"):
    with open(path, "r") as f:
        return json.load(f)

def transform_event(raw):
    """Split raw event into core columns + meta JSONB for sparse fields."""
    row = {}
    meta = {}

    for key, val in raw.items():
        if key in CORE_COLUMNS:
            row[key] = val
        else:
            # Sparse field -> meta JSONB
            if val is not None and val != "" and val != [] and val != {}:
                meta[key] = val

    row["meta"] = json.dumps(meta) if meta else "{}"
    row["source"] = "manual"
    row["confidence"] = 1.0
    row["flyer_id"] = None
    row["flyer_url"] = None

    return row

def insert_batch(rows, batch_size=50):
    """Insert rows into Supabase via REST API in batches."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    url = f"{SUPABASE_URL}/rest/v1/events"

    total = len(rows)
    inserted = 0
    errors = 0

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        resp = requests.post(url, headers=headers, json=batch)

        if resp.status_code in (200, 201):
            inserted += len(batch)
            print(f"  Inserted {inserted}/{total}")
        else:
            errors += len(batch)
            print(f"  ERROR batch {i}-{i+len(batch)}: {resp.status_code} {resp.text[:200]}")

    return inserted, errors

def main():
    events_path = os.path.join(os.path.dirname(__file__), "..", "data", "events.json")
    if not os.path.exists(events_path):
        events_path = "events.json"
    if not os.path.exists(events_path):
        print(f"ERROR: events.json not found at {events_path}")
        sys.exit(1)

    raw_events = load_events(events_path)
    print(f"Loaded {len(raw_events)} events from {events_path}")

    # Check for duplicates
    ids = [e.get("id", "") for e in raw_events]
    dupes = len(ids) - len(set(ids))
    if dupes:
        print(f"WARNING: {dupes} duplicate IDs found")

    rows = [transform_event(e) for e in raw_events]
    print(f"Transformed {len(rows)} events ({len(CORE_COLUMNS)} core columns + meta JSONB)")

    inserted, errors = insert_batch(rows)
    print(f"\nDone: {inserted} inserted, {errors} errors")

if __name__ == "__main__":
    main()
