from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ENUM as PGEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableDict
from src.shared.database import Base

# Map to existing PostgreSQL enum types created by migration (do not recreate)
PG_MESSAGE_DIRECTION = PGEnum("INBOUND", "OUTBOUND", name="message_direction", create_type=False)
PG_MESSAGE_TYPE = PGEnum("TEXT", "TEMPLATE", "MEDIA", name="message_type", create_type=False)
PG_MESSAGE_STATUS = PGEnum("QUEUED", "SENT", "DELIVERED", "READ", "FAILED", name="message_status", create_type=False)


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    direction: Mapped[str] = mapped_column(PG_MESSAGE_DIRECTION, nullable=False)
    from_phone: Mapped[str] = mapped_column(Text, nullable=False)
    to_phone: Mapped[str] = mapped_column(Text, nullable=False)

    content_jsonb: Mapped[Dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSONB), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)

    message_type: Mapped[str] = mapped_column(PG_MESSAGE_TYPE, nullable=False)
    status: Mapped[str] = mapped_column(PG_MESSAGE_STATUS, nullable=False, server_default=text("'QUEUED'"))

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    status_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["channel_id", "tenant_id"],
            ["whatsapp_channels.id", "whatsapp_channels.tenant_id"],
            name="fk_messages_channel_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_messages_tenant_created", "tenant_id", "created_at"),
        Index("ix_messages_status", "tenant_id", "status", "created_at"),
    )
