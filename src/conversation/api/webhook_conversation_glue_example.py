#*** Begin: src/messaging/api/webhook_conversation_glue_example.py ***
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# Reuse your global session factory (Stage-1/2 bootstraps)
from src.shared.database import get_session  # type: ignore

from src.conversation.application.adapter import make_conversation_reply

router = APIRouter(prefix="/api/webhooks/whatsapp", tags=["whatsapp-webhook"])

@router.post("/conversation")
async def whatsapp_conversation_adapter(request: Request) -> JSONResponse:
    """
    Minimal glue endpoint (example). Your real webhook likely already exists;
    call make_conversation_reply(...) inside that handler.
    """
    payload = await request.json()
    # Extract fields according to your Messaging inbound contract
    channel_id = UUID(payload["channel_id"])
    from_phone = str(payload["from"])
    text_in = str(payload.get("text") or "")

    # Get the app's session factory
    sf: async_sessionmaker[AsyncSession] = get_session()

    reply_text = await make_conversation_reply(
        session_factory=sf,
        channel_id=channel_id,
        from_phone=from_phone,
        text_in=text_in,
        # Optional: industry_hint="HEALTHCARE",
        request_id=str(payload.get("request_id") or "webhook"),
    )

    # Return just the text to your Messaging Outbound path,
    # or enqueue it in your existing outbox flow.
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"reply_text": reply_text},
    )
#*** End: src/messaging/api/webhook_conversation_glue_example.py ***
