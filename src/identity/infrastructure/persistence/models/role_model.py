"""
Role ORM Model
Maps to identity.roles table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models import OrganizationModel,UserRoleModel
from shared.infrastructure.database.base_model import Base


class RoleModel(Base):
    """
    SQLAlchemy model for identity.roles table.
    
    Stores RBAC roles with permissions as JSONB array.
    """
    
    __tablename__ = "roles"
    __table_args__ = {"schema": "identity"}
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Foreign Keys
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Core Fields
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Permissions (JSONB array of strings)
    permissions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    
    # System Role Flag
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Relationships
    organization: Mapped[OrganizationModel] = relationship(
        "OrganizationModel",
        back_populates="roles",
        lazy="joined",
    )
    user_roles: Mapped[list[UserRoleModel]] = relationship(
        "UserRoleModel",
        back_populates="role",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<RoleModel(id={self.id}, name={self.name}, is_system={self.is_system})>"