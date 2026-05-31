"""Example assertions referenced by the challenge scoring harness."""

from __future__ import annotations

import httpx

API_URL = "http://localhost:8000"
STORE_ID = "STORE_BLR_002"


def assert_metrics_endpoint_returns_json() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/metrics", timeout=10.0)
    assert response.status_code == 200
    body = response.json()
    assert "conversion_rate" in body
    assert "unique_visitors" in body


def assert_funnel_has_four_stages() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/funnel", timeout=10.0)
    assert response.status_code == 200
    assert len(response.json()["stages"]) == 4


def assert_health_reports_store_status() -> None:
    response = httpx.get(f"{API_URL}/health", timeout=10.0)
    assert response.status_code == 200
    assert "stores" in response.json()


def assert_ingest_accepts_batch(sample_events: list[dict]) -> None:
    response = httpx.post(
        f"{API_URL}/events/ingest",
        json={"events": sample_events[:10]},
        timeout=10.0,
    )
    assert response.status_code == 200
    assert response.json()["accepted"] >= 0


def assert_heatmap_normalized_scores() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/heatmap", timeout=10.0)
    assert response.status_code == 200
    zones = response.json()["zones"]
    for zone in zones:
        assert 0 <= zone["normalized_score"] <= 100


def assert_anomalies_have_severity() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/anomalies", timeout=10.0)
    assert response.status_code == 200
    for anomaly in response.json()["anomalies"]:
        assert anomaly["severity"] in {"INFO", "WARN", "CRITICAL"}


def assert_zero_traffic_store_safe() -> None:
    response = httpx.get(f"{API_URL}/stores/UNKNOWN_STORE/metrics", timeout=10.0)
    assert response.status_code == 200
    body = response.json()
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0


def assert_ingest_is_idempotent(sample_events: list[dict]) -> None:
    import copy
    import uuid

    fresh = []
    for event in sample_events[:5]:
        item = copy.deepcopy(event)
        item["event_id"] = str(uuid.uuid4())
        item["visitor_id"] = f"VIS_idem_{uuid.uuid4().hex[:6]}"
        fresh.append(item)

    payload = {"events": fresh}
    first = httpx.post(f"{API_URL}/events/ingest", json=payload, timeout=10.0)
    second = httpx.post(f"{API_URL}/events/ingest", json=payload, timeout=10.0)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["accepted"] == len(payload["events"])
    assert second.json()["duplicates"] == len(payload["events"])


def assert_staff_excluded_from_conversion_rate() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/metrics", timeout=10.0)
    assert response.status_code == 200


def assert_funnel_drop_off_non_negative() -> None:
    response = httpx.get(f"{API_URL}/stores/{STORE_ID}/funnel", timeout=10.0)
    for stage in response.json()["stages"]:
        assert stage["drop_off_pct"] >= 0
