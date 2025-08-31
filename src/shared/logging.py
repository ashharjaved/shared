# src/shared/logging.py
from __future__ import annotations

import logging
import os
from typing import Any, Optional


def _build_logger(name: str = "app") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(level)

    handler = logging.StreamHandler()
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


_logger = _build_logger("identity")


def log_event(event: str, *, tenant_id: Optional[str] = None, user_id: Optional[str] = None,
              correlation_id: Optional[str] = None, **fields: Any) -> None:
    """
    Structured event logger—safe for audit. Keep payloads non-PHI.
    """
    payload = {
        "event": event,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "correlation_id": correlation_id,
    }
    payload.update({k: v for k, v in fields.items() if v is not None})
    _logger.info(payload)  # JSON logging can be added by swapping formatter/handler

def _emit_security_event(payload: dict[str, Any]) -> None:
    # central place to actually emit the log (sync)
    _logger.info(payload)

async def log_security_event(
    *,
    event: str,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    correlation_id: Optional[str] = None,
    reason: Optional[str] = None,
    **fields: Any,
) -> None:
    """
    Awaitable security event logger (safe: no secrets/PHI).
    """
    payload = {
        "event": event,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email,
        "reason": reason,
        "correlation_id": correlation_id,
        **{k: v for k, v in fields.items() if v is not None},
    }
    _emit_security_event(payload)