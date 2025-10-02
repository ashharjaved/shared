"""
RefreshToken ORM Model
Maps to identity.refresh_tokens table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.user_model import UserModel
from shared.infrastructure.database.base_model import Base


class RefreshTokenModel(Base):
    """
    SQLAlchemy model for identity.refresh_tokens table.
    
    Stores hashed refresh tokens for JWT authentication.
    """
    
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "identity"}
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Token Fields
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    
    # Relationships
    user: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="refresh_tokens",
        lazy="joined",
    )
    
    def __repr__(self) -> str:
        return f"<RefreshTokenModel(id={self.id}, user_id={self.user_id})>"