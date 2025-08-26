from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Boolean,
    String,
    UniqueConstraint,
    ForeignKey,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID, ENUM as PGENUM
from sqlalchemy.orm import Mapped, mapped_column, declarative_base, relationship


from ..domain.entities import ConfigType

Base = declarative_base()
class TenantConfiguration(Base):
    __tablename__ = "tenant_configurations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    # Map to existing Postgres enum type (no type creation in SA)
    config_type: Mapped[ConfigType] = mapped_column(
        PGENUM(ConfigType, name="config_type_enum", create_type=False),
        nullable=False,
        server_default=text("'GENERAL'::config_type_enum"),
    )

    is_encrypted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "config_key", name="uq_config__tenant_key"),
    )
