from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass
class AuditEntry:
    """Append-only domain audit entry (domain-side shape; persistence elsewhere)."""
    tenant_id: UUID
    resource: str            # e.g., "user", "tenant", "plan"
    resource_id: str         # UUID or composite natural key as string
    action: str              # e.g., "create", "update", "deactivate"
    actor_id: Optional[UUID] # may be None for system actions
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)
    
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        from src.shared.errors import ValidationError
        if not (self.resource or "").strip():
            raise ValidationError("AuditEntry.resource cannot be empty")
        if not (self.action or "").strip():
            raise ValidationError("AuditEntry.action cannot be empty")
        if not isinstance(self.before, dict) or not isinstance(self.after, dict):
            raise ValidationError("AuditEntry.before/after must be dicts")
        if self.resource_id and not isinstance(self.resource_id, str):
            raise ValidationError("AuditEntry.resource_id must be a string")