from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from shared.cache import get_redis
from shared.dependencies import get_channel_limits_cb
from src.messaging.application.services.webhook_service import WebhookService
from src.messaging.application.services.message_service import MessageService
from src.messaging.domain.repositories.channel_repository import ChannelRepository
from src.shared.database import get_session, make_channel_repo, make_message_repo
from src.config import get_settings

router = APIRouter(tags=["Messaging: Webhook"])

settings=get_settings()

async def get_webhook_service() -> WebhookService:
    # Webhook is unauthenticated; we need only repos + app secret
    channel_repo: ChannelRepository = make_channel_repo(
        tenant_id=None,  # IMPORTANT: webhook handlers will set tenant per-channel lookup; repo still uses RLS on listing by current context
        encrypt=lambda s: s,
        decrypt=lambda s: s,
        session_factory=get_session(),
    )
    redis = await get_redis()
    msg_svc = MessageService(
        message_repo=make_message_repo(
            tenant_id=None,  # tenant will be set by repo via GUC before each op using resolved channel. If your helpers require tenant, adapt to per-call set.
            session_factory=get_session(),
            redis=redis,
            get_channel_limits=get_channel_limits_cb(session_factory=get_session()),
        ),
        channel_repo=channel_repo,
        conversation_svc=None,  # wire actual ConversationService if already implemented
    )
    return WebhookService(
        channel_repo=channel_repo,
        message_svc=msg_svc,
        app_secret=settings.WHATSAPP_APP_SECRET,
    )


@router.get("/api/messaging/webhook")
async def whatsapp_verify(mode: str, hub_verify_token: str | None = None, hub_challenge: str | None = None):
    svc = await get_webhook_service()
    expected = settings.WHATSAPP_VERIFY_TOKEN
    challenge = await svc.process_verification(mode=mode, token=hub_verify_token or "", challenge=hub_challenge or "", expected_token=expected)
    if challenge is None:
        raise HTTPException(status_code=403, detail="verification_failed")
    return int(challenge) if challenge.isdigit() else challenge


@router.post("/api/messaging/webhook")
async def whatsapp_inbound(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
):
    svc = await get_webhook_service()
    raw = await request.body()

    if not x_hub_signature_256:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_signature")

    ok = svc.verify_signature(raw_body=raw, signature_header=x_hub_signature_256, app_secret=settings.WHATSAPP_APP_SECRET)
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")

    # Process asynchronously if your framework startup sets a background task runner.
    await svc.process_inbound_payload(payload)
    return {"ok": True}