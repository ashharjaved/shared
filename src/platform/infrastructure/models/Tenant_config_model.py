from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
    text,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

# SQLAlchemy Declarative base

class Base(DeclarativeBase):
    pass


# --- Enums (mirror DB) -------------------------------------------------------

ConfigTypeEnum = PG_ENUM(
    "GENERAL", "SECURITY", "BILLING",
    name="config_type_enum",
    create_type=False,  # enum is created by migration
)

RateLimitScopeEnum = PG_ENUM(
    "TENANT", "GLOBAL",
    name="rate_limit_scope_enum",
    create_type=False,
)


# --- Tables ------------------------------------------------------------------

class TenantConfigurationORM(Base):
    """
    Mirrors public.tenant_configurations 1:1.

    Columns & constraints are aligned to the Stage-2 SQL schema:
    - PK id (uuid)
    - tenant_id (uuid) NOT NULL  -> FK tenants(id) (assumed existing from Stage-1)
    - config_key varchar(100) NOT NULL
    - config_value jsonb NOT NULL
    - config_type config_type_enum NOT NULL DEFAULT 'GENERAL'
    - is_encrypted boolean NOT NULL DEFAULT false
    - created_at timestamptz NOT NULL DEFAULT now()
    - updated_at timestamptz NOT NULL DEFAULT now()
    - deleted_at timestamptz NULL
    - UNIQUE(tenant_id, config_key) via ix_tenant_config__tenant_key + uq_tenant_config
    - GIN index on config_value (created by migration)
    - Triggers: set_updated_at, ensure_tenant_id, outbox wrapper (created by migration)
    """
    __tablename__ = "tenant_configurations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    config_type: Mapped[str] = mapped_column(ConfigTypeEnum, nullable=False, server_default=text("'GENERAL'"))
    is_encrypted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "config_key", name="uq_tenant_config"),
        Index("ix_tenant_config__tenant_key", "tenant_id", "config_key", unique=True),
        # Optional key format guard (keep aligned with VO); comment out to match exact DB CHECK state
        # CheckConstraint("config_key ~ '^[a-z0-9_.:-]{1,100}$'", name="ck_tenant_config__key_format"),
    )


class RateLimitPolicyORM(Base):
    """
    Mirrors public.rate_limit_policies 1:1.

    Columns & constraints aligned to Stage-2 SQL schema:
    - id uuid PK
    - tenant_id uuid NULL -> GLOBAL when NULL
    - scope rate_limit_scope_enum NOT NULL
    - requests_per_minute int NOT NULL
    - burst_limit int NOT NULL DEFAULT 0
    - timestamps, soft delete
    - UNIQUE(tenant_id, scope) with supplemental unique for (scope) WHERE tenant_id IS NULL
    - Triggers: set_updated_at, ensure_tenant_id, outbox wrapper (created by migration)
    """
    __tablename__ = "rate_limit_policies"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    scope: Mapped[str] = mapped_column(RateLimitScopeEnum, nullable=False)
    requests_per_minute: Mapped[int] = mapped_column(nullable=False)
    burst_limit: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "scope", name="uq_rate_limit"),
        Index("ix_rate_limit__tenant_scope", "tenant_id", "scope", unique=True),
        Index("ix_rate_limit__global_scope_unique", "scope", unique=True, postgresql_where=text("tenant_id IS NULL")),
    )


# --- RLS guard helper --------------------------------------------------------

async def assert_rls_context(session: AsyncSession) -> None:
    """
    Ensure RLS tenant context is present for the session.
    Calls public.jwt_tenant() and raises if NULL.
    """
    result = await session.execute(text("SELECT public.jwt_tenant()"))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise PermissionError("Missing RLS context: set GUC app.jwt_tenant before queries.")
