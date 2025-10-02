"""
IdempotencyKey ORM Model
Maps to identity.idempotency_keys table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class IdempotencyKeyModel(Base):
    """
    SQLAlchemy model for identity.idempotency_keys table.
    
    Prevents duplicate operations via idempotency key matching.
    Keys expire after 24 hours (configurable).
    """
    
    __tablename__ = "idempotency_keys"
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
    
    # Idempotency Fields
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Response Cache
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Lifecycle
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<IdempotencyKeyModel(key={self.idempotency_key}, endpoint={self.endpoint})>"