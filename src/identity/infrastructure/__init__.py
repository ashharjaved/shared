"""
Identity Infrastructure Layer
ORM models, repositories, external adapters
"""
from src.identity.infrastructure.persistence.models import (
    OrganizationModel,
    UserModel,
    RoleModel,
    UserRoleModel,
    RefreshTokenModel,
    AuditLogModel,
    ApiKeyModel,
    PasswordResetTokenModel,
)

from src.identity.infrastructure.persistence.repositories import (
    OrganizationRepository,
    UserRepository,
    RoleRepository,
    RefreshTokenRepository,
    AuditLogRepository,
    ApiKeyRepository,
)

from src.identity.infrastructure.adapters.identity_unit_of_work import (
    IdentityUnitOfWork,
)

from src.identity.infrastructure.services.audit_log_service import (
    AuditLogService,
)

from src.identity.infrastructure.adapters import (
    JWTService,
    PasswordService,
)

from src.identity.infrastructure.persistence.rls_verification import (
    RLSNotSetError,
    verify_rls_context,
    require_rls_context,
)

__all__ = [
    # Models
    "OrganizationModel",
    "UserModel",
    "RoleModel",
    "UserRoleModel",
    "RefreshTokenModel",
    "AuditLogModel",
    "ApiKeyModel",
    "PasswordResetTokenModel",
    # Repositories
    "OrganizationRepository",
    "UserRepository",
    "RoleRepository",
    "RefreshTokenRepository",
    "AuditLogRepository",
    "ApiKeyRepository",
    # Unit of Work
    "IdentityUnitOfWork",
    # Services
    "AuditLogService",
    # Adapters
    "JWTService",
    "PasswordService",
    # RLS Verification
    "RLSNotSetError",
    "verify_rls_context",
    "require_rls_context",
]