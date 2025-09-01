from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

# Prefer using your shared Base to avoid duplicate metadata/engines
from src.shared.database import Base


class WhatsAppChannelModel(Base):
    __tablename__ = "whatsapp_channels"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    phone_number_id: Mapped[str] = mapped_column(Text, nullable=False)
    business_phone: Mapped[str] = mapped_column(Text, nullable=False)

    # Stored encrypted-at-rest (ciphertext). Infra repo encrypts/decrypts.
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_token: Mapped[str] = mapped_column(Text, nullable=False)

    rate_limit_per_second: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    monthly_message_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100000"))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number_id", name="uq_channels_tenant_phone_number"),
        UniqueConstraint("tenant_id", "business_phone", name="uq_channels_tenant_business_phone"),
    )
