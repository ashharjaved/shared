# src/platform/infrastructure/models.py
"""
Shared platform infrastructure models.
Contains:
- TenantConfigurations (per-tenant key/value store)
- OutboxEvents (transactional outbox pattern)
- IdempotencyKeys (idempotent operation tracking)
Important:
- These are tenant-scoped but used across contexts
- OutboxEvents must be processed in order
"""
from uuid import UUID
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, text, String, CheckConstraint, UniqueConstraint, Index, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from shared.database import Base

class Base(DeclarativeBase):
    pass

# Enum name must match the DB enum 'config_type_enum' (already created).
CONFIG_TYPE_ENUM = SAEnum(
    "GENERAL", "WHITELABEL", "INTEGRATION", "RISK",
    name="config_type_enum", native_enum=True
)

class TenantConfiguration(Base):
    """Per-tenant configuration key/value pairs."""
    __tablename__ = 'tenant_configurations'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    config_key: Mapped[str] = mapped_column(String(100), nullable=False)
    config_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    config_type: Mapped[str] = mapped_column(CONFIG_TYPE_ENUM, nullable=False, server_default=text("'GENERAL'"))
    is_encrypted: Mapped[bool] = mapped_column(nullable=False, server_default=text('false'))
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'config_key', name='uq_config__tenant_key'),
    )

class OutboxEvent(Base):
    """Transactional outbox for reliable event publishing."""
    __tablename__ = 'outbox_events'
    
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(nullable=False)
    payload_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    __table_args__ = (
        Index('ix_outbox__tenant_created', 'tenant_id', 'created_at'),
        Index('ix_outbox__unprocessed', 'tenant_id', 'processed_at', postgresql_where=text('processed_at IS NULL')),
    )

class IdempotencyKey(Base):
    """Idempotency key tracking for safe operation retries."""
    __tablename__ = 'idempotency_keys'
    
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey('tenants.id'), primary_key=True)
    endpoint: Mapped[str] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text('now()'))
    expires_at: Mapped[datetime] = mapped_column(server_default=text('now() + interval \'24 hours\''))
    
    __table_args__ = (
        Index('ix_idem__expiry', 'expires_at'),
    )

__all__ = ['TenantConfiguration', 'OutboxEvent', 'IdempotencyKey']