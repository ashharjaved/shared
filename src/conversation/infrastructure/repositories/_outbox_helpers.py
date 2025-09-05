#* Begin: src/conversation/infrastructure/repositories/_outbox_helpers.py ***
from __future__ import annotations

from typing import Mapping
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# Safe to import JSONValue from domain:
from ...domain.value_objects import JSONValue


async def try_emit_outbox(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    event_type: str,
    payload: Mapping[str, JSONValue],
) -> None:
    """
    Best-effort insert into outbox_events if table exists.
    No raise on failure (so conversation flow is never blocked).
    """
    try:
        await session.execute(
            text(
                """
                INSERT INTO outbox_events (id, tenant_id, event_type, payload, created_at)
                VALUES (uuid_generate_v4(), :tid, :etype, :payload::jsonb, now())
                """
            ),
            {"tid": str(tenant_id), "etype": event_type, "payload": dict(payload)},
        )
    except Exception:
        # swallow silently; logging can be added if desired
        pass
#* End: src/conversation/infrastructure/repositories/_outbox_helpers.py ***
