from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import FastAPI
from src.shared.cache import close_redis

logger = logging.getLogger("app.audit")
_logger = logging.getLogger("app")


@dataclass(frozen=True)
class AuditEvent:
    event_type: Literal[
        "UserCreated",
        "LoginSuccess",
        "LoginFailure",
        "PasswordChanged",
        "RoleChanged",
    ]
    tenant_id: Optional[UUID]
    user_id: Optional[UUID]
    subject_user_id: Optional[UUID] = None
    metadata: dict | None = None
    at: datetime = datetime.utcnow()

def emit_audit(event: AuditEvent) -> None:
    # Structured log with tenant_id/user_id as required by policies
    logger.info(
        "audit_event",
        extra={
            "event_type": event.event_type,
            "tenant_id": str(event.tenant_id) if event.tenant_id else None,
            "user_id": str(event.user_id) if event.user_id else None,
            "subject_user_id": str(event.subject_user_id) if event.subject_user_id else None,
            "metadata": event.metadata or {},
            "at": event.at.isoformat(),
        },
    )

# ============================
# Stage-2: Redis lifecycle hook
# ============================

def register_cache_shutdown(app: FastAPI) -> None:
    """
    Registers a FastAPI shutdown event to gracefully close the Redis connection.
    Safe to call multiple times (FastAPI dedupes handlers by function object).
    """
    @app.on_event("shutdown")
    async def _close_redis_on_shutdown() -> None:
        try:
            await close_redis()
            _logger.info("redis_connection_closed")
        except Exception as exc:  # pragma: no cover (best-effort cleanup)
            _logger.warning("redis_close_failed", extra={"error": str(exc)})
