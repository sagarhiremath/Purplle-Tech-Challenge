from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.database import EventRecord
from app.metrics import _converted_visitors, _customer_events, _resolve_target_day
from app.models import FunnelResponse, FunnelStage


def compute_funnel(db: Session, store_id: str, day: date | None = None) -> FunnelResponse:
    target_day = _resolve_target_day(db, store_id, day)
    events = _customer_events(db, store_id, target_day)

    entry_visitors = {
        event.visitor_id
        for event in events
        if event.event_type in {"ENTRY", "REENTRY"}
    }
    zone_visitors = {
        event.visitor_id
        for event in events
        if event.event_type in {"ZONE_ENTER", "ZONE_DWELL"}
        and event.zone_id not in {None, "ENTRY", "BILLING"}
    }
    billing_visitors = {
        event.visitor_id
        for event in events
        if event.zone_id == "BILLING" or event.event_type == "BILLING_QUEUE_JOIN"
    }
    converted = _converted_visitors(db, store_id, entry_visitors, target_day)

    stages_data = [
        ("Entry", len(entry_visitors)),
        ("Zone Visit", len(zone_visitors & entry_visitors)),
        ("Billing Queue", len(billing_visitors & entry_visitors)),
        ("Purchase", len(converted)),
    ]

    stages: list[FunnelStage] = []
    previous_count = stages_data[0][1]
    for index, (name, count) in enumerate(stages_data):
        if index == 0:
            drop_off = 0.0
        else:
            drop_off = (
                round(max(0.0, ((previous_count - count) / previous_count) * 100), 2)
                if previous_count
                else 0.0
            )
        stages.append(FunnelStage(stage=name, count=count, drop_off_pct=drop_off))
        previous_count = count

    return FunnelResponse(store_id=store_id, stages=stages)
