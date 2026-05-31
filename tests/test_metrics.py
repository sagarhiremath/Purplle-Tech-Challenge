# PROMPT: Write pytest tests for store metrics and heatmap endpoints including
# conversion rate calculation and low-confidence flag when session count is small.
# CHANGES MADE: Added POS-backed conversion test and heatmap confidence assertion.

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from tests.test_pipeline import client, make_event  # noqa: F401


def test_conversion_rate_with_billing_and_pos(client: TestClient):
    from app.database import POSTransactionRecord

    db = client.testing_session()
    db.add(
        POSTransactionRecord(
            transaction_id="TXN_TEST",
            store_id="STORE_BLR_002",
            timestamp=datetime.fromisoformat("2026-04-10T14:38:12"),
            basket_value_inr=1240.0,
        )
    )
    db.commit()
    db.close()

    events = [
        make_event(
            visitor_id="VIS_buyer",
            timestamp="2026-04-10T14:34:00Z",
            event_type="ENTRY",
        ),
        make_event(
            event_id=str(uuid.uuid4()),
            visitor_id="VIS_buyer",
            camera_id="CAM_BILLING_01",
            event_type="ZONE_ENTER",
            zone_id="BILLING",
            timestamp="2026-04-10T14:36:00Z",
        ),
    ]
    response = client.post("/events/ingest", json={"events": events})
    assert response.status_code == 200

    metrics = client.get("/stores/STORE_BLR_002/metrics?day=2026-04-10")
    body = metrics.json()
    assert body["unique_visitors"] == 1
    assert body["converted_visitors"] == 1
    assert body["conversion_rate"] == 1.0


def test_heatmap_low_confidence(client: TestClient):
    events = [make_event(visitor_id=f"VIS_{idx}") for idx in range(3)]
    client.post("/events/ingest", json={"events": events})
    response = client.get("/stores/STORE_BLR_002/heatmap")
    assert response.status_code == 200
    assert response.json()["data_confidence"] == "LOW"
