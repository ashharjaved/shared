"""
Structured logging using structlog with:
- JSON/console switchable format
- Correlation ID + request context
- PII redaction (emails, E.164 phones/MSISDN, cards, SSN)
- Safe defaults for Uvicorn/SQLAlchemy/Alembic
- Tiny helpers for FastAPI middleware and perf timing

"""

from __future__ import annotations

import contextlib
import logging
import logging.config
import os
import re
import sys
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Union

import structlog
from pythonjsonlogger import jsonlogger

from src.shared.config import get_settings

# ---------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------


class PIIRedactionProcessor:
    """
    Structlog processor to redact PII from strings inside event_dict (recursively).
    - Email: keep domain, redact local-part.
    - Phone/MSISDN (E.164 preferred): keep CC and last 4.
    - Credit card/SSN: full redact.
    """
    # Reasonable patterns; avoid over-matching app IDs/tokens.
    P_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
    # E.164: + followed by 8..15 digits (allow common separators lightly)
    P_MSISDN = re.compile(r"\+?[1-9]\d{7,14}")
    # US-ish formats; kept to catch logs from 3P libs; we still treat as phone
    P_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    P_CC = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
    P_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def __call__(self, logger, method_name, event_dict):
        return self._redact(event_dict)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._redact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact(v) for v in value]
        if isinstance(value, str):
            return self._redact_str(value)
        return value

    def _redact_str(self, s: str) -> str:
        # Emails: mask local-part
        s = self.P_EMAIL.sub(lambda m: f"***@{m.group(2)}", s)
        # Phones/MSISDN: prefer E.164; if not matched, fallback phone
        def _mask_msisdn(m: re.Match) -> str:
            g = m.group(0)
            return f"{g[:2]}****{g[-4:]}" if len(g) >= 6 else "***"
        s = self.P_MSISDN.sub(_mask_msisdn, s)
        s = self.P_PHONE.sub(_mask_msisdn, s)
        # Cards/SSN: full redact
        s = self.P_CC.sub("***REDACTED***", s)
        s = self.P_SSN.sub("***REDACTED***", s)
        return s


# ---------------------------------------------------------------------
# Context processors
# ---------------------------------------------------------------------


class CorrelationIdProcessor:
    """Attach correlation_id from structlog contextvars into each event."""
    def __call__(self, logger, method_name, event_dict):
        ctx = structlog.contextvars.get_contextvars()  # Updated to get_contextvars
        cid = ctx.get("correlation_id")
        if cid:
            event_dict["correlation_id"] = cid
        return event_dict


def add_request_context(logger, method_name, event_dict):
    """
    Copy a few standard request fields from contextvars into the event.
    You can bind more via `bind_request_context(...)` during request handling.
    """
    ctx = structlog.contextvars.get_contextvars()
    for key in ("user_id", "tenant_id", "path", "method", "status_code", "client_ip"):
        if key in ctx:
            event_dict[key] = ctx[key]
    return event_dict


def add_timestamp(logger, method_name, event_dict):
    # UTC ISO8601 Z
    import datetime
    event_dict["timestamp"] = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return event_dict


# ---------------------------------------------------------------------
# Public helpers to use from API/worker code
# ---------------------------------------------------------------------


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Generate/bind a correlation_id if not provided; returns the id."""
    cid = correlation_id or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def bind_request_context(
    *,
    request_id: Optional[str] = None,
    path: Optional[str] = None,
    method: Optional[str] = None,
    status_code: Optional[int] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    roles: Optional[Union[str, List[str]]] = None,
    client_ip: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> None:
    """Bind standard request context fields (call in middleware/route handlers)."""
    payload = {
            k: v
            for k, v in dict(
                request_id=request_id,
                path=path,
                method=method,
                status_code=status_code,
                user_id=user_id,
                tenant_id=tenant_id,
                roles=roles,
                client_ip=client_ip,
            ).items()
            if v is not None
        }
    if extras:
        payload.update(extras)
    if payload:
        structlog.contextvars.bind_contextvars(**payload)


def clear_request_context() -> None:
    """Clear all bound contextvars (call at end of request/worker job)."""
    structlog.contextvars.clear_contextvars()


@contextlib.contextmanager
def time_block(name: str, *, logger: Optional[structlog.stdlib.BoundLogger] = None, labels: Optional[Dict[str, str]] = None):
    """
    Context manager to time a block and log as a performance metric.
    Usage:
        with time_block("db.query", logger=log, labels={"model":"User"}):
            await repo.fetch(...)
    """
    _log = logger or structlog.get_logger("performance")
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        _log.info("Performance metric", metric_name=name, value=ms, unit="ms", labels=labels or {})


# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------

def _ensure_log_format(settings) -> str:
    """
    Determine output format:
      - If settings has .log_format, use it ("json"|"console").
      - Else default: "console" for local/dev, "json" for staging/prod.
    """
    fmt = getattr(settings, "log_format", None)
    if fmt in ("json", "console"):
        return fmt
    return "console" if getattr(settings, "is_local", False) or getattr(settings, "is_dev", False) else "json"


def _level_name_to_int(level: str) -> int:
    return getattr(logging, level.upper(), logging.INFO)


def setup_logging() -> None:
    """Idempotent structured logging configuration."""
    settings = get_settings()
    log_format = _ensure_log_format(settings)
    is_prod_like = getattr(settings, "is_prod", False) or getattr(settings, "is_staging", False)

    # Python stdlib logging config
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger,
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            },
            "console": {
                "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if log_format == "json" else "console",
                "stream": sys.stdout,
            },
        },
        "root": {
            "level": _level_name_to_int(getattr(settings, "log_level", "INFO")),
            "handlers": ["console"],
        },
        "loggers": {
            # Quiet noisy libs, but keep errors
            "uvicorn.error": {"level": "INFO", "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "sqlalchemy.engine": {
                "level": "WARNING" if is_prod_like else "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "alembic": {"level": "INFO", "handlers": ["console"], "propagate": False},
        },
    }
    logging.config.dictConfig(logging_config)

    # structlog processors pipeline
    processors: Iterable[Any] = [
        structlog.contextvars.merge_contextvars,
        add_timestamp,
        add_request_context,
        CorrelationIdProcessor(),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        # Redact only outside of local/dev to help debugging locally
        (PIIRedactionProcessor() if is_prod_like else (lambda *_: _[-1])),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Renderer
        (structlog.processors.JSONRenderer() if log_format == "json" else structlog.dev.ConsoleRenderer()),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )

    # Clear any inherited context
    structlog.contextvars.clear_contextvars()

    # Optional: wire stdlib → structlog so `logging.getLogger().info(...)` also becomes JSON
    # Comment out if you prefer raw stdlib formatting only.
    structlog.stdlib.recreate_defaults()  # safe reset to avoid double-config in reloads


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Named loggers for common domains
security_logger = structlog.get_logger("security")
performance_logger = structlog.get_logger("performance")


def log_security_event(
    event_type: str,
    *,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """Log security-relevant events (authz changes, login, policy hits, etc.)."""
    security_logger.info(
        "Security event",
        event_type=event_type,
        user_id=user_id,
        tenant_id=tenant_id,
        details=details or {},
        **kwargs,
    )


def log_performance_metric(
    metric_name: str,
    value: float,
    unit: str = "ms",
    labels: Optional[Dict[str, str]] = None,
    **kwargs: Any,
) -> None:
    """Log numeric performance metrics; prefer ms for latency."""
    performance_logger.info(
        "Performance metric",
        metric_name=metric_name,
        value=value,
        unit=unit,
        labels=labels or {},
        **kwargs,
    )