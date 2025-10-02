"""
SQLAlchemy Declarative Base
All ORM models inherit from this
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    
    Provides common columns:
    - id (UUID, primary key)
    - created_at (timestamptz, server default NOW())
    - updated_at (timestamptz, server default NOW(), onupdate NOW())
    
    All models should inherit from this and add their specific columns.
    """
    
    # Type annotations for common columns
    type_annotation_map = {
        UUID: PGUUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }
    
    # Common columns for all tables
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        """String representation showing table name and id."""
        return f"<{self.__class__.__name__}(id={self.id})>"