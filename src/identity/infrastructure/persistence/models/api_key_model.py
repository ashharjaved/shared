"""
ApiKey ORM Model
Maps to identity.api_keys table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.organization_model import OrganizationModel
from shared.infrastructure.database.base_model import Base


class ApiKeyModel(Base):
    """
    SQLAlchemy model for identity.api_keys table.
    
    Stores hashed API keys with permission scoping.
    """
    
    __tablename__ = "api_keys"
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
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    # Key Fields
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Permissions (JSONB array)
    permissions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    
    # Usage Tracking
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    
    # Relationships
    organization: Mapped[OrganizationModel] = relationship(
        "OrganizationModel",
        back_populates="api_keys",
        lazy="joined",
    )
    
    def __repr__(self) -> str:
        return f"<ApiKeyModel(id={self.id}, prefix={self.key_prefix}, is_active={self.is_active})>"