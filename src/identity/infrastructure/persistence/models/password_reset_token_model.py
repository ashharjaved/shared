"""
PasswordResetToken ORM Model
Maps to identity.password_reset_tokens table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.user_model import UserModel

from shared.infrastructure.database.base_model import Base


class PasswordResetTokenModel(Base):
    """
    SQLAlchemy model for identity.password_reset_tokens table.
    
    One-time use tokens for password reset flow.
    """
    
    __tablename__ = "password_reset_tokens"
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
    used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Audit Fields
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    
    # Relationships
    user: Mapped[UserModel] = relationship(
        "UserModel",
        lazy="joined",
    )
    
    def __repr__(self) -> str:
        return f"<PasswordResetTokenModel(id={self.id}, user_id={self.user_id})>"