from datetime import datetime
from uuid import UUID
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

class WhatsAppMessageModel(Base):
    __tablename__ = "message"
    __table_args__ = (
        Index("message_waid_idx", "wa_message_id"),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    channel_id = Column(UUID(as_uuid=True), nullable=False)
    wa_message_id = Column(String, nullable=True)
    direction = Column(String, nullable=False)
    from_msisdn = Column(String, nullable=False)
    to_msisdn = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    template_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued")
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
