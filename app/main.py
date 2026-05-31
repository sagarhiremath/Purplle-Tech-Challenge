from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.anomalies import compute_health, detect_anomalies
from app.database import get_db, init_db
from app.funnel import compute_funnel
from app.heatmap import compute_heatmap
from app.ingestion import ingest_events, seed_pos_transactions
from app.logging_middleware import StructuredLoggingMiddleware
from app.metrics import compute_metrics
from app.models import (
    AnomaliesResponse,
    FunnelResponse,
    HealthResponse,
    HeatmapResponse,
    IngestRequest,
    IngestResponse,
    MetricsResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).resolve().parent / "static" / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = next(get_db())
    try:
        seeded = seed_pos_transactions(db)
        logger.info("Seeded %s POS transactions", seeded)
    finally:
        db.close()
    yield


app = FastAPI(title="Store Intelligence API", version="1.0.0", lifespan=lifespan)
app.add_middleware(StructuredLoggingMiddleware)

if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard/static",
        StaticFiles(directory=DASHBOARD_DIR),
        name="dashboard-static",
    )


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api", include_in_schema=False)
def api_index():
    return {
        "service": "Store Intelligence API",
        "store_id": "STORE_BLR_002",
        "endpoints": {
            "dashboard": "/dashboard",
            "docs": "/docs",
            "health": "/health",
            "metrics": "/stores/STORE_BLR_002/metrics",
            "funnel": "/stores/STORE_BLR_002/funnel",
            "heatmap": "/stores/STORE_BLR_002/heatmap",
            "anomalies": "/stores/STORE_BLR_002/anomalies",
        },
    }


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error")
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_unavailable",
            "message": "Database is temporarily unavailable. Please retry.",
        },
    )


@app.post("/events/ingest", response_model=IngestResponse)
def post_events_ingest(
    payload: IngestRequest,
    db: Session = Depends(get_db),
) -> IngestResponse:
    if len(payload.events) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 events per batch")
    return ingest_events(db, payload)


@app.get("/stores/{store_id}/metrics", response_model=MetricsResponse)
def get_store_metrics(
    store_id: str,
    day: date | None = None,
    db: Session = Depends(get_db),
) -> MetricsResponse:
    return compute_metrics(db, store_id, day)


@app.get("/stores/{store_id}/funnel", response_model=FunnelResponse)
def get_store_funnel(
    store_id: str,
    day: date | None = None,
    db: Session = Depends(get_db),
) -> FunnelResponse:
    return compute_funnel(db, store_id, day)


@app.get("/stores/{store_id}/heatmap", response_model=HeatmapResponse)
def get_store_heatmap(
    store_id: str,
    day: date | None = None,
    db: Session = Depends(get_db),
) -> HeatmapResponse:
    return compute_heatmap(db, store_id, day)


@app.get("/stores/{store_id}/anomalies", response_model=AnomaliesResponse)
def get_store_anomalies(store_id: str, db: Session = Depends(get_db)) -> AnomaliesResponse:
    return detect_anomalies(db, store_id)


@app.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    return compute_health(db)
