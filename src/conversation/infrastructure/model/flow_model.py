# src/conversation/infrastructure/models/flow_model.py
"""SQLAlchemy ORM model for flows."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship

from src.shared_.infrastructure.database.base import Base
from src.conversation.domain.value_objects import FlowStatus


class FlowModel(Base):
    """ORM model for conversation flows."""
    
    __tablename__ = "flows"
    __table_args__ = {"schema": "public"}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLEnum(FlowStatus), nullable=False, default=FlowStatus.DRAFT, index=True)
    version_major = Column(Integer, nullable=False, default=1)
    version_minor = Column(Integer, nullable=False, default=0)
    version_patch = Column(Integer, nullable=False, default=0)
    language = Column(String(10), nullable=False, default="en", index=True)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    
    # Relationships
    steps = relationship("FlowStepModel", back_populates="flow", cascade="all, delete-orphan")
    sessions = relationship("SessionModel", back_populates="flow")
    
    # RLS policy name for this table
    __rls_policy__ = "tenant_isolation"


class FlowStepModel(Base):
    """ORM model for flow steps."""
    
    __tablename__ = "flow_steps"
    __table_args__ = {"schema": "public"}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    flow_id = Column(PGUUID(as_uuid=True), ForeignKey("flows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_key = Column(String(100), nullable=False)
    step_type = Column(String(50), nullable=False, index=True)
    order = Column(Integer, nullable=False)
    prompt = Column(JSONB, nullable=False)  # {language: text}
    options = Column(JSONB, nullable=True)  # [{key, text, next_step}]
    validation = Column(JSONB, nullable=True)  # {type, rules}
    actions = Column(JSONB, nullable=True)  # [{action_type, config}]
    transitions = Column(JSONB, nullable=False, default=dict)  # {condition: next_step}
    metadata = Column(JSONB, nullable=True)
    is_entry_point = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    flow = relationship("FlowModel", back_populates="steps")
    
    # Composite unique constraint
    __table_args__ = (
        {"schema": "public"},
    )