#!/usr/bin/env python3
"""Run challenge-style assertions against a live API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assertions import ALL_ASSERTIONS, INGEST_ASSERTIONS

SAMPLE_EVENTS = ROOT / "data" / "sample_events.jsonl"
GENERATED_EVENTS = ROOT / "data" / "generated_events.jsonl"


def load_sample_events() -> list[dict]:
    path = SAMPLE_EVENTS if SAMPLE_EVENTS.exists() else GENERATED_EVENTS
    if not path.exists():
        print(f"No events file found. Run: bash pipeline/run.sh")
        sys.exit(1)
    events = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def main() -> None:
    sample_events = load_sample_events()
    passed = 0
    failed = 0

    print(f"Running {len(ALL_ASSERTIONS) + len(INGEST_ASSERTIONS)} assertions against http://localhost:8000\n")

    for fn in ALL_ASSERTIONS:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            failed += 1

    for fn in INGEST_ASSERTIONS:
        try:
            fn(sample_events)
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
