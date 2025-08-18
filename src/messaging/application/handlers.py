from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from src.messaging.infrastructure.repositories import ChannelRepository, InboundRepository
from src.messaging.domain.services import MessageDeliveryService

@dataclass
class MessagingHandlers:
    session: AsyncSession

    async def handle_link_channel(self, cmd) -> Dict[str, Any]:
        repo = ChannelRepository(self.session)
        ch = await repo.set_or_update(cmd.tenant_id, cmd.data)
        return {
            "phone_number_id": ch.phone_number_id,
            "business_phone": getattr(ch, "business_phone", None),
            "waba_id": getattr(ch, "waba_id", None),
            "display_name": getattr(ch, "display_name", None),
            "is_active": getattr(ch, "is_active", True),
        }

    async def handle_persist_inbound(self, cmd) -> Dict[str, Any]:
        irepo = InboundRepository(self.session)
        created = 0
        for m in cmd.messages:
            res = await irepo.upsert_inbound_message(
                tenant_id=cmd.tenant_id,
                channel_id=cmd.channel_id,
                whatsapp_message_id=m.get("id"),
                direction="INBOUND",
                from_phone=m.get("from") or "",
                to_phone=m.get("to") or "",
                message_type=m.get("type") or "text",
                content_jsonb=m,
                status="DELIVERED",
            )
            if res:
                created += 1

        updated = 0
        for s in cmd.statuses:
            ok = await irepo.apply_status_update(vendor_message_id=s["id"], vendor_status=s["status"])
            updated += int(bool(ok))

        return {"created_messages": created, "updated_status": updated}

    async def handle_prepare_outbound(self, cmd, api_base: str, phone_number_id: str) -> Dict[str, Any]:
        svc = MessageDeliveryService()
        return svc.prepare_payload(
            api_base=api_base,
            phone_number_id=phone_number_id,
            to=cmd.to,
            text=cmd.text,
            template=cmd.template,
            media=cmd.media,
        )
