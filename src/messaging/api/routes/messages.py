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
    except Exception as e:
        # Let your global error handler map domain exceptions; this is a guard fallback.
        raise HTTPException(status_code=400, detail=str(e))

    return MessageResponse(
        id=m.id, channel_id=m.channel_id, from_phone=str(m.from_phone), to_phone=str(m.to_phone), status=m.status.value, created_at=m.created_at
    )


@router.get("/api/messaging/messages/{message_id}", response_model=MessageResponse)
async def get_message_status(message_id: UUID, user=Depends(get_current_user)) -> MessageResponse:
    msg_repo: MessageRepository = make_message_repo(
        tenant_id=user.tenant_id,
        session_factory=get_session(),
        redis=await get_redis(),
        get_channel_limits=get_channel_limits_cb(tenant_id=UUID(user.tenant_id),),
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
