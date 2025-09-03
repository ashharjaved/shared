from __future__ import annotations

from fastapi import APIRouter, Depends, status, HTTPException
from uuid import UUID

from src.shared.cache import get_redis
from src.shared.dependencies import get_channel_limits_cb
from src.messaging.api.schemas import MessageSendRequest, MessageResponse
from src.messaging.application.services.message_service import MessageService
from src.messaging.domain.repositories.message_repository import MessageRepository
from src.messaging.domain.repositories.channel_repository import ChannelRepository

from src.dependencies import get_current_user

from src.shared.database import get_session, make_message_repo, make_channel_repo  # helpers to construct repos


router = APIRouter(tags=["Messaging: Messages"])


@router.post("/api/messaging/messages", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_outbound_message(
    body: MessageSendRequest,
    user=Depends(get_current_user),
) -> MessageResponse:
    msg_repo: MessageRepository = make_message_repo(
        tenant_id=user.tenant_id,
        session_factory=get_session(),
        redis=await get_redis(),
        get_channel_limits=get_channel_limits_cb(tenant_id=user.tenant_id,),
    )
    ch_repo: ChannelRepository = make_channel_repo(
        tenant_id=user.tenant_id,
        encrypt=lambda s: s,  # not needed here
        decrypt=lambda s: s,
        session_factory=get_session(),
    )
    svc = MessageService(message_repo=msg_repo, channel_repo=ch_repo)

    try:
        m = await svc.send_message(
            requesting_user_id=user.id,
            tenant_id=user.tenant_id,
            channel_id=body.channel_id,
            to=body.to,
            content=body.content,
            type=body.type,
            idempotency_key=body.idempotency_key,
        )
        # === Normalize result & ALWAYS return a body ===
        # If service indicates idempotent duplicate, never return None.
        if m is None:
            raise HTTPException(
                status_code=200,
                detail={"code": "idempotent_duplicate", "message": "Message already queued/sent for this idempotency_key"}
            )

        # If service returned the new message's UUID, load it for the response.
        if isinstance(m, UUID):
            found = await msg_repo.find_by_id(m)
            if not found:
                raise HTTPException(status_code=500, detail="message_persisted_but_not_readable")
            return MessageResponse(
                id=found.id,
                channel_id=found.channel_id,
                from_phone=str(found.from_phone),
                to_phone=str(found.to_phone),
                status=found.status.value if hasattr(found.status, "value") else str(found.status),
                created_at=found.created_at,
            )

        # If service already returned a schema/dict/domain entity – coerce it.
        try:
            if isinstance(m, MessageResponse):
                return m
            if isinstance(m, dict):
                return MessageResponse.model_validate(m)
            # Domain entity case
            return MessageResponse(
                id=getattr(m, "id"),
                channel_id=getattr(m, "channel_id"),
                from_phone=str(getattr(m, "from_phone")),
                to_phone=str(getattr(m, "to_phone")),
                status=getattr(m, "status").value if hasattr(getattr(m, "status", None), "value") else str(getattr(m, "status", "queued")),
                created_at=getattr(m, "created_at"),
            )
        except Exception as cast_err:
            raise HTTPException(
                status_code=500,
                detail={"code": "response_cast_error", "message": "Unable to cast message to response schema", "details": str(cast_err)},
            )
    except Exception as e:
        msg = str(e)
        # Friendly hint for missing monthly partitions (PG CheckViolationError)
        if "no partition of relation \"messages\" found for row" in msg:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_request_value",
                    "message": "Messages table has no partition for the current month.",
                    "details": "Create the current month partition for `messages` or add a DEFAULT partition."
                },
            )
        # Fallback (still structured)
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_request", "message": "Unable to queue message", "details": msg},
        )


@router.get("/api/messaging/messages/{message_id}", response_model=MessageResponse)
async def get_message_status(message_id: UUID, user=Depends(get_current_user)) -> MessageResponse:
    msg_repo: MessageRepository = make_message_repo(
        tenant_id=user.tenant_id,
        session_factory=get_session(),
        redis=await get_redis(),
        get_channel_limits=get_channel_limits_cb(tenant_id=user.tenant_id,),
    )
    found = await msg_repo.find_by_id(message_id)
    if not found:
        raise HTTPException(status_code=404, detail="message_not_found")
    return MessageResponse(
        id=found.id,
        channel_id=found.channel_id,
        from_phone=str(found.from_phone),
        to_phone=str(found.to_phone),
        status=found.status.value,
        created_at=found.created_at,
    )
