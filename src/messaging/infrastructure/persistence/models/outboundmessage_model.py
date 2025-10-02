"""Outbound Message ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class OutboundMessageModel(Base):
    """
    Outbound WhatsApp message ORM model.
    
    Stores all outgoing messages sent via WhatsApp Business API.
    Tracks delivery status and supports idempotency.
    """
    
    __tablename__ = "outbound_messages"
    __table_args__ = (
        UniqueConstraint("wa_message_id", name="uq_outbound_messages_wa_message_id"),
        UniqueConstraint("idempotency_key", name="uq_outbound_messages_idempotency_key"),
        Index("idx_outbound_account_time", "account_id", "created_at"),
        Index("idx_outbound_to_phone", "to_phone"),
        Index("idx_outbound_status", "status"),
        Index("idx_outbound_idempotency", "idempotency_key"),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.accounts.id", ondelete="CASCADE"),
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
    
    template_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    
    template_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    
    template_params: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    
    wa_message_id: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
    )
    
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    
    metadata: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<OutboundMessageModel(id={self.id}, status={self.status})>"