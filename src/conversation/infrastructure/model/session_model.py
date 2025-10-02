# src/conversation/infrastructure/models/session_model.py
"""SQLAlchemy ORM model for sessions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from src.shared_.infrastructure.database.base import Base
from src.conversation.domain.value_objects import SessionStatus


class SessionModel(Base):
    """ORM model for conversation sessions."""
    
    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_tenant_channel_msisdn", "tenant_id", "channel_id", "user_msisdn"),
        Index("idx_sessions_status_expires", "status", "expires_at"),
        {"schema": "public"},
    )
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    channel_id = Column(PGUUID(as_uuid=True), ForeignKey("channels.id"), nullable=False, index=True)
    user_msisdn = Column(String(20), nullable=False, index=True)
    flow_id = Column(PGUUID(as_uuid=True), ForeignKey("flows.id"), nullable=False, index=True)
    current_step_key = Column(String(100), nullable=False)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE, index=True)
    language = Column(String(10), nullable=False, default="en")
    context = Column(JSONB, nullable=False, default=dict)
    message_history = Column(JSONB, nullable=False, default=list)
    intent_history = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    
    # Relationships
    flow = relationship("FlowModel", back_populates="sessions")
    logs = relationship("ConversationLogModel", back_populates="session", cascade="all, delete-orphan")
    
    # RLS policy
    __rls_policy__ = "tenant_isolation"


class SessionContextModel(Base):
    """ORM model for session context (alternative key-value storage)."""
    
    __tablename__ = "session_context"
    __table_args__ = (
        Index("idx_session_context_session_key", "session_id", "context_key"),
        {"schema": "public"},
    )
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    context_key = Column(String(100), nullable=False)
    context_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConversationLogModel(Base):
    """ORM model for conversation audit logs."""
    
    __tablename__ = "conversation_logs"
    __table_args__ = (
        Index("idx_conversation_logs_session", "session_id", "created_at"),
        Index("idx_conversation_logs_tenant_msisdn", "tenant_id", "user_msisdn"),
        {"schema": "public"},
    )
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    channel_id = Column(PGUUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    user_msisdn = Column(String(20), nullable=False, index=True)
    flow_id = Column(PGUUID(as_uuid=True), ForeignKey("flows.id"), nullable=False)
    step_key = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # user, bot, system
    message = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True, index=True)
    confidence = Column(String(20), nullable=True)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationships
    session = relationship("SessionModel", back_populates="logs")
    
    # RLS policy
    __rls_policy__ = "tenant_isolation"