# Engineering Choices

## Decision 1: Detection Model Selection

### Options Considered
1. **YOLOv8 + ByteTrack** — best accuracy, heavier dependencies, needs GPU for reasonable throughput
2. **OpenCV MOG2 + centroid tracking** — lightweight, runs on CPU, weaker on occlusion
3. **VLM frame sampling** — flexible but expensive and slow for 20-minute clips

### What AI Suggested
Use YOLOv8n as default with ByteTrack, falling back to motion detection only for empty frames.

### What I Chose
OpenCV MOG2 background subtraction with a custom centroid tracker for the initial build, plus a POS-backed demo generator when clips are missing.

### Why
The acceptance gate requires a working API via `docker compose up` before full CCTV footage is available in this workspace. Motion detection provides a real video-processing path without bundling large model weights. When official clips arrive, the same event emitter and schema remain unchanged — only `detect.py` model inference needs upgrading.

---

## Decision 2: Event Schema Design

### Options Considered
1. Flat events with minimal metadata
2. Rich schema with typed event catalogue and nested metadata (challenge spec)
3. Separate tables per event type in the detection layer

### What AI Suggested
Use a single polymorphic event table with JSON metadata and strict Pydantic validation at ingest.

### What I Chose
The challenge schema exactly: typed `event_type` enum, `visitor_id` session token, `metadata.session_seq`, optional `queue_depth`.

### Why
The scoring harness validates schema compliance and downstream analytics depend on consistent event types for funnel stages. A single event table keeps ingest idempotent and simplifies heatmap/funnel SQL queries. Metadata stays extensible without schema migrations.

---

## Decision 3: API Storage and Analytics Day Resolution

### Options Considered
1. In-memory store (simple, lost on restart)
2. SQLite file (zero-config, single writer)
3. PostgreSQL (production-grade, heavier compose setup)

### What AI Suggested
PostgreSQL in Docker with Redis cache for metrics.

### What I Chose
SQLite with file persisted under `data/store_intelligence.db`.

### Why
The challenge explicitly allows SQLite. For a single-store demo with batch ingest, SQLite meets idempotency and query needs without extra services. I added `_resolve_target_day()` so metrics default to the latest day with ingested events rather than `date.today()`, which prevents empty results when demo events use historical POS dates (2026-04-10).

### API Trade-off
Conversion correlation uses a **5-minute billing window** before POS timestamp rather than customer ID matching (not available in POS data). This matches the problem statement and keeps the north-star metric computable with the provided Brigade CSV.
