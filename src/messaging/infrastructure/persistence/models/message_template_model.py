"""
SQLAlchemy ORM Model for MessageTemplate
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class MessageTemplateModel(Base):
    """ORM model for whatsapp.message_templates table."""
    
    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "language", name="uq_template_name_lang"),
        Index("idx_template_tenant_status", "tenant_id", "status"),
        {"schema": "whatsapp"}
    )
    
    # Override base id
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        nullable=False,
    )
    
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("identity.tenants.id"),
        nullable=False,
    )
    
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    body_text: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="draft",
        nullable=False,
    )
    
    header_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    footer_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    buttons: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    
    variables: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=list,
        nullable=False,
    )
    
    rejection_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    
    wa_template_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    # Override created_at and updated_at
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
    )