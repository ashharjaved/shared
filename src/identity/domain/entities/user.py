# src/identity/domain/entities/user.py
"""User aggregate root."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ..types import UserId, TenantId
from ..value_objects import Email, Phone, PasswordHash, Name, Role, Timestamps
from ..errors import InvariantViolation, ValidationError


@dataclass(slots=True)
class User:
    """User aggregate root for authentication and authorization."""
    
    id: UserId
    tenant_id: TenantId
    email: Email
    phone: Phone | None
    password_hash: PasswordHash
    roles: list[Role]
    is_active: bool
    last_login: datetime | None
    failed_login_attempts: int
    timestamps: Timestamps
    
    def __post_init__(self) -> None:
        """Validate user invariants."""
        if not self.roles:
            raise InvariantViolation("User must have at least one role")
        
        # Ensure roles are unique
        if len(set(self.roles)) != len(self.roles):
            raise InvariantViolation("User roles must be unique")
        
        if self.failed_login_attempts < 0:
            raise InvariantViolation("Failed login attempts cannot be negative")
    
    @classmethod
    def create(
        cls,
        tenant_id: TenantId,
        email: str,
        password_hash: str,
        roles: list[str],
        phone: str | None = None,
        display_name: str | None = None,
    ) -> 'User':
        """Create new user."""
        email_vo = Email.from_string(email) if hasattr(Email, "from_string") else Email(email)
        phone_vo = Phone.from_string(phone) if phone else None
        password_vo = PasswordHash(password_hash)
        role_vo = tuple((Role.from_string(r) if hasattr(Role, "from_str") else Role[r]) for r in roles)
        
        return cls(
            id=UserId(uuid4()),
            tenant_id=tenant_id,
            email=email_vo,
            phone=phone_vo,
            password_hash=password_vo,
            roles=role_vo,
            is_active=True,
            last_login=None,
            failed_login_attempts=0,
            timestamps=Timestamps.now(),
        )
    
    def activate(self) -> None:
        """Activate user account."""
        if self.is_active:
            return
        
        self.is_active = True
        self.failed_login_attempts = 0  # Reset on activation
        self._update_timestamp()
    
    def deactivate(self) -> None:
        """Deactivate user account."""
        if not self.is_active:
            return
        
        self.is_active = False
        self._update_timestamp()
    
    def record_login(self) -> None:
        """Record successful login."""
        self.last_login = datetime.now(timezone.utc)
        self.failed_login_attempts = 0
        self._update_timestamp()
    
    def bump_failed_login(self) -> None:
        """Record failed login attempt."""
        self.failed_login_attempts += 1
        self._update_timestamp()
    
    def is_locked(self, max_attempts: int = 5) -> bool:
        """Check if account is locked due to failed attempts."""
        return self.failed_login_attempts >= max_attempts
    
    def has_role(self, role: Role) -> bool:
        """Check if user has specific role."""
        return role in self.roles
    
    def has_any_role(self, roles: list[Role]) -> bool:
        """Check if user has any of the given roles."""
        return any(role in self.roles for role in roles)
    
    def get_highest_role(self) -> Role:
        """Get the highest privilege role."""
        return min(self.roles)  # Lower enum value = higher privilege
    
    def add_role(self, role: Role) -> None:
        """Add role to user."""
        if role not in self.roles:
            self.roles.append(role)
            self._update_timestamp()
    
    def remove_role(self, role: Role) -> None:
        """Remove role from user."""
        if role in self.roles:
            if len(self.roles) == 1:
                raise InvariantViolation("Cannot remove last role from user")
            
            self.roles.remove(role)
            self._update_timestamp()
    
    def update_password(self, new_password_hash: str) -> None:
        """Update user password."""
        self.password_hash = PasswordHash(new_password_hash)
        self.failed_login_attempts = 0  # Reset on password change
        self._update_timestamp()
    
    def _update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.timestamps = self.timestamps.update_timestamp()