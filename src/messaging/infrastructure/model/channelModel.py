# src/messaging/infrastructure/models.py
from sqlalchemy import Column, String, DateTime, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class WhatsAppChannelModel(Base):
    __tablename__ = "wa_channel"
    __table_args__ = (
        Index("wa_channel_tenant_idx", "tenant_id"),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    phone_number_id = Column(String, nullable=False)
    waba_id = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    credentials = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)