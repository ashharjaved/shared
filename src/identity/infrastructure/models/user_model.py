# src/identity/infrastructure/models/user_model.py

from datetime import datetime
from typing import Optional
from uuid import UUID
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text,
    UUID as SQLAlchemy_UUID, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.shared_.database.base_model import BaseModel

from src.identity.domain.value_objects.role import Role

if TYPE_CHECKING:
    # Only for type checkers; does NOT run at import time, so no cycle
    from .tenant_model import TenantModel

class UserModel(BaseModel):
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
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now()  # keep ORM instance fresh; DB trigger remains source of truth
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        CheckConstraint("failed_login_attempts >= 0", name="chk_failed_login_attempts_nonneg"),
        Index("idx_users_tenant_role", "tenant_id", "role"),
        Index("idx_users_tenant", "tenant_id"),
        Index("ix_users__tenant_active", "tenant_id", "is_active"),
    )

    tenant: Mapped["TenantModel"] = relationship("TenantModel", back_populates="users")
    
    
    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email='{self.email}', role={self.role})>"