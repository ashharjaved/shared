# Begin: src/conversation/infrastructure/models.py ***
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from ..domain.value_objects import SessionStatus


class Base(DeclarativeBase):
    pass


class MenuFlowORM(Base):
    __tablename__ = "menu_flows"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    industry_type: Mapped[str] = mapped_column(PGEnum(name="industry_type_enum", create_type=False), nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    is_default: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

    definition_jsonb: Mapped[Dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    created_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)


class ConversationSessionORM(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()"))
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("whatsapp_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(sa.Text, nullable=False)

    current_menu_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("menu_flows.id", ondelete="SET NULL"),
        nullable=True,
    )
    # optional relationship (not required by domain)
    current_menu: Mapped[Optional[MenuFlowORM]] = relationship(lazy="joined")

    context_jsonb: Mapped[Dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    message_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=sa.text("0"))

    # Keep enum name aligned with migration (native_enum disabled on purpose)
    status: Mapped[SessionStatus] = mapped_column(
        sa.Enum(SessionStatus, name="session_status_enum", native_enum=False),
        nullable=False,
        server_default=sa.text("'ACTIVE'"),
    )
    last_activity: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    expires_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now() + interval '30 minutes'"))

    created_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=True)
## End: src/conversation/infrastructure/models.py ***
