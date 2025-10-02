"""Message Status Update ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class MessageStatusUpdateModel(Base):
    """
    Message status update ORM model.
    
    Tracks status changes for outbound messages (sent, delivered, read, failed).
    Each status transition creates a new record for audit trail.
    """
    
    __tablename__ = "message_status_updates"
    __table_args__ = (
        Index("idx_status_updates_msg_id", "wa_message_id"),
        Index("idx_status_updates_outbound", "outbound_message_id"),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    outbound_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.outbound_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    wa_message_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return f"<MessageStatusUpdateModel(id={self.id}, status={self.status})>"