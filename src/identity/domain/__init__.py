"""
Identity Domain Layer
Pure domain logic with no framework dependencies
"""
from src.identity.domain.entities.organization import Organization, Industry
from src.identity.domain.entities.user import User
from src.identity.domain.entities.role import Role
from src.identity.domain.entities.user_role import UserRole
from src.identity.domain.entities.refresh_token import RefreshToken
from src.identity.domain.entities.audit_log import AuditLog, AuditAction
from src.identity.domain.entities.api_key import ApiKey

from src.identity.domain.value_objects.email import Email
from src.identity.domain.value_objects.phone import Phone
from src.identity.domain.value_objects.password_hash import PasswordHash
from src.identity.domain.value_objects.organization_metadata import (
    OrganizationMetadata,
)
from src.identity.domain.value_objects.permission import Permission

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

from src.identity.domain.exception import (
    IdentityDomainException,
    InvalidCredentialsException,
    AccountLockedException,
    EmailNotVerifiedException,
    DuplicateEmailException,
    DuplicateSlugException,
    OrganizationNotFoundException,
    UserNotFoundException,
    RoleNotFoundException,
    PermissionDeniedException,
    RefreshTokenExpiredException,
    RefreshTokenRevokedException,
    ApiKeyExpiredException,
    ApiKeyRevokedException,
    DuplicateRoleNameException,
    SystemRoleModificationException,
)

from src.identity.domain.protocols.organization_repository_protocol import (
    IOrganizationRepository,
)
from src.identity.domain.protocols.user_repository_protocol import (
    IUserRepository,
)
from src.identity.domain.protocols.role_repository_protocol import (
    IRoleRepository,
)
from src.identity.domain.protocols.refresh_token_repository_protocol import (
    IRefreshTokenRepository,
)
from src.identity.domain.protocols.audit_log_repository_protocol import (
    IAuditLogRepository,
)
from src.identity.domain.protocols.api_key_repository_protocol import (
    IApiKeyRepository,
)

__all__ = [
    # Entities
    "Organization",
    "Industry",
    "User",
    "Role",
    "UserRole",
    "RefreshToken",
    "AuditLog",
    "AuditAction",
    "ApiKey",
    # Value Objects
    "Email",
    "Phone",
    "PasswordHash",
    "OrganizationMetadata",
    "Permission",
    # Events - Organization
    "OrganizationCreatedEvent",
    "OrganizationActivatedEvent",
    "OrganizationDeactivatedEvent",
    # Events - User
    "UserCreatedEvent",
    "UserLoggedInEvent",
    "UserLockedEvent",
    "UserUnlockedEvent",
    "EmailVerifiedEvent",
    "PhoneVerifiedEvent",
    "PasswordChangedEvent",
    # Events - Role
    "RoleCreatedEvent",
    "PermissionGrantedEvent",
    "PermissionRevokedEvent",
    "RoleAssignedEvent",
    "RoleRevokedEvent",
    # Exceptions
    "IdentityDomainException",
    "InvalidCredentialsException",
    "AccountLockedException",
    "EmailNotVerifiedException",
    "DuplicateEmailException",
    "DuplicateSlugException",
    "OrganizationNotFoundException",
    "UserNotFoundException",
    "RoleNotFoundException",
    "PermissionDeniedException",
    "RefreshTokenExpiredException",
    "RefreshTokenRevokedException",
    "ApiKeyExpiredException",
    "ApiKeyRevokedException",
    "DuplicateRoleNameException",
    "SystemRoleModificationException",
    # Repository Protocols
    "IOrganizationRepository",
    "IUserRepository",
    "IRoleRepository",
    "IRefreshTokenRepository",
    "IAuditLogRepository",
    "IApiKeyRepository",
]