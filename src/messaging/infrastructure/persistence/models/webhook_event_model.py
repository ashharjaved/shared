"""Webhook Event ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class WebhookEventModel(Base):
    """
    Webhook event ORM model.
    
    Stores raw webhook payloads from WhatsApp for audit and replay.
    Events are processed asynchronously and marked as processed.
    """
    
    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("idx_webhook_events_account", "account_id"),
        Index("idx_webhook_events_type", "event_type"),
        Index(
            "idx_webhook_events_unprocessed",
            "created_at",
            postgresql_where=text("processed = false")
        ),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    account_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    raw_payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    
    signature: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    
    signature_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    def __repr__(self) -> str:
        return f"<WebhookEventModel(id={self.id}, type={self.event_type})>"