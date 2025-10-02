"""Media File ORM Model"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database.base_model import Base


class MediaFileModel(Base):
    """
    Media file ORM model.
    
    Stores metadata for media files (images, videos, documents, audio)
    sent/received via WhatsApp. Actual files stored in S3.
    """
    
    __tablename__ = "media_files"
    __table_args__ = (
        UniqueConstraint("wa_media_id", name="uq_media_files_wa_media_id"),
        Index("idx_media_account", "account_id"),
        Index("idx_media_wa_id", "wa_media_id"),
        Index("idx_media_message", "message_id"),
        {"schema": "whatsapp"}
    )
    
    # Primary key inherited from Base (id, created_at, updated_at)
    
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    wa_media_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )
    
    message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp.inbound_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    media_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    
    storage_path: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    download_url: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
    
    url_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    
    metadata: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<MediaFileModel(id={self.id}, type={self.media_type})>"