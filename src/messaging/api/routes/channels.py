from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.shared.security import get_decryptor, get_encryptor
from src.messaging.api.schemas import ChannelCreate, ChannelResponse
from src.messaging.application.services.channel_service import ChannelService
from src.messaging.domain.repositories.channel_repository import ChannelRepository

from src.dependencies import get_current_user  # project-specific
from src.shared.database import get_session, make_channel_repo  # helper you create to construct repo with tenant + crypto


router = APIRouter(tags=["Messaging: Channels"])


@router.post("/api/messaging/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def register_channel(
    body: ChannelCreate,
    user=Depends(get_current_user),
) -> ChannelResponse:
    # Build repo with tenant-scoped RLS
    repo: ChannelRepository = make_channel_repo(
        tenant_id=user.tenant_id,
        encrypt=get_encryptor(),
        decrypt=get_decryptor(),
        session_factory=get_session(),
    )
    svc = ChannelService(channel_repo=repo)
    ch = await svc.register_channel(
        name=body.name,
        phone_number_id=body.phone_number_id,
        business_phone=body.business_phone,
        access_token_plain=body.access_token,
        is_active=body.is_active,
        rate_limit_per_second=body.rate_limit_per_second,
        monthly_message_limit=body.monthly_message_limit,
        tenant_id=user.tenant_id,
    )
    return ChannelResponse(
        id=ch.id,
        name=ch.name,
        phone_number_id=ch.phone_number_id,
        business_phone=ch.business_phone,
        is_active=ch.is_active,
        rate_limit_per_second=ch.rate_limit_per_second,
        monthly_message_limit=ch.monthly_message_limit,
    )


@router.get("/api/messaging/channels", response_model=list[ChannelResponse])
async def list_channels(user=Depends(get_current_user)) -> list[ChannelResponse]:
    repo: ChannelRepository = make_channel_repo(
        tenant_id=user.tenant_id,
        encrypt=get_encryptor(),
        decrypt=get_decryptor(),
        session_factory=get_session(),
    )
    svc = ChannelService(channel_repo=repo)
    channels = await svc.list_channels()
    return [
        ChannelResponse(
            id=c.id,
            name=c.name,
            phone_number_id=c.phone_number_id,
            business_phone=c.business_phone,
            is_active=c.is_active,
            rate_limit_per_second=c.rate_limit_per_second,
            monthly_message_limit=c.monthly_message_limit,
        )
        for c in channels
    ]
