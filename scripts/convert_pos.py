#!/usr/bin/env python3
"""Convert Brigade POS CSV to challenge pos_transactions.csv format."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BRIGADE_CSV = ROOT / "data" / "brigade_pos.csv"
if not BRIGADE_CSV.exists():
    BRIGADE_CSV = ROOT / "Brigade_Bangalore_10_April_26 (1)bc6219c.csv"
OUTPUT_CSV = ROOT / "data" / "pos_transactions.csv"
STORE_ID = "STORE_BLR_002"


def convert() -> None:
    df = pd.read_csv(BRIGADE_CSV)
    grouped = (
        df.groupby("order_id")
        .agg(
            {
                "order_date": "first",
                "order_time": "first",
                "total_amount": "sum",
            }
        )
        .reset_index()
    )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["store_id", "transaction_id", "timestamp", "basket_value_inr"])
        for _, row in grouped.iterrows():
            dt = datetime.strptime(
                f"{row['order_date']} {row['order_time']}", "%d-%m-%Y %H:%M:%S"
            )
            writer.writerow(
                [
                    STORE_ID,
                    f"TXN_{int(row['order_id'])}",
                    dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    f"{row['total_amount']:.2f}",
                ]
            )
    print(f"Wrote {len(grouped)} transactions to {OUTPUT_CSV}")


if __name__ == "__main__":
    convert()
