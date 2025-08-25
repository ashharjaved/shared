from __future__ import annotations

import uuid
from datetime import datetime


from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import (
    UUID,
    Column,
    Index,
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    Enum as SAEnum,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship

from src.identity.domain.value_objects import Role, SubscriptionPlan, SubscriptionStatus, TenantType

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True,server_default=text("gen_random_uuid()"))
    name = Column(String(255), nullable=False, unique=True)
    tenant_type = Column(SAEnum(TenantType, name="tenant_type_enum"), nullable=False)
    parent_tenant_id = Column(PGUUID(as_uuid=True), nullable=True)
    subscription_plan = Column(SAEnum(SubscriptionPlan, name="subscription_plan_enum"), nullable=False, default=SubscriptionPlan.BASIC)
    subscription_status = Column(SAEnum(SubscriptionStatus, name="subscription_status_enum"), nullable=False, default=SubscriptionStatus.ACTIVE)
    billing_email = Column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=text("now()"))
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=text("now()"))

    users = relationship("User", back_populates="tenant")
    # Relationships
    #channels: Mapped[List['WhatsappChannel']] = relationship(back_populates='tenant', cascade='all, delete-orphan')
    #parent: Mapped[Optional['Tenant']] = relationship(remote_side=[id])
    
    __table_args__ = (
        Index('ix_tenants__parent', 'parent_tenant_id'),
        Index('ix_tenants__type_active', 'tenant_type', 'is_active'),
    )


class User(Base):
    __tablename__ = "users"

    # id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # password_hash = Column(String, nullable=False)
    
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    role = Column(SAEnum(Role, name="user_role_enum"), nullable=False, default=Role.STAFF)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_login = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=text("now()"))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=text("now()"))
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=text("now()"))
    deleted_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)

    tenant = relationship("Tenant", back_populates="users")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_users__tenant_email'),
        Index('ix_users__tenant_active', 'tenant_id', 'is_active'),
        Index('ix_users__failed_attempts', 'failed_login_attempts', postgresql_where=text('failed_login_attempts > 0')),
    )
