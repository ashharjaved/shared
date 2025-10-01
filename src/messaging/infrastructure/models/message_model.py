"""SQLAlchemy ORM models for messages."""

from sqlalchemy import (
    Column, String, Integer, DateTime, Enum as SQLEnum, JSON,
    ForeignKey, Index, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.shared.database.base_model import BaseModel
from src.messaging.domain.entities.message import MessageDirection, MessageStatus, MessageType


class MessageModel(BaseModel):
    """WhatsApp message ORM model."""
    
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_tenant_channel", "tenant_id", "channel_id"),
        Index("ix_messages_whatsapp_id", "whatsapp_message_id"),
        Index("ix_messages_status_direction", "status", "direction"),
        Index("ix_messages_created_at", "created_at"),
        CheckConstraint("retry_count >= 0"),
        {"schema": "messaging"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("messaging.channels.id"), nullable=False)
    direction = Column(
        SQLEnum(MessageDirection, native_enum=False),
        nullable=False
    )
    message_type = Column(
        SQLEnum(MessageType, native_enum=False),
        nullable=False
    )
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)
    content = Column(String(4096), nullable=True)
    media_url = Column(String(2048), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("messaging.message_templates.id"), nullable=True)
    template_variables = Column(JSON, nullable=True)
    whatsapp_message_id = Column(String(255), nullable=True, unique=True)
    status = Column(
        SQLEnum(MessageStatus, native_enum=False),
        nullable=False,
        default=MessageStatus.QUEUED
    )
    error_code = Column(String(50), nullable=True)
    error_message = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=12)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    channel = relationship("ChannelModel", back_populates="messages")
    template = relationship("MessageTemplateModel", back_populates="messages")
    
    # RLS policy
    __table_args__ = (
        *__table_args__,
        text("""
            ALTER TABLE messaging.messages ENABLE ROW LEVEL SECURITY;
            
            CREATE POLICY messages_tenant_isolation ON messaging.messages
                USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
                WITH CHECK (tenant_id = current_setting('app.jwt_tenant')::uuid);
            
            CREATE TRIGGER ensure_tenant_id_messages
                BEFORE INSERT OR UPDATE ON messaging.messages
                FOR EACH ROW
                EXECUTE FUNCTION ensure_tenant_id();
                
            -- Outbox trigger for message events
            CREATE TRIGGER messages_outbox_trigger
                AFTER INSERT OR UPDATE ON messaging.messages
                FOR EACH ROW
                EXECUTE FUNCTION create_outbox_event();
        """)
    )