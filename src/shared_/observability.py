# /src/shared/observability.py
"""
Observability utilities:
- Time utils: monotonic(), duration_ms(start)
- Health checks: db_healthcheck(), redis_healthcheck()
- Prometheus metrics: optional (if 'prometheus_client' installed)
- OTel spans: optional (if 'opentelemetry' installed) with no hard dependency

All exports are safe no-ops if optional libs are not installed.
"""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, Dict, Optional

from shared_.cache.redis import get_redis

from .structured_logging import get_logger

_log = get_logger("obs")

# ---------- time utils ----------------------------------------------------------------

def monotonic() -> float:
    """High-resolution monotonic clock (seconds)."""
    return perf_counter()

def duration_ms(start: float) -> float:
    """Return milliseconds elapsed since 'start' (perf_counter value)."""
    return (perf_counter() - start) * 1000.0

# ---------- health checks --------------------------------------------------------------

async def db_healthcheck() -> Dict[str, Any]:
    """
    Executes a cheap 'SELECT 1' using the existing engine.
    """
    try:
        from sqlalchemy import text
        from .database.database import get_session_factory
        factory = get_session_factory()
        async with factory() as s:  # type: ignore[call-arg]
            res = await s.execute(text("SELECT 1"))
            ok = res.scalar_one_or_none() == 1
            return {"db": "ok" if ok else "degraded"}
    except Exception as e:
        _log.warning("db_healthcheck_failed", error=str(e))
        return {"db": "down", "reason": str(e)}

async def redis_healthcheck() -> Dict[str, Any]:
    try:
        pong = await get_redis()
        return {"redis": "ok" if pong else "degraded"}
    except Exception as e:
        _log.warning("redis_healthcheck_failed", error=str(e))
        return {"redis": "down", "reason": str(e)}

# ---------- Prometheus (optional) ------------------------------------------------------

from typing import Optional

# ---------- Prometheus (optional) ------------------------------------------------------

try:
    from prometheus_client import Counter, Histogram  # type: ignore
    PROM_AVAILABLE = True
except Exception:
    PROM_AVAILABLE = False
    Counter = Gauge = Histogram = None  # type: ignore

REQUESTS_TOTAL: Optional[Counter] = Counter("requests_total", "HTTP requests", ["route", "method"]) if PROM_AVAILABLE else None  # type: ignore[call]
REQUEST_LATENCY_MS: Optional[Histogram] = Histogram("request_latency_ms", "HTTP request latency (ms)", ["route", "method"]) if PROM_AVAILABLE else None  # type: ignore[call]

def inc_requests(route: str, method: str) -> None:
    if REQUESTS_TOTAL is not None:
        assert REQUESTS_TOTAL is not None  # Type narrowing
        REQUESTS_TOTAL.labels(route=route, method=method).inc()

def observe_latency(route: str, method: str, ms: float) -> None:
    if REQUEST_LATENCY_MS is not None:
        assert REQUEST_LATENCY_MS is not None  # Type narrowing
        REQUEST_LATENCY_MS.labels(route=route, method=method).observe(ms)
# ---------- OpenTelemetry (optional) ---------------------------------------------------

class _Span:
    def __init__(self, tracer, name: str):
        self._tracer = tracer
        self._name = name
        self._span = None

    def __enter__(self):
        if self._tracer:
            self._span = self._tracer.start_as_current_span(self._name).__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._tracer and self._span:
            self._tracer.start_as_current_span  # keep reference to avoid lints
            self._span.__exit__(exc_type, exc, tb)

def tracer():
    try:
        from opentelemetry import trace  # type: ignore
        return trace.get_tracer("shared")
    except Exception:
        return None

def start_span(name: str):
    """
    Context manager:
        with start_span("work"):
            ...
    Works as no-op if OTel is not installed.
    """
    return _Span(tracer(), name)
