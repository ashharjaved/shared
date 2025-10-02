"""SQLAlchemy ORM models for channels."""

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Enum as SQLEnum,
    ForeignKey, Index, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.shared_.database.base_model import BaseModel
from src.messaging.domain.entities.channel import ChannelStatus


class ChannelModel(BaseModel):
    """WhatsApp channel ORM model."""
    
    __tablename__ = "channels"
    __table_args__ = (
        Index("ix_channels_tenant_id", "tenant_id"),
        Index("ix_channels_phone_number_id", "phone_number_id"),
        CheckConstraint("rate_limit_per_second > 0 AND rate_limit_per_second <= 1000"),
        CheckConstraint("current_month_usage >= 0"),
        {"schema": "messaging"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    phone_number_id = Column(String(255), nullable=False, unique=True)
    business_phone = Column(String(20), nullable=False)
    access_token = Column(String(2048), nullable=False)  # Encrypted
    status = Column(
        SQLEnum(ChannelStatus, native_enum=False),
        nullable=False,
        default=ChannelStatus.PENDING
    )
    rate_limit_per_second = Column(Integer, nullable=False, default=80)
    monthly_message_limit = Column(Integer, nullable=True)
    current_month_usage = Column(Integer, nullable=False, default=0)
    webhook_verify_token = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    messages = relationship("MessageModel", back_populates="channel", lazy="select")
    templates = relationship("MessageTemplateModel", back_populates="channel", lazy="select")
    
    # RLS policy
    __table_args__ = (
        *__table_args__,
        text("""
            ALTER TABLE messaging.channels ENABLE ROW LEVEL SECURITY;
            
            CREATE POLICY channels_tenant_isolation ON messaging.channels
                USING (tenant_id = current_setting('app.jwt_tenant')::uuid)
                WITH CHECK (tenant_id = current_setting('app.jwt_tenant')::uuid);
            
            CREATE TRIGGER ensure_tenant_id_channels
                BEFORE INSERT OR UPDATE ON messaging.channels
                FOR EACH ROW
                EXECUTE FUNCTION ensure_tenant_id();
        """)
    )