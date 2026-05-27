# TeamRopingCalendar.com

Supabase-backed team roping event calendar with OCR flyer extraction pipeline.

## Architecture

- **Database:** Supabase (PostgreSQL + REST API)
- **Frontend:** Static HTML on Cloudflare Pages
- **OCR Pipeline:** Claude Sonnet API — extracts structured data from flyer images
- **Flyer Storage:** Cloudflare Images CDN
- **Philosophy:** Zero fabrication. Only data that's literally on the flyer. Link to flyer for details.

## Project Structure

```
sql/                    SQL migrations
  001_create_events.sql   Events table + indexes + RLS
scripts/
  migrate_events.py       Seed Supabase from events.json (393 existing events)
  extract_flyer.py        OCR pipeline — process flyer images via Claude API
data/
  events.json             Copy of existing event data (seed only, not live)
```

## Setup

1. Create Supabase project
2. Run `sql/001_create_events.sql` in SQL Editor
3. Set env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
4. Run `python3 scripts/migrate_events.py` to seed existing events
5. Process new flyers: `python3 scripts/extract_flyer.py /path/to/flyers/`

## OCR Pipeline

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export SUPABASE_URL=https://xxxxx.supabase.co
export SUPABASE_SERVICE_KEY=eyJ...

# Single flyer
python3 scripts/extract_flyer.py flyer.jpg

# Batch folder
python3 scripts/extract_flyer.py ./flyers/
```

Cost: ~$0.014 per flyer (~$21/month at 1500 flyers)

## Data Rules

- `source: "manual"` — existing human-verified events (393 seed records)
- `source: "ocr_auto"` — auto-extracted from flyers, needs review
- `source: "ocr_reviewed"` — auto-extracted, human-verified
- `confidence` — OCR confidence score (1.0 = certain, <0.7 = flag for review)
- `flyer_url` — link to original flyer image (the source of truth)
- `description` — NULL for OCR events (the flyer IS the description)

## Relationship to teamroping.ai

**None.** This is a completely separate project. teamroping.ai is untouched. The `data/events.json` file is a one-time copy used for seeding only.
