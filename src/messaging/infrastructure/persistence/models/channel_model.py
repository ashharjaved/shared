"""
SQLAlchemy ORM Model for Channel
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from messaging.infrastructure.persistence.models.inboundmessage_model import InboundMessageModel
from messaging.infrastructure.persistence.models.outboundmessage_model import OutboundMessageModel
from shared.infrastructure.database.base_model import Base


class ChannelModel(Base):
    """ORM model for whatsapp.channels table."""
    
    __tablename__ = "channels"
    __table_args__ = {"schema": "whatsapp"}
    
    # Override base id to remove default (will be set explicitly)
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.tenants.id"),
        nullable=False,
        index=True,
    )
    
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    phone_number_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )
    
    business_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    waba_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    access_token_encrypted: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )
    
    rate_limit_per_second: Mapped[int] = mapped_column(
        Integer,
        default=80,
        nullable=False,
    )
    
    monthly_message_limit: Mapped[int] = mapped_column(
        Integer,
        default=10000,
        nullable=False,
    )
    
    webhook_verify_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    metadata: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    # Override created_at and updated_at to remove server_default
    # (will be set by application)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    # Relationships
    inbound_messages: Mapped[list[InboundMessageModel]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    
    outbound_messages: Mapped[list[OutboundMessageModel]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )