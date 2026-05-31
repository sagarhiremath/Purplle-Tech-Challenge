from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth: int | None = None
    sku_zone: str | None = None
    session_seq: int | None = None


class StoreEvent(BaseModel):
    event_id: UUID
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: EventType
    timestamp: datetime
    zone_id: str | None = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        raise ValueError("Invalid timestamp")


class IngestRequest(BaseModel):
    events: list[StoreEvent]


class IngestResponse(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    errors: list[dict[str, str]] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    store_id: str
    date: str
    unique_visitors: int
    converted_visitors: int
    conversion_rate: float
    avg_dwell_by_zone: dict[str, float]
    current_queue_depth: int
    queue_abandonment_rate: float


class FunnelStage(BaseModel):
    stage: str
    count: int
    drop_off_pct: float


class FunnelResponse(BaseModel):
    store_id: str
    stages: list[FunnelStage]


class HeatmapZone(BaseModel):
    zone_id: str
    visit_frequency: int
    avg_dwell_ms: float
    normalized_score: float


class HeatmapResponse(BaseModel):
    store_id: str
    zones: list[HeatmapZone]
    data_confidence: str


class AnomalySeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class Anomaly(BaseModel):
    anomaly_type: str
    severity: AnomalySeverity
    message: str
    suggested_action: str
    detected_at: datetime


class AnomaliesResponse(BaseModel):
    store_id: str
    anomalies: list[Anomaly]


class StoreHealth(BaseModel):
    store_id: str
    last_event_at: datetime | None
    is_stale: bool


class HealthResponse(BaseModel):
    status: str
    stores: list[StoreHealth]
    warnings: list[str] = Field(default_factory=list)
