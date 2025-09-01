# src/identity/infrastructure/models/user_model.py

from datetime import datetime
from typing import Optional
from uuid import UUID
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, Text,
    UUID as SQLAlchemy_UUID, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.shared.database import Base
from src.identity.domain.entities.user import User
from src.shared.roles import Role

if TYPE_CHECKING:
    # Only for type checkers; does NOT run at import time, so no cycle
    from .tenant_model import TenantModel

class UserModel(Base):
    """SQLAlchemy model for users table."""
    
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False
    )
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Role] = mapped_column(
        PG_ENUM(Role, name="user_role_enum", create_type=False),
        nullable=False
    )    
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
        Index("idx_users_tenant", "tenant_id"),
        Index("idx_users_tenant_active", "tenant_id", "is_active"),    )
    
    # Relationships
    tenant: Mapped["TenantModel"] = relationship("TenantModel", back_populates="users")
    
    def to_domain(self) -> User:
        """Convert ORM model to domain entity."""
        return User(
            id=self.id,
            tenant_id=self.tenant_id,
            email=self.email,
            password_hash=self.password_hash,
            role=self.role,
            is_active=self.is_active,
            is_verified=self.is_verified,
            failed_login_attempts=self.failed_login_attempts,
            last_login=self.last_login,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
    
    @classmethod
    def from_domain(cls, user: User) -> "UserModel":
        """Create ORM model from domain entity."""
        return cls(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            failed_login_attempts=user.failed_login_attempts,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    
    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email='{self.email}', role={self.role})>"