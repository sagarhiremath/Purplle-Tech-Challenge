from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import STALE_FEED_THRESHOLD_SECONDS
from app.database import EventRecord, get_store_ids
from app.metrics import _customer_events, _resolve_target_day, compute_metrics
from app.models import (
    AnomaliesResponse,
    Anomaly,
    AnomalySeverity,
    HealthResponse,
    StoreHealth,
)


def detect_anomalies(db: Session, store_id: str) -> AnomaliesResponse:
    target_day = _resolve_target_day(db, store_id, None)
    metrics = compute_metrics(db, store_id, target_day)
    events = _customer_events(db, store_id, target_day)
    anomalies: list[Anomaly] = []
    now = datetime.utcnow()

    if metrics.current_queue_depth >= 3:
        anomalies.append(
            Anomaly(
                anomaly_type="BILLING_QUEUE_SPIKE",
                severity=AnomalySeverity.WARN
                if metrics.current_queue_depth < 5
                else AnomalySeverity.CRITICAL,
                message=f"Billing queue depth is {metrics.current_queue_depth}",
                suggested_action="Open an additional billing counter or deploy floor staff to billing.",
                detected_at=now,
            )
        )

    week_ago = target_day - timedelta(days=7)
    historical_rates = []
    for offset in range(1, 8):
        day = week_ago + timedelta(days=offset)
        if day >= target_day:
            break
        day_metrics = compute_metrics(db, store_id, day)
        historical_rates.append(day_metrics.conversion_rate)
    baseline = sum(historical_rates) / len(historical_rates) if historical_rates else None
    if baseline and metrics.conversion_rate < baseline * 0.7:
        anomalies.append(
            Anomaly(
                anomaly_type="CONVERSION_DROP",
                severity=AnomalySeverity.WARN,
                message=(
                    f"Conversion rate {metrics.conversion_rate:.2%} is below 7-day baseline "
                    f"{baseline:.2%}"
                ),
                suggested_action="Review staffing, queue management, and in-store promotions.",
                detected_at=now,
            )
        )

    zone_last_seen: dict[str, datetime] = {}
    for event in events:
        if event.zone_id and event.zone_id not in {"ENTRY", "BILLING"}:
            zone_last_seen[event.zone_id] = max(
                zone_last_seen.get(event.zone_id, event.timestamp), event.timestamp
            )
    cutoff = now - timedelta(minutes=30)
    for zone_id, last_seen in zone_last_seen.items():
        if last_seen < cutoff:
            anomalies.append(
                Anomaly(
                    anomaly_type="DEAD_ZONE",
                    severity=AnomalySeverity.INFO,
                    message=f"No visits in zone {zone_id} for over 30 minutes",
                    suggested_action="Check product placement or run a zone-specific promotion.",
                    detected_at=now,
                )
            )

    return AnomaliesResponse(store_id=store_id, anomalies=anomalies)


def compute_health(db: Session) -> HealthResponse:
    warnings: list[str] = []
    stores: list[StoreHealth] = []
    now = datetime.utcnow()

    for store_id in get_store_ids():
        last_event = (
            db.query(EventRecord.timestamp)
            .filter(EventRecord.store_id == store_id)
            .order_by(EventRecord.timestamp.desc())
            .first()
        )
        last_event_at = last_event[0] if last_event else None
        is_stale = False
        if last_event_at is None:
            is_stale = True
            warnings.append(f"STALE_FEED: No events ingested for {store_id}")
        elif (now - last_event_at).total_seconds() > STALE_FEED_THRESHOLD_SECONDS:
            is_stale = True
            warnings.append(
                f"STALE_FEED: Last event for {store_id} was "
                f"{int((now - last_event_at).total_seconds())}s ago"
            )
        stores.append(
            StoreHealth(store_id=store_id, last_event_at=last_event_at, is_stale=is_stale)
        )

    status = "degraded" if warnings else "ok"
    return HealthResponse(status=status, stores=stores, warnings=warnings)
