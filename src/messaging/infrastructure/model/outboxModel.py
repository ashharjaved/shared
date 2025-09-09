from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class OutboxModel(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("outbox_avail_idx", "available_at"),
        UniqueConstraint("dedupe_key", name="uq_outbox_dedupe_key"),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    channel_id = Column(UUID(as_uuid=True), nullable=False)
    kind = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    dedupe_key = Column(String, nullable=True, unique=True)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=12)
    last_error = Column(Text, nullable=True)
    claimed_by = Column(String, nullable=True)
    claimed_at = Column(DateTime, nullable=True)