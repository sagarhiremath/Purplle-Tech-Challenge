# PROMPT: Generate pytest tests for a FastAPI store intelligence pipeline covering
# event schema validation, idempotent ingest, metrics on empty store, and funnel dedup.
# CHANGES MADE: Added explicit edge-case fixtures for staff exclusion, re-entry, and
# duplicate ingest batches; tightened assertions to match POS correlation window logic.

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import EventMetadata, EventType, StoreEvent


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.testing_session = TestingSessionLocal
        yield test_client
    app.dependency_overrides.clear()


def make_event(**overrides):
    payload = {
        "event_id": str(uuid.uuid4()),
        "store_id": "STORE_BLR_002",
        "camera_id": "CAM_ENTRY_01",
        "visitor_id": "VIS_0001",
        "event_type": EventType.ENTRY.value,
        "timestamp": "2026-04-10T12:00:00Z",
        "zone_id": "ENTRY",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.9,
        "metadata": {},
    }
    payload.update(overrides)
    return payload


def test_event_schema_validation():
    event = StoreEvent(
        event_id=uuid.uuid4(),
        store_id="STORE_BLR_002",
        camera_id="CAM_ENTRY_01",
        visitor_id="VIS_abc",
        event_type=EventType.ENTRY,
        timestamp=datetime.utcnow(),
        zone_id="ENTRY",
        confidence=0.91,
        metadata=EventMetadata(session_seq=1),
    )
    assert event.event_type == EventType.ENTRY


def test_ingest_idempotent(client):
    event = make_event()
    payload = {"events": [event]}
    first = client.post("/events/ingest", json=payload)
    second = client.post("/events/ingest", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["accepted"] == 1
    assert second.json()["duplicates"] == 1


def test_metrics_empty_store(client):
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0


def test_staff_excluded_from_metrics(client):
    events = [
        make_event(visitor_id="VIS_staff", is_staff=True),
        make_event(
            event_id=str(uuid.uuid4()),
            visitor_id="VIS_cust",
            event_type=EventType.ENTRY.value,
            timestamp="2026-04-10T12:00:00Z",
        ),
        make_event(
            event_id=str(uuid.uuid4()),
            visitor_id="VIS_cust",
            event_type=EventType.EXIT.value,
            timestamp="2026-04-10T12:30:00Z",
        ),
    ]
    client.post("/events/ingest", json={"events": events})
    response = client.get("/stores/STORE_BLR_002/metrics")
    assert response.json()["unique_visitors"] == 1


def test_funnel_does_not_double_count_reentry(client):
    events = [
        make_event(event_type=EventType.ENTRY.value, visitor_id="VIS_0002"),
        make_event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.EXIT.value,
            visitor_id="VIS_0002",
            timestamp="2026-04-10T12:10:00Z",
        ),
        make_event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.REENTRY.value,
            visitor_id="VIS_0002",
            timestamp="2026-04-10T12:20:00Z",
        ),
    ]
    client.post("/events/ingest", json={"events": events})
    response = client.get("/stores/STORE_BLR_002/funnel")
    assert response.status_code == 200
    entry_stage = response.json()["stages"][0]
    assert entry_stage["count"] == 1
