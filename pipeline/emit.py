from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.models import EventMetadata, EventType, StoreEvent


@dataclass
class EventEmitter:
    store_id: str
    session_counters: dict[str, int] = field(default_factory=dict)

    def _next_session_seq(self, visitor_id: str) -> int:
        self.session_counters[visitor_id] = self.session_counters.get(visitor_id, 0) + 1
        return self.session_counters[visitor_id]

    def create_event(
        self,
        *,
        camera_id: str,
        visitor_id: str,
        event_type: EventType,
        timestamp: datetime,
        zone_id: str | None = None,
        dwell_ms: int = 0,
        is_staff: bool = False,
        confidence: float = 0.85,
        queue_depth: int | None = None,
        sku_zone: str | None = None,
    ) -> StoreEvent:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return StoreEvent(
            event_id=uuid.uuid4(),
            store_id=self.store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            event_type=event_type,
            timestamp=timestamp,
            zone_id=zone_id,
            dwell_ms=dwell_ms,
            is_staff=is_staff,
            confidence=confidence,
            metadata=EventMetadata(
                queue_depth=queue_depth,
                sku_zone=sku_zone or zone_id,
                session_seq=self._next_session_seq(visitor_id),
            ),
        )

    def write_jsonl(self, events: list[StoreEvent], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            for event in events:
                payload = event.model_dump(mode="json")
                payload["timestamp"] = event.timestamp.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                handle.write(json.dumps(payload) + "\n")

    @staticmethod
    def iter_jsonl(path: Path) -> Iterator[StoreEvent]:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield StoreEvent.model_validate_json(line)
