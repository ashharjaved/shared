"""Identity Domain Events"""
from src.identity.domain.events.organization_events import (
    OrganizationCreatedEvent,
    OrganizationActivatedEvent,
    OrganizationDeactivatedEvent,
)
from src.identity.domain.events.user_events import (
    UserCreatedEvent,
    UserLoggedInEvent,
    UserLockedEvent,
    UserUnlockedEvent,
    EmailVerifiedEvent,
    PhoneVerifiedEvent,
    PasswordChangedEvent,
)
from src.identity.domain.events.role_events import (
    RoleCreatedEvent,
    PermissionGrantedEvent,
    PermissionRevokedEvent,
    RoleAssignedEvent,
    RoleRevokedEvent,
)

__all__ = [
    # Organization Events
    "OrganizationCreatedEvent",
    "OrganizationActivatedEvent",
    "OrganizationDeactivatedEvent",
    # User Events
    "UserCreatedEvent",
    "UserLoggedInEvent",
    "UserLockedEvent",
    "UserUnlockedEvent",
    "EmailVerifiedEvent",
    "PhoneVerifiedEvent",
    "PasswordChangedEvent",
    # Role Events
    "RoleCreatedEvent",
    "PermissionGrantedEvent",
    "PermissionRevokedEvent",
    "RoleAssignedEvent",
    "RoleRevokedEvent",
]