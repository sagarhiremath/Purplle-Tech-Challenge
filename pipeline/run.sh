#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[1/5] Converting POS data..."
python scripts/convert_pos.py

echo "[2/5] Linking CCTV clips into data/clips/..."
python scripts/setup_clips.py

echo "[3/5] Running detection pipeline..."
if compgen -G "data/clips/*.mp4" > /dev/null || compgen -G "data/clips/**/*.mp4" > /dev/null; then
  python -m pipeline.detect \
    --clips-dir data/clips \
    --output data/generated_events.jsonl \
    --clip-date 2026-04-10T10:00:00Z \
    --frame-skip 10
else
  echo "No CCTV clips found. Using POS-backed demo event generator."
  python -m pipeline.demo_generator --output data/generated_events.jsonl
fi

echo "[4/5] Copying sample events..."
cp data/generated_events.jsonl data/sample_events.jsonl

echo "[5/5] Ingesting events into API..."
python scripts/ingest_events.py --file data/generated_events.jsonl || echo "API not running; skip ingest."

echo "Pipeline complete. Events written to data/generated_events.jsonl"
