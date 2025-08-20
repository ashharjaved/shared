from __future__ import annotations
from typing import Any, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from .commands import TriggerFlow, RunTick
from .runner import FlowRunner
from ..infrastructure.repositories import FlowRepository, SessionRepository, ConfigRepository
from ...config import Settings

async def handle_trigger_flow(db: AsyncSession, settings: Settings, cmd: TriggerFlow) -> Dict[str, Any]:
    runner = FlowRunner(FlowRepository(db), SessionRepository(db), ConfigRepository(db), settings)
    result = await runner.run_trigger(cmd.tenant_id, cmd.channel_id, cmd.contact_id, cmd.inbound_payload, cmd.event_id)
    return result

# Provided for symmetry; current MVP uses trigger+tick in one go.
async def handle_run_tick(db: AsyncSession, settings: Settings, cmd: RunTick) -> Dict[str, Any]:
    from sqlalchemy import select
    from ..infrastructure.models import ConversationSession
    sess_id = cmd.session_id
    # Load tenant/channel/phone from DB to keep signature small
    row = (await db.execute(select(ConversationSession).where(ConversationSession.id == sess_id))).scalar_one()
    runner = FlowRunner(FlowRepository(db), SessionRepository(db), ConfigRepository(db), settings)
    return await runner.run_trigger(row.tenant_id, row.channel_id, row.phone_number, cmd.inbound_payload, cmd.event_id)
