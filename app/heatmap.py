from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.metrics import _customer_events, _resolve_target_day
from app.models import HeatmapResponse, HeatmapZone


def compute_heatmap(db: Session, store_id: str, day: date | None = None) -> HeatmapResponse:
    target_day = _resolve_target_day(db, store_id, day)
    events = _customer_events(db, store_id, target_day)

    visits: dict[str, set[str]] = defaultdict(set)
    dwells: dict[str, list[int]] = defaultdict(list)
    for event in events:
        if not event.zone_id or event.zone_id in {"ENTRY"}:
            continue
        visits[event.zone_id].add(event.visitor_id)
        if event.dwell_ms > 0:
            dwells[event.zone_id].append(event.dwell_ms)

    session_count = len(
        {
            event.visitor_id
            for event in events
            if event.event_type in {"ENTRY", "REENTRY"}
        }
    )
    data_confidence = "HIGH" if session_count >= 20 else "LOW"

    raw_scores = []
    zones: list[HeatmapZone] = []
    for zone_id, visitor_set in visits.items():
        avg_dwell = (
            sum(dwells[zone_id]) / len(dwells[zone_id]) if dwells.get(zone_id) else 0.0
        )
        score = len(visitor_set) * 10 + (avg_dwell / 1000)
        raw_scores.append(score)
        zones.append(
            HeatmapZone(
                zone_id=zone_id,
                visit_frequency=len(visitor_set),
                avg_dwell_ms=round(avg_dwell, 2),
                normalized_score=0.0,
            )
        )

    max_score = max(raw_scores) if raw_scores else 1.0
    for zone in zones:
        raw = zone.visit_frequency * 10 + (zone.avg_dwell_ms / 1000)
        zone.normalized_score = round((raw / max_score) * 100, 2) if max_score else 0.0

    zones.sort(key=lambda item: item.normalized_score, reverse=True)
    return HeatmapResponse(
        store_id=store_id, zones=zones, data_confidence=data_confidence
    )
