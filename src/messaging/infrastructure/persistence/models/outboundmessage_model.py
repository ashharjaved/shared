"""
SQLAlchemy ORM Model for OutboundMessage
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from messaging.infrastructure.persistence.models.channel_model import ChannelModel
from messaging.infrastructure.persistence.models.message_template_model import MessageTemplateModel
from shared.infrastructure.database.base_model import Base


class OutboundMessageModel(Base):
    """ORM model for whatsapp.outbound_messages table (partitioned by month)."""
    
    __tablename__ = "outbound_messages"
    __table_args__ = (
        Index("idx_outbound_channel_status", "channel_id", "status"),
        Index("idx_outbound_tenant", "tenant_id"),
        Index("idx_outbound_wa_message_id", "wa_message_id"),
        {"schema": "whatsapp"}
    )
    
    # Override base id
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.tenants.id"),
        nullable=False,
    )
    
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.channels.id"),
        nullable=False,
    )
    
    to_number: Mapped[str] = mapped_column(
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
    
    template_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.message_templates.id"),
        nullable=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
    )
    
    wa_message_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    
    error_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    scheduled_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    sent_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    delivered_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    read_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    # Override created_at and updated_at
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    # Relationships
    channel: Mapped[ChannelModel] = relationship(
        back_populates="outbound_messages",
    )
    
    template: Mapped[MessageTemplateModel | None] = relationship()