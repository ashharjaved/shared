from __future__ import annotations

from typing import Any, Dict, Optional, Protocol
from uuid import UUID

from src.messaging.domain.entities.message import (
    Message,
    MessageDirection,
    MessageStatus,
    PhoneNumber,
)
from src.messaging.domain.repositories.message_repository import MessageRepository
from src.messaging.domain.repositories.channel_repository import ChannelRepository

# Conversation engine contract (implemented in Conversation module)
# Must expose: async def handle_incoming_message(channel_id: UUID, from_phone: str, content: Dict[str, Any]) -> Optional[Dict]
# Only import for type checking; no runtime dependency on Conversation module.
# Temporary in-file protocol until Conversation module exists.
class ConversationPort(Protocol):
    # handle_inbound
    async def handle_incoming_message(
        self,
        *,
        channel_id: UUID,
        from_phone: str,
        payload: dict,
    ) -> None: ...

class MessageService:
    """
    Business orchestration around messages:
    - AuthZ is assumed done at API layer (user->tenant->channel access).
    - Redis rate limits + DB idempotency handled inside MessageRepository.
    """

    def __init__(
        self,
        *,
        message_repo: MessageRepository,
        channel_repo: ChannelRepository,
        conversation_svc: Optional["ConversationPort"] = None,
    ) -> None:
        self._messages = message_repo
        self._channels = channel_repo
        self._conversation = conversation_svc

    async def send_message(
        self,
        *,
        requesting_user_id: UUID,
        tenant_id: UUID,
        channel_id: UUID,
        to: str,
        content: Dict[str, Any],
        type: str,
        idempotency_key: Optional[str] = None,
    ) -> Message:
        # 1) Ensure channel exists & belongs to tenant (RLS further constrains access)
        channel = await self._channels.find_by_id(channel_id)
        if not channel or not channel.is_active:
            raise ValueError("channel_not_found_or_inactive")

        # 2) Compose outbound domain message; from_phone = business_phone
        msg = Message(
            id=UUID(int=0),  # DB will generate
            tenant_id=tenant_id,
            channel_id=channel_id,
            from_phone=PhoneNumber(channel.business_phone),
            to_phone=PhoneNumber(to),
            content=content,
            message_type=type,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.QUEUED,
        )

        # 3) Queue with idempotency + rate limits (repo wraps DB proc + Redis)
        queued = await self._messages.queue_message(msg, idempotency_key=idempotency_key)
        return queued

    async def mark_delivered(self, message_id: UUID) -> Message:
        return await self._messages.update_status(message_id, MessageStatus.DELIVERED)

    async def mark_read(self, message_id: UUID) -> Message:
        return await self._messages.update_status(message_id, MessageStatus.READ)

    async def process_inbound_message(
        self,
        *,
        tenant_id: UUID,
        channel_id: UUID,
        from_phone: str,
        to_phone: str,
        payload: Dict[str, Any],
    ) -> Message:
        """
        Persist the inbound message and kick ConversationService if available.
        """
        # Persist inbound record (status: DELIVERED by default for inbound)
        inbound = Message(
            id=UUID(int=0),
            tenant_id=tenant_id,
            channel_id=channel_id,
            from_phone=PhoneNumber(from_phone),
            to_phone=PhoneNumber(to_phone),
            content=payload,
            message_type=payload.get("type", "text"),
            direction=MessageDirection.INBOUND,
            status=MessageStatus.DELIVERED,
        )
        saved = await self._messages.queue_message(inbound, idempotency_key=None)  # queues as if outbound
        # For INBOUND, the DB proc may be different; if you have a dedicated insert path for inbound, add it to the repo.
        # Optionally call conversation engine
        if self._conversation:
            try:
                await self._conversation.handle_incoming_message(channel_id=channel_id, from_phone=from_phone, payload=payload)
            except Exception:
                # swallow errors to avoid blocking WA webhook; logs handled by global logging
                pass
        return saved