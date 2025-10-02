"""
SQLAlchemy ORM Model for InboundMessage
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from messaging.infrastructure.persistence.models.channel_model import ChannelModel
from shared.infrastructure.database.base_model import Base


class InboundMessageModel(Base):
    """ORM model for whatsapp.inbound_messages table (partitioned by month)."""
    
    __tablename__ = "inbound_messages"
    __table_args__ = (
        Index("idx_inbound_wa_message_id", "wa_message_id"),
        Index("idx_inbound_channel_tenant", "channel_id", "tenant_id"),
        Index("idx_inbound_processed", "processed"),
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
    
    wa_message_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    
    from_number: Mapped[str] = mapped_column(
        String(20),
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
    
    timestamp_wa: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    raw_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    
    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
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
        back_populates="inbound_messages",
    )