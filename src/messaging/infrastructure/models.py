# src/messaging/infrastructure/models.py
"""
Messaging gateway models.
Contains:
- WhatsAppChannel (tenant messaging channels)
- Message (message transport records)
Security notes:
- Access tokens are envelope-encrypted (app/KMS)
- Messages must NOT contain PHI (tokenized references only)
"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ENUM


from src.shared.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.conversation.infrastructure.models import ConversationSession
    from src.identity.infrastructure.models import Tenant

class WhatsappChannel(Base):
    """WhatsApp Business API channel configuration."""
    __tablename__ = 'whatsapp_channels'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    phone_number_id: Mapped[str] = mapped_column(nullable=False, unique=True)
    business_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    access_token_ciphertext: Mapped[str] = mapped_column(nullable=False)  # envelope-encrypted
    webhook_verify_token_ciphertext: Mapped[str] = mapped_column(nullable=False)  # envelope-encrypted
    webhook_url: Mapped[str] = mapped_column(nullable=False)
    rate_limit_per_second: Mapped[int] = mapped_column(nullable=False, server_default=text('10'))
    monthly_message_limit: Mapped[int] = mapped_column(nullable=False, server_default=text('10000'))
    current_month_usage: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    last_webhook_received: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    tenant: Mapped['Tenant'] = relationship(back_populates='channels')
    messages: Mapped[List['Message']] = relationship(back_populates='channel')
    sessions: Mapped[list["ConversationSession"]] = relationship(
        "ConversationSession", back_populates="channel", lazy="raise"
    )
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'business_phone', name='uq_channels__tenant_business'),
        CheckConstraint("business_phone ~ '^\\+[1-9]\\d{1,14}$'", name='chk_channels__phone_e164'),
        Index('ix_channels__tenant_active', 'tenant_id', 'is_active'),
        Index('ix_channels__tenant_created', 'tenant_id', text('created_at DESC'))
    )

class Message(Base):
    """WhatsApp message transport record (no PHI)."""
    __tablename__ = 'messages'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey('whatsapp_channels.id'), nullable=False)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(nullable=True, unique=True)
    direction: Mapped[str] = mapped_column(ENUM('INBOUND', 'OUTBOUND', name='message_direction_enum'), nullable=False)
    from_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    to_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    content_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(ENUM('QUEUED', 'SENT', 'DELIVERED', 'READ', 'FAILED', name='message_status_enum'), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status_updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    channel: Mapped['WhatsappChannel'] = relationship(back_populates='messages')
    
    __table_args__ = (
        CheckConstraint("from_phone ~ '^\\+[1-9]\\d{1,14}$'", name='chk_messages__from_e164'),
        CheckConstraint("to_phone ~ '^\\+[1-9]\\d{1,14}$'", name='chk_messages__to_e164'),
        CheckConstraint(
            "tenant_id = (SELECT tenant_id FROM whatsapp_channels c WHERE c.id = channel_id)",
            name='fk_messages__tenant_match'
        ),
        Index("ix_messages__tenant_channel_to_created","tenant_id", "channel_id", "to_phone", "created_at",postgresql_ops={"created_at": "DESC"}),
        # Index('ix_messages__tenant_channel_from_created', 'tenant_id', 'channel_id', 'from_phone', 'created_at', postgresql_desc=True),
        Index('ix_messages__tenant_channel_from_created', 'tenant_id', 'channel_id', 'from_phone', 'created_at'),
        Index('ix_messages__tenant_created', 'tenant_id', 'created_at'),
        Index('ix_messages__content_gin', 'content_jsonb', postgresql_using='gin'),
        Index('ix_messages__content_hash', 'content_hash'),
        Index('ix_messages__non_delivered', 'channel_id', 'status', postgresql_where=text("status <> 'DELIVERED'")),
        Index('ix_messages__failed_retries', 'channel_id', 'status', 'retry_count', postgresql_where=text("status = 'FAILED' AND retry_count < 3")),        
    )

__all__ = ['WhatsappChannel', 'Message']