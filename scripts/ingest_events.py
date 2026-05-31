#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.emit import EventEmitter


def ingest_file(file_path: Path, api_url: str, batch_size: int = 100) -> None:
    events = list(EventEmitter.iter_jsonl(file_path))
    if not events:
        print("No events to ingest.")
        return

    with httpx.Client(timeout=30.0) as client:
        for start in range(0, len(events), batch_size):
            batch = events[start : start + batch_size]
            payload = {
                "events": [
                    json.loads(event.model_dump_json())
                    for event in batch
                ]
            }
            response = client.post(f"{api_url}/events/ingest", json=payload)
            response.raise_for_status()
            result = response.json()
            print(
                f"Batch {start // batch_size + 1}: "
                f"accepted={result['accepted']} duplicates={result['duplicates']} "
                f"rejected={result['rejected']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    ingest_file(args.file, args.api_url, args.batch_size)


if __name__ == "__main__":
    main()
