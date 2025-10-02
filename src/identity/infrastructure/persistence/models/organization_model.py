"""
Organization ORM Model
Maps to identity.organizations table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.api_key_model import ApiKeyModel
from identity.infrastructure.persistence.models.role_model import RoleModel
from identity.infrastructure.persistence.models.user_model import UserModel
from shared.infrastructure.database.base_model import Base


class OrganizationModel(Base):
    """
    SQLAlchemy model for identity.organizations table.
    
    Multi-tenant root - all data scopes to an organization.
    No RLS on this table (handled at application level).
    """
    
    __tablename__ = "organizations"
    __table_args__ = {"schema": "identity"}
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Core Fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    
    # JSONB Fields
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Relationships
    users: Mapped[list[UserModel]] = relationship(
        "UserModel",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    roles: Mapped[list[RoleModel]] = relationship(
        "RoleModel",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    api_keys: Mapped[list[ApiKeyModel]] = relationship(
        "ApiKeyModel",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<OrganizationModel(id={self.id}, slug={self.slug}, name={self.name})>"