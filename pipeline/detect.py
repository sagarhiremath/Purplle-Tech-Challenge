from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

from app.models import EventType
from pipeline.emit import EventEmitter
from pipeline.tracker import CentroidTracker

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_ID = "STORE_BLR_002"

ZONE_BY_X = [
    (0.0, 0.2, "ENTRY"),
    (0.2, 0.35, "GOOD_VIBES"),
    (0.35, 0.5, "DERMDOC"),
    (0.5, 0.65, "MAKEUP_UNIT"),
    (0.65, 0.8, "FRAGRANCE"),
    (0.8, 1.0, "BILLING"),
]


def zone_from_position(x_norm: float) -> str:
    for start, end, zone in ZONE_BY_X:
        if start <= x_norm < end:
            return zone
    return "MAKEUP_UNIT"


def detect_people(frame: np.ndarray, bg_subtractor) -> list[tuple[float, float, float]]:
    mask = bg_subtractor.apply(frame)
    mask = cv2.medianBlur(mask, 5)
    _, thresh = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    height, width = frame.shape[:2]
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 800:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        cx = x + w / 2
        cy = y + h / 2
        confidence = min(0.99, area / (width * height) * 20)
        detections.append((cx, cy, confidence))
    return detections


def process_video(
    video_path: Path,
    camera_id: str,
    store_id: str,
    clip_start: datetime,
    fps: float,
    frame_skip: int = 5,
) -> list:
    emitter = EventEmitter(store_id=store_id)
    tracker = CentroidTracker()
    events = []
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    frame_idx = 0
    active_zones: dict[int, str] = {}
    dwell_start: dict[int, datetime] = {}
    seen_direction: set[int] = set()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        if frame_idx % frame_skip != 0:
            continue

        timestamp = clip_start + timedelta(seconds=frame_idx / max(fps, 1))
        detections = detect_people(frame, bg_subtractor)
        tracks = tracker.update(detections)
        height, width = frame.shape[:2]

        for track_id, track in tracks.items():
            visitor_id = tracker.assign_visitor_id(track_id)
            x_norm = track.centroid[0] / width
            zone = zone_from_position(x_norm)
            is_staff = tracker.infer_staff(track, uniform_region_hits=0)

            if camera_id == "CAM_ENTRY_01" and track_id not in seen_direction:
                direction = tracker.detect_direction(track, axis="x", inbound_positive=True)
                if direction == "inbound":
                    events.append(
                        emitter.create_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=EventType.ENTRY,
                            timestamp=timestamp,
                            zone_id="ENTRY",
                            is_staff=is_staff,
                            confidence=min(0.99, track.frames_seen / 20),
                        )
                    )
                    seen_direction.add(track_id)
                elif direction == "outbound":
                    events.append(
                        emitter.create_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=EventType.EXIT,
                            timestamp=timestamp,
                            zone_id="ENTRY",
                            is_staff=is_staff,
                            confidence=min(0.99, track.frames_seen / 20),
                        )
                    )
                    seen_direction.add(track_id)

            previous_zone = active_zones.get(track_id)
            if previous_zone != zone:
                if previous_zone:
                    events.append(
                        emitter.create_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=EventType.ZONE_EXIT,
                            timestamp=timestamp,
                            zone_id=previous_zone,
                            is_staff=is_staff,
                            confidence=0.8,
                        )
                    )
                events.append(
                    emitter.create_event(
                        camera_id=camera_id,
                        visitor_id=visitor_id,
                        event_type=EventType.ZONE_ENTER,
                        timestamp=timestamp,
                        zone_id=zone,
                        is_staff=is_staff,
                        confidence=0.82,
                    )
                )
                active_zones[track_id] = zone
                dwell_start[track_id] = timestamp
            else:
                started = dwell_start.get(track_id, timestamp)
                dwell_ms = int((timestamp - started).total_seconds() * 1000)
                if dwell_ms >= 30000 and dwell_ms % 30000 < int(1000 / max(fps, 1)):
                    events.append(
                        emitter.create_event(
                            camera_id=camera_id,
                            visitor_id=visitor_id,
                            event_type=EventType.ZONE_DWELL,
                            timestamp=timestamp,
                            zone_id=zone,
                            dwell_ms=30000,
                            is_staff=is_staff,
                            confidence=0.75,
                        )
                    )

    cap.release()
    return events


def resolve_camera_id(path: Path) -> str:
    name = path.stem.lower().replace("_", " ").replace("-", " ")

    if "entry" in name or name in {"cam 1", "cam1"}:
        return "CAM_ENTRY_01"
    if "billing" in name or name in {"cam 3", "cam3"}:
        return "CAM_BILLING_01"
    if "floor" in name or name in {"cam 2", "cam2"}:
        return "CAM_FLOOR_01"
    if name in {"cam 4", "cam4"}:
        return "CAM_FLOOR_01"
    if name in {"cam 5", "cam5"}:
        return "CAM_BILLING_01"
    return "CAM_FLOOR_01"


def discover_clips(clips_dir: Path, include_extras: bool = False) -> list[tuple[Path, str, str]]:
    clips = []
    if not clips_dir.exists():
        return clips
    for path in sorted(clips_dir.rglob("*")):
        if path.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv"}:
            continue
        if not include_extras and "extra" in path.parts:
            continue
        camera_id = resolve_camera_id(path)
        clips.append((path, camera_id, DEFAULT_STORE_ID))
    return clips


def main() -> None:
    parser = argparse.ArgumentParser(description="Process CCTV clips into structured events")
    parser.add_argument("--clips-dir", type=Path, default=ROOT / "data" / "clips")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "generated_events.jsonl")
    parser.add_argument("--store-id", default=DEFAULT_STORE_ID)
    parser.add_argument("--clip-date", default="2026-04-10T10:00:00Z")
    parser.add_argument("--frame-skip", type=int, default=5)
    args = parser.parse_args()

    clip_start = datetime.fromisoformat(args.clip_date.replace("Z", "+00:00"))
    all_events = []
    clips = discover_clips(args.clips_dir)

    if not clips:
        print("No video clips found. Run pipeline/demo_generator.py instead.")
        return

    for video_path, camera_id, store_id in clips:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
        cap.release()
        print(f"Processing {video_path.name} ({camera_id})")
        events = process_video(
            video_path, camera_id, store_id, clip_start, fps, args.frame_skip
        )
        all_events.extend(events)

    all_events.sort(key=lambda item: item.timestamp)
    emitter = EventEmitter(store_id=args.store_id)
    emitter.write_jsonl(all_events, args.output)
    print(f"Wrote {len(all_events)} events to {args.output}")


if __name__ == "__main__":
    main()
