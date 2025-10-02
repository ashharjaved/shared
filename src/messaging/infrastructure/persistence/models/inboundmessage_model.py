"""Inbound Message ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class InboundMessageModel(Base):
    """
    Inbound WhatsApp message ORM model.
    
    Stores all incoming messages from WhatsApp webhook.
    Supports text, image, video, document, audio, location, and contacts.
    """
    
    __tablename__ = "inbound_messages"
    __table_args__ = (
        UniqueConstraint("wa_message_id", name="uq_inbound_messages_wa_message_id"),
        Index("idx_inbound_account_time", "account_id", "timestamp"),
        Index("idx_inbound_from_phone", "from_phone"),
        Index("idx_inbound_wa_msg_id", "wa_message_id"),
        Index("idx_inbound_status", "status"),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    wa_message_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    
    from_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    to_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    message_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    content: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    context: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="received",
        nullable=False,
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return f"<InboundMessageModel(id={self.id}, wa_id={self.wa_message_id})>"