#*** Begin: src/conversation/application/adapter.py ***
from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text, select

from ..domain.repositories.flow_repository import FlowRepository
from ..domain.repositories.session_repository import SessionRepository
from ..infrastructure.repositories.flow_repository_impl import PostgresFlowRepository
from ..infrastructure.repositories.session_repository_impl import PostgresSessionRepository
from ..application.services.conversation_service import ConversationService, ConversationConfig
from ..application.actions import DefaultActionRouter
from ..application.context import RequestContext

logger = logging.getLogger(__name__)

# A resolver that maps channel_id -> tenant_id.
# You may inject your own implementation (e.g., call Messaging's ChannelRepository),
# or rely on the default that uses a SECURITY DEFINER function from Stage-3.
TenantResolver = Callable[[async_sessionmaker[AsyncSession], UUID], Awaitable[UUID]]


async def _default_tenant_resolver(sf: async_sessionmaker[AsyncSession], channel_id: UUID) -> UUID:
    """
    Default resolver uses a Stage-3 DB helper:

        CREATE OR REPLACE FUNCTION resolve_whatsapp_channel_tenant(p_channel uuid)
        RETURNS uuid
        LANGUAGE sql
        SECURITY DEFINER
        AS $$
          SELECT tenant_id FROM whatsapp_channels WHERE id = p_channel LIMIT 1
        $$;

    This function must exist and be owned by a role with access to the table.
    """
    async with sf() as s:
        cur = await s.execute(text("SELECT resolve_whatsapp_channel_tenant(:cid)"), {"cid": str(channel_id)})
        tid = cur.scalar_one_or_none()
        if not tid:
            raise RuntimeError("Unable to resolve tenant for channel")
        return UUID(str(tid))


async def make_conversation_reply(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    channel_id: UUID,
    from_phone: str,
    text_in: str,
    # Optional overrides/wiring:
    tenant_resolver: TenantResolver = _default_tenant_resolver,
    user_id: Optional[UUID] = None,       # webhook is unauthenticated; keep None
    roles_csv: Optional[str] = None,
    cfg: Optional[ConversationConfig] = None,
    industry_hint: Optional[str] = None,  # optional filter when selecting default flow first time
    request_id: str = "webhook",
) -> str:
    """
    Pure function used by the WhatsApp webhook.

    Returns only the reply text. Sending is performed by the Messaging module.
    """
    # 1) Resolve tenant from channel (Stage-3 infra)
    tenant_id = await tenant_resolver(session_factory, channel_id)

    # 2) Build repositories (RLS enforced inside repositories via GUCs)
    flows: FlowRepository = PostgresFlowRepository(
        session_factory=session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        roles_csv=roles_csv,
    )
    sessions: SessionRepository = PostgresSessionRepository(
        session_factory=session_factory,
        tenant_id=tenant_id,
        user_id=user_id,
        roles_csv=roles_csv,
    )

    # 3) Build service + default router
    svc = ConversationService(
        flows=flows,
        sessions=sessions,
        action_router=DefaultActionRouter(),
        config=cfg,
    )

    # 4) Execute state machine
    ctx = RequestContext(request_id=request_id, tenant_id=tenant_id, user_id=user_id, channel_id=channel_id)
    try:
        reply = await svc.handle_message(
            channel_id=channel_id,
            user_phone=from_phone,
            text=text_in,
            ctx=ctx,
            industry_hint=industry_hint,
        )
        return reply
    except Exception as e:
        # Never leak internals to user; return a safe fallback and log the error.
        logger.exception("make_conversation_reply failed: %s", e, extra={
            "tenant_id": str(tenant_id),
            "channel_id": str(channel_id),
            "from_phone": from_phone,
            "request_id": request_id,
        })
        return "Sorry, something went wrong. Please try again."
#*** End: src/conversation/application/adapter.py ***
