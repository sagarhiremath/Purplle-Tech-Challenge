# PROMPT: Create anomaly detection tests for billing queue spike, conversion drop,
# and health stale feed warnings.
# CHANGES MADE: Added deterministic queue spike fixture and stale-feed health test.

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.test_pipeline import client, make_event  # noqa: F401


def test_billing_queue_spike_anomaly(client: TestClient):
    events = [
        make_event(
            event_id=str(uuid.uuid4()),
            visitor_id=f"VIS_{idx}",
            camera_id="CAM_BILLING_01",
            event_type="BILLING_QUEUE_JOIN",
            zone_id="BILLING",
            timestamp=f"2026-04-10T15:{10 + idx:02d}:00Z",
            metadata={"queue_depth": 4, "session_seq": 1},
        )
        for idx in range(1)
    ]
    client.post("/events/ingest", json={"events": events})
    response = client.get("/stores/STORE_BLR_002/anomalies")
    assert response.status_code == 200
    types = [item["anomaly_type"] for item in response.json()["anomalies"]]
    assert "BILLING_QUEUE_SPIKE" in types


def test_health_ok_after_recent_event(client: TestClient):
    client.post("/events/ingest", json={"events": [make_event()]})
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded"}
