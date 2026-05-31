#!/usr/bin/env python3
"""Link root-level CCTV files into data/clips/ with camera-aware names."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIPS_DIR = ROOT / "data" / "clips"
EXTRA_DIR = CLIPS_DIR / "extra"

# Brigade Bangalore: CAM 1=entry, CAM 2=floor, CAM 3=billing
CAMERA_MAP = {
    "CAM 1.mp4": ("STORE_BLR_002_entry.mp4", "CAM_ENTRY_01"),
    "CAM 2.mp4": ("STORE_BLR_002_floor.mp4", "CAM_FLOOR_01"),
    "CAM 3.mp4": ("STORE_BLR_002_billing.mp4", "CAM_BILLING_01"),
    "CAM 4.mp4": ("extra/CAM_4_floor_alt.mp4", "CAM_FLOOR_01"),
    "CAM 5.mp4": ("extra/CAM_5_billing_alt.mp4", "CAM_BILLING_01"),
}


def link_clip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    target.symlink_to(source.resolve())


def setup(use_extras: bool = False) -> list[tuple[str, str]]:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    linked: list[tuple[str, str]] = []

    for source_name, (target_name, camera_id) in CAMERA_MAP.items():
        if not use_extras and target_name.startswith("extra/"):
            continue
        source = ROOT / source_name
        if not source.exists():
            continue
        target = CLIPS_DIR / target_name
        link_clip(source, target)
        linked.append((target_name, camera_id))
        print(f"Linked {source_name} -> data/clips/{target_name} ({camera_id})")

    return linked


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-extras",
        action="store_true",
        help="Also link CAM 4 and CAM 5 (may duplicate visitor counts)",
    )
    args = parser.parse_args()
    result = setup(use_extras=args.include_extras)
    if not result:
        print("No CAM *.mp4 files found in project root.")
    else:
        print(f"Ready: {len(result)} clip(s) in data/clips/")
