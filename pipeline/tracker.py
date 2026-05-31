from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Track:
    track_id: int
    centroid: tuple[float, float]
    history: list[tuple[float, float]] = field(default_factory=list)
    frames_seen: int = 0
    is_staff: bool = False

    def update(self, centroid: tuple[float, float]) -> None:
        self.history.append(self.centroid)
        self.centroid = centroid
        self.frames_seen += 1


class CentroidTracker:
    """Lightweight centroid tracker for entry/exit and zone movement."""

    def __init__(self, max_distance: float = 80.0) -> None:
        self.max_distance = max_distance
        self.tracks: dict[int, Track] = {}
        self._next_id = 1
        self._reid_map: dict[int, str] = {}

    def _distance(self, a: tuple[float, float], b: tuple[float, float]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def update(self, detections: list[tuple[float, float, float]]) -> dict[int, Track]:
        assigned: set[int] = set()
        for x, y, confidence in detections:
            centroid = (x, y)
            best_id = None
            best_distance = self.max_distance
            for track_id, track in self.tracks.items():
                if track_id in assigned:
                    continue
                distance = self._distance(track.centroid, centroid)
                if distance < best_distance:
                    best_distance = distance
                    best_id = track_id
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
                self.tracks[best_id] = Track(track_id=best_id, centroid=centroid)
            else:
                self.tracks[best_id].update(centroid)
            assigned.add(best_id)
        return self.tracks

    def assign_visitor_id(self, track_id: int, prefix: str = "VIS") -> str:
        if track_id not in self._reid_map:
            self._reid_map[track_id] = f"{prefix}_{track_id:04x}"
        return self._reid_map[track_id]

    def detect_direction(
        self, track: Track, axis: str = "x", inbound_positive: bool = True
    ) -> str | None:
        if len(track.history) < 5:
            return None
        start = track.history[-5]
        end = track.centroid
        delta = end[0] - start[0] if axis == "x" else end[1] - start[1]
        if abs(delta) < 8:
            return None
        if inbound_positive:
            return "inbound" if delta > 0 else "outbound"
        return "inbound" if delta < 0 else "outbound"

    def infer_staff(self, track: Track, uniform_region_hits: int) -> bool:
        return uniform_region_hits >= 3 or track.frames_seen > 900
