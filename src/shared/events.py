from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

logger = logging.getLogger("app.audit")

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
