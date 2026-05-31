from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
logger = logging.getLogger("store_intelligence.access")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
        trace_id_var.set(trace_id)
        start = time.perf_counter()
        status_code = 500
        event_count = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            store_id = request.path_params.get("id", "-")
            if request.url.path.endswith("/ingest"):
                event_count = request.headers.get("X-Event-Count", "-")
            logger.info(
                "request_completed",
                extra={
                    "trace_id": trace_id,
                    "store_id": store_id,
                    "endpoint": request.url.path,
                    "latency_ms": latency_ms,
                    "event_count": event_count,
                    "status_code": status_code,
                },
            )
