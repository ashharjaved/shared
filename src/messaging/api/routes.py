from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.api.schemas import OnboardingRequest, ChannelResponse, OutboundRequest, OkResponse
from src.messaging.application.commands import LinkChannel, PrepareOutboundMessage
from src.messaging.application.handlers import MessagingHandlers
from src.messaging.infrastructure.repositories import ChannelRepository
from src.messaging.infrastructure.whatsapp_client import build_outbound_payload
from src.shared.security import get_principal
from src.identity.domain.entities import Principal
from src.dependencies import get_session
from src.config import settings

router = APIRouter(prefix="/api/v1/wa", tags=["whatsapp"])

@router.post("/channel", response_model=ChannelResponse)
async def link_channel(
    body: OnboardingRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    data = body.dict(exclude_unset=True)
    if "access_token" in data:
        data["access_token_ciphertext"] = data.pop("access_token")
    if "verify_token" in data:
        data["webhook_verify_token_ciphertext"] = data.pop("verify_token")

    handler = MessagingHandlers(session)
    resp = await handler.handle_link_channel(LinkChannel(tenant_id=principal.tenant_id, data=data))
    await session.commit()
    return ChannelResponse(**resp)

@router.get("/channel", response_model=ChannelResponse)
async def get_channel(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    repo = ChannelRepository(session)
    ch = await repo.get_by_tenant(principal.tenant_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return ChannelResponse(
        phone_number_id=ch.phone_number_id,
        business_phone=getattr(ch, "business_phone", None),
        waba_id=getattr(ch, "waba_id", None),
        display_name=getattr(ch, "display_name", None),
        is_active=getattr(ch, "is_active", True),
    )

@router.post("/messages", response_model=OkResponse)
async def outbound_preview(
    body: OutboundRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    repo = ChannelRepository(session)
    ch = await repo.get_by_tenant(principal.tenant_id)
    if not ch:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel not onboarded")

    payload = build_outbound_payload(
        api_base=settings.WHATSAPP_API_BASE,
        phone_number_id=ch.phone_number_id,
        to=body.to,
        text=body.text,
        template=body.template.dict() if body.template else None,
        media=body.media.dict() if body.media else None,
    )
    return OkResponse(ok=True, data=payload)
