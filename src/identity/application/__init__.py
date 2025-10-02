"""
Identity Application Layer
Commands, queries, services, and DTOs
"""
from src.identity.application.commands import (
    CreateOrganizationCommand,
    CreateOrganizationCommandHandler,
    CreateUserCommand,
    CreateUserCommandHandler,
    LoginCommand,
    LoginCommandHandler,
    RefreshTokenCommand,
    RefreshTokenCommandHandler,
    AssignRoleCommand,
    AssignRoleCommandHandler,
    RevokeRoleCommand,
    RevokeRoleCommandHandler,
    UpdatePasswordCommand,
    UpdatePasswordCommandHandler,
)

# NEW: Email verification commands
from src.identity.application.commands.request_email_verification_command import (
    RequestEmailVerificationCommand,
    RequestEmailVerificationCommandHandler,
)
from src.identity.application.commands.verify_email_command import (
    VerifyEmailCommand,
    VerifyEmailCommandHandler,
)

# NEW: Password reset commands
from src.identity.application.commands.request_password_reset_command import (
    RequestPasswordResetCommand,
    RequestPasswordResetCommandHandler,
)
from src.identity.application.commands.reset_password_command import (
    ResetPasswordCommand,
    ResetPasswordCommandHandler,
)

# NEW: User deactivation commands
from src.identity.application.commands.deactivate_user_command import (
    DeactivateUserCommand,
    DeactivateUserCommandHandler,
)
from src.identity.application.commands.reactivate_user_command import (
    ReactivateUserCommand,
    ReactivateUserCommandHandler,
)

from src.identity.application.queries import (
    GetUserByIdQuery,
    GetUserByIdQueryHandler,
    GetUserByEmailQuery,  # Now implemented
    GetUserByEmailQueryHandler,  # Now implemented
    GetOrganizationByIdQuery,  # Now implemented
    GetOrganizationByIdQueryHandler,  # Now implemented
    GetUserRolesQuery,
    GetUserRolesQueryHandler,
    ListUsersQuery,
    ListUsersQueryHandler,
)

from src.identity.application.services import (
    UserService,
    AuthService,
    RoleService,
)

from src.identity.application.dto import (
    UserDTO,
    UserListDTO,
    OrganizationDTO,
    RoleDTO,
    LoginResponseDTO,
)

__all__ = [
    # Commands - Core
    "CreateOrganizationCommand",
    "CreateOrganizationCommandHandler",
    "CreateUserCommand",
    "CreateUserCommandHandler",
    "LoginCommand",
    "LoginCommandHandler",
    "RefreshTokenCommand",
    "RefreshTokenCommandHandler",
    "AssignRoleCommand",
    "AssignRoleCommandHandler",
    "RevokeRoleCommand",
    "RevokeRoleCommandHandler",
    "UpdatePasswordCommand",
    "UpdatePasswordCommandHandler",
    # Commands - Email Verification
    "RequestEmailVerificationCommand",
    "RequestEmailVerificationCommandHandler",
    "VerifyEmailCommand",
    "VerifyEmailCommandHandler",
    # Commands - Password Reset
    "RequestPasswordResetCommand",
    "RequestPasswordResetCommandHandler",
    "ResetPasswordCommand",
    "ResetPasswordCommandHandler",
    # Commands - User Management
    "DeactivateUserCommand",
    "DeactivateUserCommandHandler",
    "ReactivateUserCommand",
    "ReactivateUserCommandHandler",
    # Queries
    "GetUserByIdQuery",
    "GetUserByIdQueryHandler",
    "GetUserByEmailQuery",
    "GetUserByEmailQueryHandler",
    "GetOrganizationByIdQuery",
    "GetOrganizationByIdQueryHandler",
    "GetUserRolesQuery",
    "GetUserRolesQueryHandler",
    "ListUsersQuery",
    "ListUsersQueryHandler",
    # Services
    "UserService",
    "AuthService",
    "RoleService",
    # DTOs
    "UserDTO",
    "UserListDTO",
    "OrganizationDTO",
    "RoleDTO",
    "LoginResponseDTO",
]