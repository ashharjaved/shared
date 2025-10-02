"""Delivery status tracking model."""

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.shared_.database.base_model import BaseModel


class DeliveryStatusModel(BaseModel):
    """Delivery status ORM model."""
    
    __tablename__ = "delivery_status"
    __table_args__ = (
        Index("ix_delivery_status_message", "message_id"),
        Index("ix_delivery_status_timestamp", "timestamp"),
        {"schema": "messaging"}
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messaging.messages.id"), nullable=False)
    status = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    error_code = Column(String(50), nullable=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    message = relationship("MessageModel", back_populates="delivery_statuses")