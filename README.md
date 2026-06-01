# Store Intelligence Challenge

End-to-end Store Intelligence system for Purplle Tech Challenge 2026 Round 2.

## Quick Start

```bash
cd "Purple Tech"
docker compose up --build -d
docker compose --profile pipeline up --build   # process CCTV + load data
open http://localhost:8000/dashboard           # live metrics UI
```

## Web Dashboard

Open **http://localhost:8000/dashboard** for a live, auto-refreshing store intelligence UI:

- Conversion rate (north star metric)
- Visitor count, queue depth, abandonment rate
- Conversion funnel with drop-offs
- Zone heatmap
- Dwell time chart
- Live anomaly alerts

Refreshes every 3 seconds from the API.

## Quick Start (API only)

```bash
docker compose up --build
curl http://localhost:8000/stores/STORE_BLR_002/metrics
```

## Full Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/convert_pos.py
bash pipeline/run.sh
uvicorn app.main:app --reload
```

## Detection Pipeline

CCTV clips live in the project root as `CAM 1.mp4` … `CAM 5.mp4`. The setup script links them into `data/clips/` with camera-aware names:

| Root file | Linked as | Camera |
|---|---|---|
| `CAM 1.mp4` | `data/clips/STORE_BLR_002_entry.mp4` | Entry |
| `CAM 2.mp4` | `data/clips/STORE_BLR_002_floor.mp4` | Main floor |
| `CAM 3.mp4` | `data/clips/STORE_BLR_002_billing.mp4` | Billing |
| `CAM 4.mp4`, `CAM 5.mp4` | `data/clips/extra/` | Optional alternates |

```bash
python scripts/setup_clips.py   # link root clips into data/clips/
bash pipeline/run.sh            # process videos → events → ingest
```

If no clips are present, the pipeline falls back to a POS-backed demo generator.

Output: `data/generated_events.jsonl`

## Ingest Events

```bash
python scripts/ingest_events.py --file data/generated_events.jsonl
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /events/ingest` | Batch ingest up to 500 events |
| `GET /stores/{id}/metrics` | Visitors, conversion rate, dwell, queue |
| `GET /stores/{id}/funnel` | Entry → Zone → Billing → Purchase funnel |
| `GET /stores/{id}/heatmap` | Zone visit frequency and dwell scores |
| `GET /stores/{id}/anomalies` | Queue spike, conversion drop, dead zones |
| `GET /health` | Service and stale-feed status |

## Docker Profiles

```bash
docker compose up --build
docker compose --profile pipeline up --build
docker compose --profile dashboard up --build
```

Live dashboard:

```bash
open http://localhost:8000/dashboard
# OR terminal version:
python dashboard/live_dashboard.py
```

## Tests

```bash
pytest --cov=app --cov=pipeline --cov-report=term-missing
```

## Data Mapping

- Brigade POS CSV → `data/pos_transactions.csv` (`STORE_BLR_002`)
- Store layout image → `data/store_layout.json` zone definitions
