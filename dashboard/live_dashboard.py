#!/usr/bin/env python3
"""Terminal dashboard showing live store metrics."""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import httpx
from rich.console import Console
from rich.live import Live
from rich.table import Table


def build_table(store_id: str, metrics: dict, health: dict) -> Table:
    table = Table(title=f"Store Intelligence Dashboard — {store_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Unique Visitors", str(metrics.get("unique_visitors", 0)))
    table.add_row("Converted Visitors", str(metrics.get("converted_visitors", 0)))
    table.add_row("Conversion Rate", f"{metrics.get('conversion_rate', 0) * 100:.2f}%")
    table.add_row("Queue Depth", str(metrics.get("current_queue_depth", 0)))
    table.add_row("Abandonment Rate", f"{metrics.get('queue_abandonment_rate', 0) * 100:.2f}%")
    table.add_row("API Status", health.get("status", "unknown"))
    table.add_row("Updated At", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    return table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--store-id", default="STORE_BLR_002")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    console = Console()
    with httpx.Client(timeout=10.0) as client, Live(console=console, refresh_per_second=1) as live:
        while True:
            metrics = client.get(f"{args.api_url}/stores/{args.store_id}/metrics").json()
            health = client.get(f"{args.api_url}/health").json()
            live.update(build_table(args.store_id, metrics, health))
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
