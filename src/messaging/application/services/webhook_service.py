from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from src.messaging.application.services.message_service import MessageService
from src.messaging.domain.repositories.channel_repository import ChannelRepository
from src.messaging.infrastructure.whatsapp_api import WhatsAppApiClient


class WebhookService:
    """
    Validates and processes WhatsApp webhook (verification + inbound events).
    """

    def __init__(
        self,
        *,
        channel_repo: ChannelRepository,
        message_svc: MessageService,
        app_secret: str,
    ) -> None:
        self._channels = channel_repo
        self._messages = message_svc
        self._app_secret = app_secret

    @staticmethod
    def verify_signature(*, raw_body: bytes, signature_header: str, app_secret: str) -> bool:
        return WhatsAppApiClient.verify_webhook_signature(payload=raw_body, signature_header=signature_header, app_secret=app_secret)

    async def process_verification(self, *, mode: str, token: str, challenge: str, expected_token: str) -> Optional[str]:
        """
        GET handshake: echo 'challenge' if mode=subscribe and token matches.
        """
        if mode == "subscribe" and token == expected_token:
            return challenge
        return None

    async def process_inbound_payload(self, payload: Dict[str, Any]) -> None:
        """
        POST webhook: handle messages + statuses.
        Expected Meta structure:
        { "entry":[{"changes":[{"value":{"metadata":{"phone_number_id": "..."},"messages":[...],"statuses":[...]}}]}]}
        """
        entries = payload.get("entry") or []
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
                if not phone_number_id:
                    continue

                # Resolve channel (tenant via RLS)
                channel = await self._find_channel_by_phone_number_id(phone_number_id)
                if not channel:
                    continue

                # Inbound messages
                for m in value.get("messages", []):
                    from_phone = m.get("from")
                    to_phone = m.get("to") or channel.business_phone
                    await self._messages.process_inbound_message(
                        tenant_id=channel.tenant_id,
                        channel_id=channel.id,
                        from_phone=from_phone,
                        to_phone=to_phone,
                        payload=m,
                    )

                # Delivery/read statuses
                for s in value.get("statuses", []):
                    internal_id = await self._resolve_internal_message_id_from_wa_id(s.get("id"))
                    if not internal_id:
                        continue
                    status = (s.get("status") or "").lower()
                    if status == "delivered":
                        await self._messages.mark_delivered(internal_id)
                    elif status == "read":
                        await self._messages.mark_read(internal_id)

    async def _find_channel_by_phone_number_id(self, phone_number_id: str):
        # If your repo doesn’t have a "find_by_phone_number_id", list() and filter in memory is acceptable for MVP.
        channels = await self._channels.list()
        return next((c for c in channels if c.phone_number_id == phone_number_id), None)

    async def _resolve_internal_message_id_from_wa_id(self, wa_id: Optional[str]) -> Optional[UUID]:
        # Hint: add MessageRepository.find_by_whatsapp_id if you want a direct lookup.
        # For now return None (status updates no-op). Implement later when WA ID stored.
        return None
