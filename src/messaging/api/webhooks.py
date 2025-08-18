from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.api.schemas import WhatsAppVerifyQuery, WhatsAppInboundPayload, OkResponse
from src.messaging.infrastructure.repositories import ChannelRepository, InboundRepository
from src.shared.security import verify_hub_signature
from src.config import settings
from src.dependencies import get_session

router = APIRouter(prefix="/api/v1/wa", tags=["whatsapp-webhook"])

@router.get("/webhook", response_class=Response)
async def verify_webhook(q: WhatsAppVerifyQuery = Depends()):
    if q.hub_verify_token != settings.WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad verify token")
    return Response(content=q.hub_challenge, media_type="text/plain")

@router.post("/webhook", response_model=OkResponse)
async def inbound_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    sig = request.headers.get("X-Hub-Signature-256")
    raw = await request.body()
    if not verify_hub_signature(raw, settings.WHATSAPP_APP_SECRET, sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = WhatsAppInboundPayload.parse_raw(raw)
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload")

    repo = ChannelRepository(session)
    pn_ids = payload.phone_number_ids()
    if not pn_ids:
        return OkResponse(ok=True, details="No phone_number_id present")
    channel = await repo.get_by_phone_number_id(pn_ids[0])
    if not channel:
        return OkResponse(ok=True, details="Unknown phone_number_id")

    irepo = InboundRepository(session)
    created = 0
    for m in payload.iter_messages():
        res = await irepo.upsert_inbound_message(
            tenant_id=str(channel.tenant_id),
            channel_id=str(channel.id),
            whatsapp_message_id=m.id,
            direction="INBOUND",
            from_phone=m.from_ or getattr(channel, "business_phone", ""),
            to_phone=m.to or getattr(channel, "business_phone", ""),
            message_type=m.type or "text",
            content_jsonb=m.dict(by_alias=True),
            status="DELIVERED",
        )
        if res:
            created += 1

    updated = 0
    for s in payload.iter_statuses():
        if await irepo.apply_status_update(vendor_message_id=s.id, vendor_status=s.status):
            updated += 1

    await session.commit()
    return OkResponse(ok=True, details="Processed", data={"created": created, "updated": updated})
