from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


_E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


class MessageDirection(str, Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"

    @classmethod
    def is_valid_transition(cls, old: "MessageStatus", new: "MessageStatus") -> bool:
        """Domain-level guard; DB proc enforces again for safety."""
        allowed = {
            cls.QUEUED: {cls.SENT, cls.FAILED},
            cls.SENT: {cls.DELIVERED, cls.FAILED},
            cls.DELIVERED: {cls.READ},
            cls.READ: set(),   # terminal
            cls.FAILED: set(), # terminal (retry logic lives in app/worker layers)
        }
        return new in allowed.get(old, set())


@dataclass(frozen=True)
class PhoneNumber:
    """
    E.164 phone number value object.

    - Always stores as canonical E.164 with leading '+'.
    - Validation is strict here; infra/DB have additional CHECK constraints.
    """
    e164: str

    def __post_init__(self) -> None:
        if not _E164_PATTERN.match(self.e164):
            raise ValueError(f"Invalid E.164 phone number: {self.e164}")

    def __str__(self) -> str:
        return self.e164


@dataclass(frozen=True)
class Message:
    """
    Domain entity representing a WhatsApp message (inbound or outbound).

    Notes:
    - content is a JSON-like dict (text/template/media payloads).
    - whatsapp_message_id is provider ID once known (None until actual send).
    - created_at is used for DB partitioning; domain treats it as data.
    """

    id: UUID
    tenant_id: UUID
    channel_id: UUID

    from_phone: PhoneNumber
    to_phone: PhoneNumber

    content: Dict[str, Any]
    message_type: str  # "text" | "template" | "media" (kept open; validated upstream)
    direction: MessageDirection
    status: MessageStatus = MessageStatus.QUEUED

    whatsapp_message_id: Optional[str] = None
    error_code: Optional[str] = None
    retry_count: int = 0

    created_at: Optional[datetime] = None
    status_updated_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def with_status(self, new_status: MessageStatus) -> "Message":
        """
        Return a *new* Message with an updated status if transition is legal.
        Domain remains immutable (dataclass frozen=True).
        """
        if not MessageStatus.is_valid_transition(self.status, new_status):
            raise ValueError(f"Illegal message status transition: {self.status} -> {new_status}")

        now = datetime.utcnow()
        delivered_at = self.delivered_at
        if new_status == MessageStatus.DELIVERED and delivered_at is None:
            delivered_at = now

        return replace(self, status=new_status, status_updated_at=now, delivered_at=delivered_at)

    def is_outbound(self) -> bool:
        return self.direction == MessageDirection.OUTBOUND

    def is_inbound(self) -> bool:
        return self.direction == MessageDirection.INBOUND
