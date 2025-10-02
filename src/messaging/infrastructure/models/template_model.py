"""SQLAlchemy ORM models for message templates."""

from sqlalchemy import (
    Column, String, DateTime, Enum as SQLEnum, JSON,
    ForeignKey, Index, UniqueConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.shared_.database.base_model import BaseModel
from src.messaging.domain.entities.template import TemplateStatus, TemplateCategory


class MessageTemplateModel(BaseModel):
    """WhatsApp message template ORM model."""
    
    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("channel_id", "name", "language", name="uq_template_name_lang"),
        Index("ix_templates_tenant_channel", "tenant_id", "channel_id"),
        Index("ix_templates_status", "status"),
        {"schema": "messaging"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("messaging.channels.id"), nullable=False)
    name = Column(String(512), nullable=False)
    language = Column(String(10), nullable=False)
    category = Column(
        SQLEnum(TemplateCategory, native_enum=False),
        nullable=False
    )
    status = Column(
        SQLEnum(TemplateStatus, native_enum=False),
        nullable=False,
        default=TemplateStatus.DRAFT
    )
    components = Column(JSON, nullable=False)  # List of component objects
    whatsapp_template_id = Column(String(255), nullable=True, unique=True)
    rejection_reason = Column(String(1024), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    channel = relationship("ChannelModel", back_populates="templates")
    messages = relationship("MessageModel", back_populates="template")
    
    # RLS policy
    __table_args__ = (
        *__table_args__,
        text("""
            ALTER TABLE messaging.message_templates ENABLE ROW LEVEL SECURITY;
            
            CREATE POLICY templates_tenant_isolation ON messaging.message_templates
                USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
                WITH CHECK (tenant_id = current_setting('app.jwt_tenant')::uuid);
            
            CREATE TRIGGER ensure_tenant_id_templates
                BEFORE INSERT OR UPDATE ON messaging.message_templates
                FOR EACH ROW
                EXECUTE FUNCTION ensure_tenant_id();
        """)
    )