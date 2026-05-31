from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import CONVERSION_WINDOW_SECONDS
from app.database import EventRecord, POSTransactionRecord
from app.models import MetricsResponse


def _customer_events(db: Session, store_id: str, day: date | None = None):
    query = db.query(EventRecord).filter(
        EventRecord.store_id == store_id,
        EventRecord.is_staff.is_(False),
    )
    if day:
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        query = query.filter(EventRecord.timestamp >= start, EventRecord.timestamp < end)
    return query.order_by(EventRecord.timestamp.asc()).all()


def _sessions_from_events(events: list[EventRecord]) -> dict[str, list[EventRecord]]:
    sessions: dict[str, list[EventRecord]] = defaultdict(list)
    for event in events:
        sessions[event.visitor_id].append(event)
    return sessions


def _converted_visitors(
    db: Session, store_id: str, visitor_ids: set[str], day: date
) -> set[str]:
    if not visitor_ids:
        return set()

    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    transactions = (
        db.query(POSTransactionRecord)
        .filter(
            POSTransactionRecord.store_id == store_id,
            POSTransactionRecord.timestamp >= start,
            POSTransactionRecord.timestamp < end,
        )
        .all()
    )
    billing_events = [
        event
        for event in _customer_events(db, store_id, day)
        if event.zone_id == "BILLING"
        or event.event_type in {"BILLING_QUEUE_JOIN", "ZONE_ENTER", "ZONE_DWELL"}
    ]

    converted: set[str] = set()
    for txn in transactions:
        window_start = txn.timestamp - timedelta(seconds=CONVERSION_WINDOW_SECONDS)
        for event in billing_events:
            if (
                event.visitor_id in visitor_ids
                and window_start <= event.timestamp <= txn.timestamp
            ):
                converted.add(event.visitor_id)
                break
    return converted


def _resolve_target_day(db: Session, store_id: str, day: date | None) -> date:
    if day:
        return day
    latest = (
        db.query(func.max(EventRecord.timestamp))
        .filter(EventRecord.store_id == store_id)
        .scalar()
    )
    return latest.date() if latest else date.today()


def compute_metrics(db: Session, store_id: str, day: date | None = None) -> MetricsResponse:
    target_day = _resolve_target_day(db, store_id, day)
    events = _customer_events(db, store_id, target_day)
    entry_visitors = {
        event.visitor_id
        for event in events
        if event.event_type == "ENTRY" or event.event_type == "REENTRY"
    }
    unique_visitors = len(entry_visitors)
    converted = _converted_visitors(db, store_id, entry_visitors, target_day)
    conversion_rate = (len(converted) / unique_visitors) if unique_visitors else 0.0

    dwell_by_zone: dict[str, list[int]] = defaultdict(list)
    for event in events:
        if event.zone_id and event.dwell_ms > 0:
            dwell_by_zone[event.zone_id].append(event.dwell_ms)
    avg_dwell_by_zone = {
        zone: round(sum(values) / len(values), 2)
        for zone, values in dwell_by_zone.items()
        if values
    }

    queue_joins = [
        event
        for event in events
        if event.event_type == "BILLING_QUEUE_JOIN"
    ]
    current_queue_depth = 0
    if queue_joins:
        latest = max(queue_joins, key=lambda item: item.timestamp)
        metadata = __import__("json").loads(latest.metadata_json or "{}")
        current_queue_depth = metadata.get("queue_depth") or 0

    abandon_count = sum(
        1 for event in events if event.event_type == "BILLING_QUEUE_ABANDON"
    )
    join_count = sum(1 for event in events if event.event_type == "BILLING_QUEUE_JOIN")
    abandonment_rate = (abandon_count / join_count) if join_count else 0.0

    return MetricsResponse(
        store_id=store_id,
        date=target_day.isoformat(),
        unique_visitors=unique_visitors,
        converted_visitors=len(converted),
        conversion_rate=round(conversion_rate, 4),
        avg_dwell_by_zone=avg_dwell_by_zone,
        current_queue_depth=current_queue_depth,
        queue_abandonment_rate=round(abandonment_rate, 4),
    )
