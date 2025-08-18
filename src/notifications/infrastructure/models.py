# src/notifications/infrastructure/models.py
"""
Notification system models.
Contains:
- NotificationTemplate (message templates)
- Notification (scheduled/delivered messages)
Important:
- Templates support multiple delivery channels
- Notifications track delivery attempts and status
"""
from uuid import UUID
from datetime import datetime
from typing import Optional, List

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, ENUM, ARRAY

from shared.database import Base

class NotificationTemplate(Base):
    """Notification message template."""
    __tablename__ = 'notification_templates'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(ENUM('APPOINTMENT_REMINDER', 'FEE_REMINDER', 'GENERAL', 'EMERGENCY', name='template_type_enum'), nullable=False)
    content_template: Mapped[str] = mapped_column(nullable=False)
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    delivery_channels: Mapped[List[str]] = mapped_column(ARRAY(ENUM('WHATSAPP', 'SMS', 'EMAIL', name='delivery_channel_enum')), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text('true'))
    created_by: Mapped[UUID] = mapped_column(ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    notifications: Mapped[List['Notification']] = relationship(back_populates='template')
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='uq_tpl__tenant_name'),
        CheckConstraint('array_length(delivery_channels,1) > 0', name='chk_tpl__channels_nonempty'),
    )

class Notification(Base):
    """Scheduled or delivered notification."""
    __tablename__ = 'notifications'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    template_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey('notification_templates.id'), nullable=True)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    priority: Mapped[str] = mapped_column(ENUM('LOW', 'NORMAL', 'HIGH', 'URGENT', name='notification_priority_enum'), nullable=False, server_default='NORMAL')
    delivery_attempts: Mapped[int] = mapped_column(nullable=False, server_default=text('0'))
    max_retry_attempts: Mapped[int] = mapped_column(nullable=False, server_default=text('3'))
    status: Mapped[str] = mapped_column(ENUM('SCHEDULED', 'QUEUED', 'SENT', 'DELIVERED', 'FAILED', 'CANCELLED', name='notification_status_enum'), nullable=False, server_default='SCHEDULED')
    error_message: Mapped[Optional[str]] = mapped_column(nullable=True)
    context_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    # Relationships
    template: Mapped[Optional['NotificationTemplate']] = relationship(back_populates='notifications')
    
    __table_args__ = (
        CheckConstraint('delivery_attempts >= 0 AND max_retry_attempts >= 0', name='chk_notifications__attempts'),
        CheckConstraint("recipient_phone ~ '^\\+[1-9]\\d{1,14}$'", name='chk_notifications__phone_e164'),
        Index('ix_notifications__queue', 'scheduled_at', 'status', 'priority'),
        # Index('ix_notifications__tenant_status_created', 'tenant_id', 'status', 'created_at', postgresql_desc=True),
        Index('ix_notifications__tenant_status_created', 'tenant_id', 'status', 'created_at'),
        Index('ix_notifications__recipient_recent', 'recipient_phone', 'created_at', postgresql_desc=True),
    )

__all__ = ['NotificationTemplate', 'Notification']