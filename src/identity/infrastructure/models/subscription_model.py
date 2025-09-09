from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# NOTE: reuse your existing enums; keep paths as in your project
from identity.domain.types import SubscriptionStatus
from src.identity.infrastructure.models import TenantModel, PlanModel

# ---------- Base ----------
class Base(DeclarativeBase):
    pass

# ---------- Subscriptions ----------
class SubscriptionModel(Base):
    __tablename__ = "tenant_plan_subscriptions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB), nullable=False, server_default=text("'{}'::jsonb"))
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
    tenant: Mapped["TenantModel"] = relationship(back_populates="subscriptions")
    plan: Mapped["PlanModel"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("tenant_id", "status", name="uq_tenant_subscription_status"),
        CheckConstraint("end_at > start_at", name="ck_subscription_time_order"),
        Index("ix_subscriptions_tenant_status", "tenant_id", "status"),
    )
