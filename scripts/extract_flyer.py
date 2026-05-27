#!/usr/bin/env python3
"""
OCR flyer extraction via Claude API.
Sends flyer image to Claude Sonnet, returns structured JSON with event data.
Only extracts what is literally on the flyer — no fabrication.

Usage:
  export ANTHROPIC_API_KEY=your_key
  export SUPABASE_URL=https://YOUR_PROJECT.supabase.co
  export SUPABASE_SERVICE_KEY=your_service_key
  python3 extract_flyer.py /path/to/flyer.jpg
  python3 extract_flyer.py /path/to/flyers/   # batch mode
"""

import anthropic
import base64
import json
import os
import sys
import hashlib
import requests
from pathlib import Path

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

EXTRACTION_PROMPT = """You are a data extraction tool for team roping event flyers. Extract ONLY information that is literally visible on the flyer. If a field is not on the flyer, return null. NEVER guess, infer, or fabricate any data.

Return valid JSON with exactly these fields:

{
  "title": "Event name exactly as shown on flyer",
  "event_date": "YYYY-MM-DD or null if ambiguous/missing year",
  "end_date": "YYYY-MM-DD or null (same as event_date if single day)",
  "start_time": "Exact time text from flyer (e.g. 'Books open 9 AM, Rope at 10 AM')",
  "venue": "Venue/arena name or null",
  "address": "Street address or null",
  "venue_city": "City or null",
  "venue_state": "2-letter state code or null",
  "zip": "Zip code or null",
  "category": "Team Roping",
  "event_type": "Jackpot|Series|Memorial|Saddle Roping|Open|Practice|Other",
  "entry_fee": "Fee text exactly as shown (e.g. '$150/man, enter 3x')",
  "runs": "Format text (e.g. 'Pick 1 Draw 2, 3-steer, 4.5 cap')",
  "prize_money": "Prize text exactly as shown or null",
  "phone": "Phone number(s) or null",
  "email": "Email or null",
  "website": "Website or null",
  "is_series": true/false,
  "roping_divisions": "Brief summary of all divisions/numbers on the flyer",
  "notes": "Any other important text (producer name, cattle provider, special rules)",
  "confidence": 0.0-1.0,
  "date_ambiguous": true/false,
  "date_ambiguity_note": "Explain if date/year is unclear or day-of-week doesn't match"
}

CRITICAL RULES:
- Extract ONLY literal text from the flyer
- If the year is not shown, check if the day-of-week matches 2025 or 2026 and note which
- If you cannot determine the year with certainty, set date_ambiguous to true
- Never generate descriptions or embellish — just extract the raw data
- confidence should reflect how clearly you could read the flyer (1.0 = crystal clear)
- Return ONLY the JSON object, no other text"""

def get_media_type(path):
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }.get(ext, "image/jpeg")

def extract_flyer(image_path):
    """Send flyer image to Claude API and extract structured data."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    media_type = get_media_type(image_path)

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": EXTRACTION_PROMPT
                }
            ]
        }]
    )

    raw_text = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

    return json.loads(raw_text)

def generate_event_id(data):
    """Generate a slug-based event ID from extracted data."""
    title = (data.get("title") or "unknown").lower()
    date = data.get("event_date") or "nodate"
    slug = "".join(c if c.isalnum() or c == "-" else "-" for c in title)
    slug = "-".join(filter(None, slug.split("-")))[:60]
    return f"{slug}-{date.replace('-', '')}"

def generate_flyer_id(image_path):
    """Generate a unique flyer ID from file hash."""
    with open(image_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]

def insert_event(data, flyer_id, flyer_url=None):
    """Insert extracted event into Supabase."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    # Build row from extraction
    row = {
        "id": generate_event_id(data),
        "title": data.get("title"),
        "description": None,  # No fabricated descriptions
        "event_date": data.get("event_date"),
        "end_date": data.get("end_date") or data.get("event_date"),
        "start_time": data.get("start_time"),
        "venue": data.get("venue"),
        "address": data.get("address"),
        "venue_city": data.get("venue_city"),
        "venue_state": data.get("venue_state"),
        "zip": data.get("zip"),
        "category": data.get("category", "Team Roping"),
        "event_type": data.get("event_type"),
        "entry_fee": data.get("entry_fee"),
        "runs": data.get("runs"),
        "prize_money": data.get("prize_money"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "website": data.get("website"),
        "is_series": data.get("is_series", False),
        "meta": json.dumps({
            k: v for k, v in {
                "roping_divisions": data.get("roping_divisions"),
                "notes": data.get("notes"),
                "date_ambiguous": data.get("date_ambiguous"),
                "date_ambiguity_note": data.get("date_ambiguity_note"),
                "ocr_raw": data
            }.items() if v
        }),
        "flyer_id": flyer_id,
        "flyer_url": flyer_url,
        "source": "ocr_auto",
        "confidence": data.get("confidence", 0.9)
    }

    url = f"{SUPABASE_URL}/rest/v1/events"
    resp = requests.post(url, headers=headers, json=row)

    if resp.status_code in (200, 201):
        return True, row["id"]
    else:
        return False, resp.text[:200]

def process_single(image_path):
    """Process a single flyer image."""
    print(f"Processing: {image_path}")
    flyer_id = generate_flyer_id(image_path)

    data = extract_flyer(image_path)
    print(f"  Extracted: {data.get('title', 'UNKNOWN')}")
    print(f"  Date: {data.get('event_date', 'UNKNOWN')} | City: {data.get('venue_city', 'UNKNOWN')}")
    print(f"  Confidence: {data.get('confidence', '?')}")

    if data.get("date_ambiguous"):
        print(f"  ⚠️  DATE AMBIGUOUS: {data.get('date_ambiguity_note', '')}")

    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        ok, result = insert_event(data, flyer_id)
        if ok:
            print(f"  ✅ Inserted: {result}")
        else:
            print(f"  ❌ Insert failed: {result}")
    else:
        print("  (Dry run — no SUPABASE env vars set)")
        print(f"  {json.dumps(data, indent=2)}")

    return data

def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python3 extract_flyer.py <image_or_folder>")
        sys.exit(1)

    target = sys.argv[1]
    p = Path(target)

    if p.is_file():
        process_single(str(p))
    elif p.is_dir():
        images = sorted(p.glob("*.jpg")) + sorted(p.glob("*.jpeg")) + sorted(p.glob("*.png"))
        print(f"Found {len(images)} flyer images in {target}")
        for img in images:
            try:
                process_single(str(img))
            except Exception as e:
                print(f"  ❌ Error: {e}")
            print()
        print(f"Done. Processed {len(images)} flyers.")
    else:
        print(f"ERROR: {target} not found")
        sys.exit(1)

if __name__ == "__main__":
    main()
