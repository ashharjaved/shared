# src/identity/domain/events/user_events.py
"""
Domain events related to user lifecycle and authentication.

All events are immutable and contain complete data needed by downstream systems.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from ..types import UserId, TenantId

from typing import Mapping, Optional, Sequence

from ._base import EventBase

@dataclass(frozen=True, slots=True)
class UserInvited(EventBase):
    user_id: UserId = UserId(uuid4())
    email: str = field(default="")
    invited_by: Optional[UserId] = None

    @classmethod
    def create(cls, *, tenant_id: TenantId, user_id: UserId, email: str,
               invited_by: Optional[UserId] = None,
               correlation_id: Optional[str] = None,
               causation_id: Optional[str] = None,
               metadata: Optional[Mapping[str, Any]] = None) -> "UserInvited":
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            email=email,
            invited_by=invited_by,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=metadata or {},
        )


@dataclass(frozen=True, slots=True)
class UserRegistered(EventBase):
    id: UUID = UserId(uuid4()) # Backward-compat if you already used `id`
    user_id: UserId = UserId(uuid4())
    email: str = field(default="")
    roles: Sequence[str] = field(default_factory=tuple)
    phone: Optional[str] = None
    registration_source: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.email.strip():
            raise ValueError("Email cannot be empty")
        if not self.roles:
            raise ValueError("At least one role must be assigned")

    @classmethod
    def create(cls, *, tenant_id: TenantId, user_id: UserId, email: str,
               roles: Sequence[str],
               phone: Optional[str] = None,
               registration_source: Optional[str] = None,
               correlation_id: Optional[str] = None,
               causation_id: Optional[str] = None,
               metadata: Optional[Mapping[str, Any]] = None) -> "UserRegistered":
        return cls(
            tenant_id=tenant_id,
            user_id=user_id,
            email=email,
            roles=tuple(roles),
            phone=phone,
            registration_source=registration_source,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=metadata or {},
        )


@dataclass(frozen=True, slots=True)
class UserActivated(EventBase):
    user_id: UserId = UserId(uuid4())
    actor_id: Optional[UserId] = None
    reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UserDeactivated(EventBase):
    user_id: UserId = UserId(uuid4())
    actor_id: Optional[UserId] = None
    reason: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UserUpdated(EventBase):
    user_id: UserId = UserId(uuid4())
    actor_id: Optional[UserId] = None
    # Keep PII out; only changed field names and redacted hints if needed
    changes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UserPasswordChanged(EventBase):
    user_id: UserId = UserId(uuid4())
    actor_id: Optional[UserId] = None   # None if self-service
    method: str = field(default="self_service")  # "self_service" | "admin_reset"


@dataclass(frozen=True, slots=True)
class UserRolesChanged(EventBase):
    user_id: UserId = UserId(uuid4())
    actor_id: UserId = UserId(uuid4())
    old_roles: Sequence[str] = field(default_factory=tuple)
    new_roles: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class UserLoggedIn(EventBase):
    user_id: UserId = UserId(uuid4())
    ip: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass(frozen=True, slots=True)
class UserLoginFailed(EventBase):
    # user_id may be unknown; capture attempted email instead
    email: str = field(default="")
    ip: Optional[str] = None
    reason: Optional[str] = None           # e.g., "invalid_credentials"
    attempts: Optional[int] = None         # failed_login_attempts after increment
