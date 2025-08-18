# src/conversation/infrastructure/models.py
"""
Conversation engine models.
Contains:
- ConversationSession (active chat sessions)
- MenuFlow (conversation flow definitions)
Important:
- Sessions have TTL (expires_at)
- MenuFlows are versioned per tenant
"""
from uuid import UUID
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ENUM

from shared.database import Base

class MenuFlow(Base):
    """Conversation menu flow definition."""
    __tablename__ = 'menu_flows'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    industry_type: Mapped[str] = mapped_column(ENUM('HEALTHCARE', 'EDUCATION', 'GENERIC', name='industry_type_enum'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, server_default=text('1'))
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    is_default: Mapped[bool] = mapped_column(nullable=False, server_default=text('false'))
    created_by: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    sessions: Mapped[List['ConversationSession']] = relationship(back_populates='current_menu')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', 'version', name='uq_flows__tenant_name_version'),
        UniqueConstraint('tenant_id', 'industry_type', 'is_default', name='uq_flows__tenant_industry_default', deferrable=True),
    )

class ConversationSession(Base):
    """Active conversation session with state."""
    __tablename__ = 'conversation_sessions'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey('whatsapp_channels.id'), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    current_menu_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey('menu_flows.id'), nullable=True)
    context_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    conversation_stage: Mapped[str] = mapped_column(ENUM('INITIATED', 'IN_PROGRESS', 'AWAITING_INPUT', 'COMPLETED', 'EXPIRED', name='conversation_stage_enum'), nullable=False, server_default='INITIATED')
    status: Mapped[str] = mapped_column(ENUM('CREATED', 'ACTIVE', 'EXPIRED', name='session_status_enum'), nullable=False, server_default='CREATED')
    message_count: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_activity: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    channel: Mapped['WhatsappChannel'] = relationship(back_populates='sessions')
    current_menu: Mapped[Optional['MenuFlow']] = relationship(back_populates='sessions')
    
    __table_args__ = (
        UniqueConstraint('channel_id', 'phone_number', name='uq_sessions__channel_phone'),
        CheckConstraint('expires_at > created_at', name='chk_sessions__ttl'),
        CheckConstraint("phone_number ~ '^\\+[1-9]\\d{1,14}$'", name='chk_sessions__phone_e164'),
        CheckConstraint(
            "tenant_id = (SELECT tenant_id FROM whatsapp_channels c WHERE c.id = channel_id)",
            name='fk_sessions__tenant_match'
        ),
        # Index('ix_sessions__tenant_phone_created', 'tenant_id', 'phone_number', 'created_at', postgresql_desc=True),
        Index('ix_sessions__tenant_phone_created', 'tenant_id', 'phone_number', 'created_at'),
        Index('ix_sessions__expires_at', 'expires_at', postgresql_where=text('expires_at < now()')),
        Index('ix_sessions__stage_last_activity', 'conversation_stage', 'last_activity'),
    )

__all__ = ['MenuFlow', 'ConversationSession']