# src/identity/infrastructure/models/tenant_model.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UUID as SQLAlchemy_UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.shared_.database.base_model import BaseModel
from src.identity.domain.entities.tenant import TenantType

if TYPE_CHECKING:
    # Only for type checkers; does NOT run at import time, so no cycle
    from .user_model import UserModel

class TenantModel(BaseModel):
    """SQLAlchemy model for tenants table."""
    
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid()
    )

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # match table column name "type"
    type: Mapped[TenantType] = mapped_column(
        PG_ENUM(TenantType, name="tenant_type_enum", create_type=False),
        name="type",
        nullable=False
    )

    parent_tenant_id: Mapped[Optional[UUID]] = mapped_column(
        SQLAlchemy_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=True
    )

    # use server_default to mirror DDL
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=("true")
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

    remarks: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    users: Mapped[list["UserModel"]] = relationship(
        "UserModel",
        back_populates="tenant",
    )

    __table_args__ = (
        # point to the actual column "type" and align names
        Index("idx_tenants_type", "type"),
        Index("idx_tenants_parent", "parent_tenant_id"),
    )
    def __repr__(self) -> str:
        return f"<TenantModel(id={self.id}, name='{self.name}', type={self.type})>"