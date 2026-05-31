from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'store_intelligence.db'}")
STORE_LAYOUT_PATH = Path(os.getenv("STORE_LAYOUT_PATH", DATA_DIR / "store_layout.json"))
POS_TRANSACTIONS_PATH = Path(
    os.getenv("POS_TRANSACTIONS_PATH", DATA_DIR / "pos_transactions.csv")
)
STALE_FEED_THRESHOLD_SECONDS = int(os.getenv("STALE_FEED_THRESHOLD_SECONDS", "600"))
CONVERSION_WINDOW_SECONDS = int(os.getenv("CONVERSION_WINDOW_SECONDS", "300"))
DEFAULT_STORE_ID = os.getenv("DEFAULT_STORE_ID", "STORE_BLR_002")
