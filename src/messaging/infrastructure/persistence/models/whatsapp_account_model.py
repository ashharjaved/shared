"""WhatsApp Account ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class WhatsAppAccountModel(Base):
    """
    WhatsApp Business Account ORM model.
    
    Stores WhatsApp Business API account configuration and credentials.
    Each organization can have multiple WhatsApp accounts.
    """
    
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("phone_number_id", name="uq_accounts_phone_number_id"),
        Index("idx_wa_accounts_org", "organization_id"),
        Index("idx_wa_accounts_phone", "display_phone_number"),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    
    phone_number_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    
    display_phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    business_account_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    access_token_encrypted: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    
    webhook_verify_token_encrypted: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )
    
    rate_limit_tier: Mapped[str] = mapped_column(
        String(20),
        default="standard",
        nullable=False,
    )
    
    metadata: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<WhatsAppAccountModel(id={self.id}, phone={self.display_phone_number})>"