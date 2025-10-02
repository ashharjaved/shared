"""
Identity API Schemas
Pydantic v2 models for request/response validation
"""
from src.identity.api.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    EmailVerificationRequest,
)
from src.identity.api.schemas.user_schemas import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
    UserListResponse,
    DeactivateUserRequest,
)
from src.identity.api.schemas.organization_schemas import (
    CreateOrganizationRequest,
    UpdateOrganizationRequest,
    OrganizationResponse,
)
from src.identity.api.schemas.role_schemas import (
    AssignRoleRequest,
    RevokeRoleRequest,
    RoleResponse,
    UserRolesResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "PasswordResetRequest",
    "PasswordResetConfirmRequest",
    "EmailVerificationRequest",
    # User
    "CreateUserRequest",
    "UpdateUserRequest",
    "UserResponse",
    "UserListResponse",
    "DeactivateUserRequest",
    # Organization
    "CreateOrganizationRequest",
    "UpdateOrganizationRequest",
    "OrganizationResponse",
    # Role
    "AssignRoleRequest",
    "RevokeRoleRequest",
    "RoleResponse",
    "UserRolesResponse",
]