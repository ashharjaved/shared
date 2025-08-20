# from __future__ import annotations
# from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
# from sqlalchemy.ext.asyncio import AsyncSession

# from src.messaging.api.schemas import WhatsAppVerifyQuery, WhatsAppInboundPayload, OkResponse
# from src.messaging.infrastructure.repositories import ChannelRepository, InboundRepository
# from src.shared.security import verify_hub_signature
# from src.config import settings
# from src.dependencies import get_session
# from src.platform.infrastructure.cache import get_cached
# import hmac, hashlib

# router = APIRouter(prefix="/api/v1/wa", tags=["whatsapp-webhook"])
# legacy = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhook"])

# def _constant_time_eq(a: str, b: str) -> bool:
#     try:
#         return hmac.compare_digest(a, b)
#     except Exception:
#         return False

# @router.get("/webhook", response_class=Response)
# async def verify_webhook(request: Request, q: WhatsAppVerifyQuery = Depends()):
#     tenant_id = request.headers.get("X-Tenant-Id")
#     configured = get_cached(tenant_id, "whatsapp.verify_token") if tenant_id else None
#     expected = configured or settings.WHATSAPP_VERIFY_TOKEN
#     if q.hub_verify_token != expected:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad verify token")
#     return Response(content=q.hub_challenge, media_type="text/plain")

# @router.post("/webhook", response_model=OkResponse)
# async def inbound_webhook(request: Request, session: AsyncSession = Depends(get_session)):
#     sig = request.headers.get("X-Hub-Signature-256")
#     raw = await request.body()
#     tenant_id = request.headers.get("X-Tenant-Id")
#     configured_secret = get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None
#     app_secret = configured_secret or settings.WHATSAPP_APP_SECRET
#     if not verify_hub_signature(raw, app_secret, sig):
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

#     try:
#         payload = WhatsAppInboundPayload.parse_raw(raw)
#     except Exception:
#         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid payload")

#     repo = ChannelRepository(session)
#     pn_ids = payload.phone_number_ids()
#     if not pn_ids:
#         return OkResponse(ok=True, details="No phone_number_id present")
#     channel = await repo.get_by_phone_number_id(pn_ids[0])
#     if not channel:
#         return OkResponse(ok=True, details="Unknown phone_number_id")

#     irepo = InboundRepository(session)
#     created = 0
#     for m in payload.iter_messages():
#         res = await irepo.upsert_inbound_message(
#             tenant_id=str(channel.tenant_id),
#             channel_id=str(channel.id),
#             whatsapp_message_id=m.id,
#             direction="INBOUND",
#             from_phone=m.from_ or getattr(channel, "business_phone", ""),
#             to_phone=m.to or getattr(channel, "business_phone", ""),
#             message_type=m.type or "text",
#             content_jsonb=m.dict(by_alias=True),
#             status="DELIVERED",
#         )
#         if res:
#             created += 1

#     updated = 0
#     for s in payload.iter_statuses():
#         if await irepo.apply_status_update(vendor_message_id=s.id, vendor_status=s.status):
#             updated += 1

#     await session.commit()
#     return OkResponse(ok=True, details="Processed", data={"created": created, "updated": updated})

# async def receive_old(request: Request):
#     raw = await request.body()
#     tenant_id = request.headers.get("X-Tenant-Id")
#     configured = get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None
#     app_secret = (configured or settings.WHATSAPP_APP_SECRET).encode("utf-8")
#     sig = request.headers.get("X-Hub-Signature-256", "")
#     if not sig.startswith("sha256="):
#         raise HTTPException(status_code=401, detail="Missing signature")
#     expected = "sha256=" + hmac.new(app_secret, raw, hashlib.sha256).hexdigest()
#     if not _constant_time_eq(sig, expected):
#         raise HTTPException(status_code=401, detail="Invalid signature")
#     # Idempotent persist -> ack fast
#     # (delegate to handler; it MUST be idempotent)
#     return {"status": "accepted"}

# @router.post("/{phone_number_id}")
# async def receive(phone_number_id: str, request: Request):
#     raw = await request.body()
#     sig = request.headers.get("X-Hub-Signature-256", "")
#     tenant_id = request.headers.get("X-Tenant-Id")
#     configured = get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None
#     #app_secret = await ConfigRepository.get_app_secret(phone_number_id) or settings.WHATSAPP_APP_SECRET
#     app_secret = (configured or settings.WHATSAPP_APP_SECRET)
#     if not _sig_valid(app_secret, raw, sig):
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid signature")
#     payload = await request.json()
#     # Minimal idempotent persist (repo raises on duplicate whatsapp_message_id)
#     await InboundRepository.persist_inbound(phone_number_id, payload)
#     return {"status": "ok"}

# def _sig_valid(app_secret: str, raw_body: bytes, provided: str) -> bool:
#     if not provided or not provided.startswith("sha256="):
#         return False
#     digest = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
#     return hmac.compare_digest(provided.split("=",1)[1], digest)

# @router.get("/{phone_number_id}")
# async def verify(phone_number_id: str, hub_mode: str, hub_challenge: str, hub_verify_token: str):
#     # per-tenant override via ConfigRepository, else fallback to settings
#     expected = settings.WHATSAPP_VERIFY_TOKEN
#     if hub_mode == "subscribe" and hub_verify_token == expected:
#         return int(hub_challenge)
#     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="verify failed")

# @legacy.get("/{phone_number_id}")
# async def legacy_verify(phone_number_id: str, hub_mode: str, hub_challenge: str, hub_verify_token: str):
#     return await verify(phone_number_id, hub_mode, hub_challenge, hub_verify_token)

# @legacy.post("/{phone_number_id}")
# async def legacy_receive(phone_number_id: str, request: Request):
#     return await receive(phone_number_id, request)
#################################---------------------------------------------------------
from __future__ import annotations

import hmac
import hashlib
from typing import Any, Dict, Iterable, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from ...shared.security import get_principal
from src.config import Settings, get_settings, settings
from src.conversation.application.commands import TriggerFlow
from src.conversation.application.handlers import handle_trigger_flow
from src.dependencies import get_session
from src.platform.infrastructure.cache import get_cached
from src.messaging.infrastructure.repositories import ChannelRepository, InboundRepository
from src.shared.security import verify_hub_signature

router = APIRouter(prefix="/api/v1/wa", tags=["whatsapp-webhook"])


# ---------------------------------------------------------------------
# Helpers to safely traverse WhatsApp payloads
# ---------------------------------------------------------------------
def _first(items: Iterable[Any], default=None) -> Any:
    for x in items or []:
        return x
    return default


def _get_phone_number_id(payload: Dict[str, Any]) -> Optional[str]:
    entry = _first(payload.get("entry", []))
    change = _first(entry.get("changes")) if entry else None
    value = (change or {}).get("value", {})
    meta = value.get("metadata", {})
    # WA Cloud API sends phone_number_id in metadata; display_phone_number is also present
    return meta.get("phone_number_id") or meta.get("display_phone_number")


def _iter_messages(payload: Dict[str, Any]):
    entry = _first(payload.get("entry",[]))
    change = _first(entry.get("changes")) if entry else None
    value = (change or {}).get("value", {})
    for m in value.get("messages", []) or []:
        yield {
            "id": m.get("id"),
            "from": m.get("from", ""),
            "to": value.get("metadata", {}).get("display_phone_number", ""),
            "type": m.get("type", "text"),
            "raw": m,
        }


def _iter_statuses(payload: Dict[str, Any]):
    entry = _first(payload.get("entry",[]))
    change = _first(entry.get("changes")) if entry else None
    value = (change or {}).get("value", {})
    for s in value.get("statuses", []) or []:
        yield {
            "id": s.get("id", ""),
            "status": s.get("status", ""),
            "raw": s,
        }


# ---------------------------------------------------------------------
# Webhook GET — verify token
# ---------------------------------------------------------------------
@router.get("/webhook", response_class=Response)
async def verify_webhook(request: Request) -> Response:
    qp = request.query_params
    hub_mode = qp.get("hub.mode")
    hub_challenge = qp.get("hub.challenge")
    hub_verify_token = qp.get("hub.verify_token")

    if hub_mode != "subscribe" or not hub_challenge or not hub_verify_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verify params")

    tenant_id = request.headers.get("X-Tenant-Id")
    expected = (get_cached(tenant_id, "whatsapp.verify_token") if tenant_id else None) or settings.WHATSAPP_VERIFY_TOKEN

    if hub_verify_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad verify token")

    # Echo back the challenge per WA requirement
    return Response(content=str(hub_challenge), media_type="text/plain")


# ---------------------------------------------------------------------
# Webhook POST — signature verify + inbound persist (idempotent)
# ---------------------------------------------------------------------
@router.post("/webhook")
async def inbound_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    # 1) Verify signature (per-tenant secret -> fallback to global)
    sig = request.headers.get("X-Hub-Signature-256")
    raw = await request.body()
    tenant_id = request.headers.get("X-Tenant-Id")
    app_secret = (get_cached(tenant_id, "whatsapp.app_secret") if tenant_id else None) or settings.WHATSAPP_APP_SECRET
    if not verify_hub_signature(raw, app_secret, sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    # 2) Parse payload
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid JSON payload")

    # 3) Resolve channel from phone_number_id
    phone_number_id = _get_phone_number_id(payload)
    if not phone_number_id:
        # Not a message/status notification; ack quickly
        return {"ok": True, "details": "No phone_number_id present"}

    channel_repo = ChannelRepository(session)
    channel = await channel_repo.get_by_phone_number_id(phone_number_id)
    if not channel:
        # Unknown phone number id; ack but do not fail (avoids retries)
        return {"ok": True, "details": "Unknown phone_number_id"}

    inbound_repo = InboundRepository(session)

    # 4) Persist messages idempotently
    created = 0
    for m in _iter_messages(payload):
        msg = await inbound_repo.upsert_inbound_message(
            tenant_id=UUID(channel.tenant_id),
            channel_id=str(channel.id),
            whatsapp_message_id=m["id"],
            direction="INBOUND",
            from_phone=m["from"],
            to_phone=m["to"],
            message_type=m["type"],
            content_jsonb=m["raw"],
            status="DELIVERED",
        )
        if msg:
            created += 1

    # 5) Apply status updates
    updated = 0
    for s in _iter_statuses(payload):
        if await inbound_repo.apply_status_update(vendor_message_id=s["id"], vendor_status=s["status"]):
            updated += 1

    await session.commit()
    return {"ok": True, "details": "Processed", "data": {"created": created, "updated": updated}}


# ---------------------------------------------------------------------
# (Optional) Legacy endpoints — keep if your external config still points here
# ---------------------------------------------------------------------
legacy = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhook-legacy"])


@legacy.get("/{phone_number_id}")
async def legacy_verify(phone_number_id: str, request: Request):
    # Delegate to new verify (no tenant resolution on path)
    return await verify_webhook(request)


@legacy.post("/{phone_number_id}")
async def legacy_receive(phone_number_id: str, request: Request):
    # Delegate to new inbound (still validates signature)
    return await inbound_webhook(request)

@router.post("/whatsapp/inbound")
async def whatsapp_inbound(request: Request,
                           db: AsyncSession = Depends(get_session),
                           settings: Settings = Depends(get_settings),
                           principal=Depends(get_principal)):
    body = await request.json()
    # Assume upstream persistence already happened (Stage-3).
    # Extract essentials (normalize for MVP).
    tenant_id: UUID = getattr(principal, "tenant_id")
    channel_id: UUID = UUID(body["channel_id"])
    contact_id: str = body.get("from_phone") or body.get("contact_id")
    payload: dict = body.get("payload") or {}
    event_id: str | None = body.get("whatsapp_message_id") or body.get("event_id")

    # Trigger CE (no network I/O)
    result = await handle_trigger_flow(
        db, settings,
        TriggerFlow(tenant_id=tenant_id, channel_id=channel_id, contact_id=contact_id, inbound_payload=payload, event_id=event_id)
    )
    return {"status": "ok", "conversation_result": result}