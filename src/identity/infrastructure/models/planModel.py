from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# NOTE: reuse your existing enums; keep paths as in your project
from identity.infrastructure.models.subscription_model import SubscriptionModel

# ---------- Base ----------
class Base(DeclarativeBase):
    pass

# ---------- Plans ----------
class PlanModel(Base):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_inr: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)
    features: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now() at time zone 'utc'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now() at time zone 'utc'"),
        server_onupdate=text("now() at time zone 'utc'"),
    )

    # Relationships
    subscriptions: Mapped[List["SubscriptionModel"]] = relationship(back_populates="plan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_plans_active", "is_active"),
    )
