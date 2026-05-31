from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from app.models import EventType
from pipeline.emit import EventEmitter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_ID = "STORE_BLR_002"

ZONE_ROTATION = [
    "GOOD_VIBES",
    "DERMDOC",
    "MAYBELLINE",
    "FACES_CANADA",
    "FRAGRANCE",
    "MAKEUP_UNIT",
    "BILLING",
]

DEP_TO_ZONE = {
    "skin": ["GOOD_VIBES", "DERMDOC", "MINIMALIST", "AQUALOGICA"],
    "makeup": ["MAYBELLINE", "FACES_CANADA", "LAKME_MAKEUP", "MAKEUP_UNIT"],
    "hair": ["ALPS_GOODNESS", "STREAX"],
    "fragrance": ["FRAGRANCE"],
    "personal-care": ["DERMDOC", "ACCESSORIES"],
    "bath-and-body": ["DERMDOC", "GOOD_VIBES"],
}


def generate_from_pos(
    pos_csv: Path,
    brigade_csv: Path,
    store_id: str = DEFAULT_STORE_ID,
) -> list:
    emitter = EventEmitter(store_id=store_id)
    events = []

    pos_df = pd.read_csv(pos_csv)
    brigade_df = pd.read_csv(brigade_csv)
    order_zones = {}
    for _, row in brigade_df.iterrows():
        dep = row.get("dep_name", "skin")
        zones = DEP_TO_ZONE.get(dep, ZONE_ROTATION)
        order_zones.setdefault(int(row["order_id"]), []).append(random.choice(zones))

    visitor_counter = 1
    for _, txn in pos_df.iterrows():
        txn_time = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
        visitor_id = f"VIS_{visitor_counter:04x}"
        visitor_counter += 1
        entry_time = txn_time - timedelta(minutes=random.randint(8, 20))
        events.append(
            emitter.create_event(
                camera_id="CAM_ENTRY_01",
                visitor_id=visitor_id,
                event_type=EventType.ENTRY,
                timestamp=entry_time,
                zone_id="ENTRY",
                confidence=round(random.uniform(0.78, 0.96), 2),
            )
        )

        zones = order_zones.get(int(str(txn["transaction_id"]).replace("TXN_", "")), ZONE_ROTATION[:3])
        cursor = entry_time + timedelta(seconds=30)
        for zone in zones[: random.randint(2, 4)]:
            events.append(
                emitter.create_event(
                    camera_id="CAM_FLOOR_01",
                    visitor_id=visitor_id,
                    event_type=EventType.ZONE_ENTER,
                    timestamp=cursor,
                    zone_id=zone,
                    confidence=round(random.uniform(0.7, 0.93), 2),
                )
            )
            dwell_ms = random.randint(30000, 120000)
            events.append(
                emitter.create_event(
                    camera_id="CAM_FLOOR_01",
                    visitor_id=visitor_id,
                    event_type=EventType.ZONE_DWELL,
                    timestamp=cursor + timedelta(seconds=30),
                    zone_id=zone,
                    dwell_ms=dwell_ms,
                    confidence=round(random.uniform(0.65, 0.9), 2),
                )
            )
            events.append(
                emitter.create_event(
                    camera_id="CAM_FLOOR_01",
                    visitor_id=visitor_id,
                    event_type=EventType.ZONE_EXIT,
                    timestamp=cursor + timedelta(seconds=dwell_ms // 1000),
                    zone_id=zone,
                    confidence=round(random.uniform(0.7, 0.92), 2),
                )
            )
            cursor += timedelta(seconds=dwell_ms // 1000 + random.randint(20, 60))

        queue_depth = random.randint(0, 4)
        billing_time = txn_time - timedelta(minutes=random.randint(1, 4))
        if queue_depth > 0:
            events.append(
                emitter.create_event(
                    camera_id="CAM_BILLING_01",
                    visitor_id=visitor_id,
                    event_type=EventType.BILLING_QUEUE_JOIN,
                    timestamp=billing_time,
                    zone_id="BILLING",
                    queue_depth=queue_depth,
                    confidence=0.88,
                )
            )
        else:
            events.append(
                emitter.create_event(
                    camera_id="CAM_BILLING_01",
                    visitor_id=visitor_id,
                    event_type=EventType.ZONE_ENTER,
                    timestamp=billing_time,
                    zone_id="BILLING",
                    confidence=0.9,
                )
            )

        exit_time = txn_time + timedelta(minutes=random.randint(2, 8))
        events.append(
            emitter.create_event(
                camera_id="CAM_ENTRY_01",
                visitor_id=visitor_id,
                event_type=EventType.EXIT,
                timestamp=exit_time,
                zone_id="ENTRY",
                confidence=0.87,
            )
        )

    if len(events) > 5 and random.random() > 0.5:
        reentry_id = "VIS_0002"
        reentry_time = events[5].timestamp + timedelta(minutes=15)
        events.append(
            emitter.create_event(
                camera_id="CAM_ENTRY_01",
                visitor_id=reentry_id,
                event_type=EventType.REENTRY,
                timestamp=reentry_time,
                zone_id="ENTRY",
                confidence=0.81,
            )
        )

    staff_id = "VIS_staff01"
    first_txn_time = datetime.fromisoformat(pos_df.iloc[0]["timestamp"].replace("Z", "+00:00"))
    staff_entry = first_txn_time.replace(hour=10, minute=5)
    events.extend(
        [
            emitter.create_event(
                camera_id="CAM_ENTRY_01",
                visitor_id=staff_id,
                event_type=EventType.ENTRY,
                timestamp=staff_entry,
                zone_id="ENTRY",
                is_staff=True,
                confidence=0.92,
            ),
            emitter.create_event(
                camera_id="CAM_FLOOR_01",
                visitor_id=staff_id,
                event_type=EventType.ZONE_DWELL,
                timestamp=staff_entry + timedelta(minutes=5),
                zone_id="GOOD_VIBES",
                dwell_ms=180000,
                is_staff=True,
                confidence=0.95,
            ),
        ]
    )

    events.sort(key=lambda item: item.timestamp)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate demo events from POS data")
    parser.add_argument("--pos", type=Path, default=ROOT / "data" / "pos_transactions.csv")
    parser.add_argument(
        "--brigade",
        type=Path,
        default=ROOT / "data" / "brigade_pos.csv",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "generated_events.jsonl")
    parser.add_argument("--store-id", default=DEFAULT_STORE_ID)
    args = parser.parse_args()

    events = generate_from_pos(args.pos, args.brigade, args.store_id)
    emitter = EventEmitter(store_id=args.store_id)
    emitter.write_jsonl(events, args.output)
    print(f"Generated {len(events)} events -> {args.output}")


if __name__ == "__main__":
    main()
