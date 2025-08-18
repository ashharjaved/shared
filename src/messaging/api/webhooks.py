from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.api.schemas import WhatsAppVerifyQuery, WhatsAppInboundPayload, OkResponse
from src.messaging.infrastructure.repositories import ChannelRepository, InboundRepository
from src.shared.security import verify_hub_signature
from src.config import settings
from src.dependencies import get_session
from src.platform.infrastructure.cache import get_cached
import hmac, hashlib

router = APIRouter(prefix="/api/v1/wa", tags=["whatsapp-webhook"])
legacy = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhook"])

def _constant_time_eq(a: str, b: str) -> bool:
    try:
        return hmac.compare_digest(a, b)
    except Exception:
        return False

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

async def receive_old(request: Request):
    raw = await request.body()
    tenant_id = request.headers.get("X-Tenant-Id")
    configured = get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None
    app_secret = (configured or settings.WHATSAPP_APP_SECRET).encode("utf-8")
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not sig.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing signature")
    expected = "sha256=" + hmac.new(app_secret, raw, hashlib.sha256).hexdigest()
    if not _constant_time_eq(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    # Idempotent persist -> ack fast
    # (delegate to handler; it MUST be idempotent)
    return {"status": "accepted"}

@router.post("/{phone_number_id}")
async def receive(phone_number_id: str, request: Request):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    tenant_id = request.headers.get("X-Tenant-Id")
    configured = get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None
    #app_secret = await ConfigRepository.get_app_secret(phone_number_id) or settings.WHATSAPP_APP_SECRET
    app_secret = (configured or settings.WHATSAPP_APP_SECRET)
    if not _sig_valid(app_secret, raw, sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")
    payload = await request.json()
    # Minimal idempotent persist (repo raises on duplicate whatsapp_message_id)
    await InboundRepository.persist_inbound(phone_number_id, payload)
    return {"status": "ok"}

def _sig_valid(app_secret: str, raw_body: bytes, provided: str) -> bool:
    if not provided or not provided.startswith("sha256="):
        return False
    digest = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided.split("=",1)[1], digest)

@router.get("/{phone_number_id}")
async def verify(phone_number_id: str, hub_mode: str, hub_challenge: str, hub_verify_token: str):
    # per-tenant override via ConfigRepository, else fallback to settings
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if hub_mode == "subscribe" and hub_verify_token == expected:
        return int(hub_challenge)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verify failed")
# Legacy paths for tests/back-compat

@legacy.get("/{phone_number_id}")
async def legacy_verify(phone_number_id: str, hub_mode: str, hub_challenge: str, hub_verify_token: str):
    return await verify(phone_number_id, hub_mode, hub_challenge, hub_verify_token)

@legacy.post("/{phone_number_id}")
async def legacy_receive(phone_number_id: str, request: Request):
    return await receive(phone_number_id, request)






