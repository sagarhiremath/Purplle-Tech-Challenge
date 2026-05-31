# Store Intelligence — Design Document

## Overview

This system converts offline retail camera signals and POS transactions into actionable store analytics. The north-star metric is **offline conversion rate**: purchasers divided by unique visitors in a session window.

```
CCTV Clips / Demo Generator
        ↓
Detection Pipeline (OpenCV + centroid tracking)
        ↓
Structured Events (JSONL)
        ↓
FastAPI Ingest + SQLite Storage
        ↓
Metrics / Funnel / Heatmap / Anomalies / Health
        ↓
Live Terminal Dashboard
```

## Components

### Detection Pipeline (`pipeline/`)

- **`detect.py`**: Processes CCTV clips using background subtraction and contour detection. Tracks centroids, infers entry/exit direction on the entry camera, and maps floor positions to store zones.
- **`tracker.py`**: Lightweight centroid tracker with visitor token assignment and direction inference.
- **`emit.py`**: Emits schema-compliant events with UUIDs, session sequence numbers, and metadata.
- **`demo_generator.py`**: POS-backed fallback when CCTV clips are unavailable. Generates realistic visitor journeys correlated with Brigade Bangalore transactions.

### Intelligence API (`app/`)

- **Ingestion**: Idempotent batch ingest keyed by `event_id`.
- **Metrics**: Unique visitors, conversion rate (5-minute billing window before POS timestamp), dwell by zone, queue depth, abandonment rate.
- **Funnel**: Session-based funnel with re-entry deduplication via visitor sets.
- **Heatmap**: Zone visit frequency and normalized dwell scores with confidence flag when sessions < 20.
- **Anomalies**: Billing queue spike, conversion drop vs 7-day baseline, dead zone detection.
- **Health**: Per-store last event timestamp with `STALE_FEED` warnings after 10 minutes.

### Storage

SQLite is used for simplicity and zero-config Docker deployment. Events and POS transactions are stored in separate tables. The API resolves the analytics day from the latest ingested event when no date query param is supplied.

## Edge Case Handling

| Edge Case | Approach |
|---|---|
| Group entry | One ENTRY event per detected centroid/track |
| Staff movement | `is_staff` flag; excluded from customer metrics |
| Re-entry | REENTRY event type; funnel deduplicates by visitor_id set |
| Partial occlusion | Low-confidence events retained (not suppressed) |
| Empty store | Metrics return zeros, no crashes |
| Cross-camera overlap | Visitor tokens assigned per tracker; dedup at analytics layer |
| Billing abandonment | BILLING_QUEUE_ABANDON events + abandonment rate metric |

## AI-Assisted Decisions

1. **Zone mapping from floor plan**: An LLM was used to interpret the Brigade Road layout image and map brand bays to zone IDs in `store_layout.json`. I validated zone names against the POS CSV department fields (`skin`, `makeup`, `hair`, etc.) and adjusted mappings where brand placement did not match department taxonomy.

2. **Conversion correlation window**: AI suggested a 10-minute POS correlation window. I chose **5 minutes** instead because billing queue clips in the problem statement imply tighter coupling between billing-zone presence and transaction timestamp, reducing false conversions from visitors who browsed earlier.

3. **Detection fallback strategy**: AI recommended waiting for YOLO weights before building the API. I overrode this and shipped an OpenCV motion pipeline plus POS-backed demo generator so the acceptance gate (`docker compose up`, `/metrics`) passes immediately while remaining ready for YOLO upgrade when CCTV clips arrive.

## Deployment

`docker compose up` starts the API with health checks. Optional profiles run the pipeline ingest and live dashboard. Structured request logging includes trace ID, endpoint, latency, and status code.

## Future Improvements

- Replace motion detection with YOLOv8 + ByteTrack when official clips are available
- Add PostgreSQL for multi-store concurrent writes
- Cross-camera Re-ID using OSNet embeddings
- Web dashboard with zone heatmap visualization
