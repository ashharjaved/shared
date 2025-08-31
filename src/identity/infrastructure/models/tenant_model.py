# src/identity/infrastructure/models/tenant_model.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UUID as SQLAlchemy_UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from identity.infrastructure.models.user_model import UserModel
from src.identity.domain.entities.tenant import SubscriptionPlan
from src.shared.database import Base
from src.identity.domain.entities.tenant import Tenant, TenantType

class TenantModel(Base):
    """SQLAlchemy model for tenants table."""
    
    __tablename__ = "tenants"
    
    id: Mapped[UUID] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    type: Mapped[TenantType] = mapped_column(
        PG_ENUM(TenantType, name="tenant_type_enum", create_type=False),
        nullable=False
    )
     
    parent_tenant_id: Mapped[Optional[UUID]] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True
    )
    plan: Mapped[Optional["SubscriptionPlan"]] = mapped_column(
        PG_ENUM(SubscriptionPlan, name="subscription_plan_enum", create_type=False),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    
    # Relationships
    users: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        back_populates="tenant",
    )
    
    __table_args__ = (
        Index("idx_tenants_type", "type"),
        Index("ix_tenants_parent_tenant_id", "parent_tenant_id"),)
    
    def to_domain(self) -> Tenant:
        """Convert ORM model to domain entity."""
        return Tenant(
            id=self.id,
            name=self.name,
            type=self.type,
            parent_tenant_id=self.parent_tenant_id,
            plan=self.plan,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
    
    @classmethod
    def from_domain(cls, tenant: Tenant) -> "TenantModel":
        """Create ORM model from domain entity."""
        return cls(
            id=tenant.id,
            name=tenant.name,
            type=tenant.type,
            parent_tenant_id=tenant.parent_tenant_id,
            plan=tenant.plan,
            is_active=tenant.is_active,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at
        )
    
    def __repr__(self) -> str:
        return f"<TenantModel(id={self.id}, name='{self.name}', type={self.type})>"