from __future__ import annotations

import csv
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import POS_TRANSACTIONS_PATH
from app.database import EventRecord, POSTransactionRecord
from app.models import IngestRequest, IngestResponse, StoreEvent

logger = logging.getLogger(__name__)


def event_to_record(event: StoreEvent) -> EventRecord:
    return EventRecord(
        event_id=str(event.event_id),
        store_id=event.store_id,
        camera_id=event.camera_id,
        visitor_id=event.visitor_id,
        event_type=event.event_type.value,
        timestamp=event.timestamp.replace(tzinfo=None),
        zone_id=event.zone_id,
        dwell_ms=event.dwell_ms,
        is_staff=event.is_staff,
        confidence=event.confidence,
        metadata_json=json.dumps(event.metadata.model_dump()),
    )


def ingest_events(db: Session, payload: IngestRequest) -> IngestResponse:
    accepted = 0
    duplicates = 0
    rejected = 0
    errors: list[dict[str, str]] = []

    for index, event in enumerate(payload.events):
        try:
            existing = db.get(EventRecord, str(event.event_id))
            if existing:
                duplicates += 1
                continue
            db.add(event_to_record(event))
            accepted += 1
        except Exception as exc:
            rejected += 1
            errors.append({"index": str(index), "error": str(exc)})

    if accepted:
        db.commit()
    return IngestResponse(
        accepted=accepted, duplicates=duplicates, rejected=rejected, errors=errors
    )


def seed_pos_transactions(db: Session) -> int:
    if not POS_TRANSACTIONS_PATH.exists():
        logger.warning("POS file not found at %s", POS_TRANSACTIONS_PATH)
        return 0

    inserted = 0
    with POS_TRANSACTIONS_PATH.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            txn_id = row["transaction_id"]
            if db.get(POSTransactionRecord, txn_id):
                continue
            db.add(
                POSTransactionRecord(
                    transaction_id=txn_id,
                    store_id=row["store_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "")),
                    basket_value_inr=float(row["basket_value_inr"]),
                )
            )
            inserted += 1
    if inserted:
        db.commit()
    return inserted
