"""
AuditLog ORM Model
Maps to identity.audit_logs table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class AuditLogModel(Base):
    """
    SQLAlchemy model for identity.audit_logs table.
    
    Immutable audit trail for security and compliance.
    7-year retention enforced at database level.
    """
    
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "identity"}
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Foreign Keys (nullable for system events)
    organization_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.organizations.id"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.users.id"),
        nullable=True,
        index=True,
    )
    
    # Action Fields
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    
    # Context Fields
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata (JSONB)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    
    # Timestamp (immutable)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self) -> str:
        return f"<AuditLogModel(id={self.id}, action={self.action})>"