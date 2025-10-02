"""
User ORM Model
Maps to identity.users table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.organization_model import OrganizationModel
from identity.infrastructure.persistence.models.refresh_token_model import RefreshTokenModel
from identity.infrastructure.persistence.models.user_role_model import UserRoleModel
from shared.infrastructure.database.base_model import Base


class UserModel(Base):
    """
    SQLAlchemy model for identity.users table.
    
    RLS enabled - scoped by organization_id.
    """
    
    __tablename__ = "users"
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
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Status Flags
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Security Fields
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # JSONB Fields
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Relationships
    organization: Mapped[OrganizationModel] = relationship(
        "OrganizationModel",
        back_populates="users",
        lazy="joined",
    )
    user_roles: Mapped[list[UserRoleModel]] = relationship(
        "UserRoleModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    refresh_tokens: Mapped[list[RefreshTokenModel]] = relationship(
        "RefreshTokenModel",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, email={self.email})>"