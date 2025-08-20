# src/identity/infrastructure/models.py
"""
Identity and Access Management models.
Contains:
- Tenants (platform organizations)
- Users (tenant members)
Security notes:
- Password hashes are encrypted at rest (handled by app layer)
- Email addresses are case-insensitive (CITEXT)
"""
from uuid import UUID
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import CITEXT, ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PGEnum, CITEXT

from src.shared.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.messaging.infrastructure.models import WhatsappChannel

# Bind directly to existing DB enums to avoid NameError on import
TENANT_TYPE_ENUM = PGEnum(
    "PLATFORM_OWNER", "RESELLER", "CLIENT",
    name="tenant_type_enum", create_type=False
)
SUBSCRIPTION_STATUS_ENUM = PGEnum(
    "ACTIVE", "PAST_DUE", "SUSPENDED", "CANCELLED",
    name="subscription_status_enum", create_type=False
)
USER_ROLE_ENUM = PGEnum(
    "SUPER_ADMIN","RESELLER_ADMIN","TENANT_ADMIN","STAFF",
    name="user_role_enum", create_type=False
)

class Tenant(Base):
    """Platform organization with subscription plan."""
    __tablename__ = 'tenants'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tenant_type: Mapped[str] = mapped_column(TENANT_TYPE_ENUM, nullable=False, server_default=text("'CLIENT'"))
    parent_tenant_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey('tenants.id'), nullable=True)
    subscription_plan: Mapped[str] = mapped_column(String(50), nullable=False)
    # subscription_status: Mapped[str] = mapped_column(SUBSCRIPTION_STATUS_ENUM, name="subscription_status_enum", nullable=False,
    #     server_default=text("'ACTIVE'")
    # )
    subscription_status: Mapped[str] = mapped_column(
        SUBSCRIPTION_STATUS_ENUM,
        nullable=False,
        server_default=text("'ACTIVE'::subscription_status_enum"),
    )
    billing_email: Mapped[Optional[str]] = mapped_column(CITEXT, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    
    # Relationships
    users: Mapped[List['User']] = relationship(back_populates='tenant', cascade='all, delete-orphan')
    channels: Mapped[List['WhatsappChannel']] = relationship(back_populates='tenant', cascade='all, delete-orphan')
    parent: Mapped[Optional['Tenant']] = relationship(remote_side=[id])
    
    __table_args__ = (
        Index('ix_tenants__parent', 'parent_tenant_id'),
        Index('ix_tenants__type_active', 'tenant_type', 'is_active'),
    )

class User(Base):
    """Tenant member with authentication credentials."""
    __tablename__ = 'users'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    roles: Mapped[str] = mapped_column(USER_ROLE_ENUM, nullable=False, server_default=text("'STAFF'"))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    is_verified: Mapped[bool] = mapped_column(nullable=False, server_default=text('false'))
    failed_login_attempts: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    tenant: Mapped['Tenant'] = relationship(back_populates='users')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_users__tenant_email'),
        CheckConstraint("roles IS NOT NULL", name="chk_users__roles_nonempty"),
        Index('ix_users__tenant_active', 'tenant_id', 'is_active'),
        Index('ix_users__failed_attempts', 'failed_login_attempts', postgresql_where=text('failed_login_attempts > 0')),
    )

__all__ = ['Tenant', 'User'];
