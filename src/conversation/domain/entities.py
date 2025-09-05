#*** Begin: src/conversation/domain/entities.py ***
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from .value_objects import MenuDefinition, PhoneNumber, SessionStatus, JSONValue


@dataclass(slots=True)
class MenuFlow:
    """
    Tenant-scoped flow: a named, versioned menu tree with an optional default flag.
    Note: actual routing/action semantics are handled by the application service.
    """
    id: UUID
    tenant_id: UUID
    name: str
    industry_type: str
    version: int
    is_active: bool
    is_default: bool
    definition: MenuDefinition

    created_by: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    def assert_active(self) -> None:
        if not self.is_active:
            raise ValueError("menu flow is not active")

    def main_menu_key(self) -> str:
        # Convention: main entry point is "main"
        return "main"


@dataclass(slots=True)
class ConversationSession:
    """
    Session state for a (channel_id, phone_number). TTL is enforced in DB.
    """
    id: UUID
    tenant_id: UUID
    channel_id: UUID
    phone_number: PhoneNumber

    current_menu_id: Optional[UUID]
    status: SessionStatus
    expires_at: datetime
    last_activity: datetime | None
    message_count: int
    context: Dict[str, JSONValue] = field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # --- domain behaviors (lightweight) ---
    def mark_expired(self) -> None:
        self.status = SessionStatus.EXPIRED

    def set_current_menu(self, menu_id: Optional[UUID]) -> None:
        self.current_menu_id = menu_id

    def bump_message_count(self) -> None:
        self.message_count += 1

    def put_context(self, key: str, value: JSONValue) -> None:
        self.context[key] = value
