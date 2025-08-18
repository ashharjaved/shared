from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.infrastructure.models import WhatsappChannel, Message

@dataclass
class ChannelRepository:
    session: AsyncSession

    async def get_by_tenant(self, tenant_id: str) -> Optional[WhatsappChannel]:
        res = await self.session.execute(
            select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id)
        )
        return res.scalars().first()

    async def get_by_phone_number_id(self, phone_number_id: str) -> Optional[WhatsappChannel]:
        res = await self.session.execute(
            select(WhatsappChannel).where(WhatsappChannel.phone_number_id == phone_number_id)
        )
        return res.scalars().first()

    async def set_or_update(self, tenant_id: str, data: Dict[str, Any]) -> WhatsappChannel:
        existing = await self.get_by_tenant(tenant_id)
        if existing:
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            await self.session.flush()
            return existing
        obj = WhatsappChannel(tenant_id=tenant_id, **{k: v for k, v in data.items() if hasattr(WhatsappChannel, k)})
        self.session.add(obj)
        await self.session.flush()
        return obj

@dataclass
class InboundRepository:
    session: AsyncSession

    async def upsert_inbound_message(
        self,
        tenant_id: str,
        channel_id: str,
        whatsapp_message_id: Optional[str],
        direction: str,
        from_phone: str,
        to_phone: str,
        message_type: str,
        content_jsonb: Dict[str, Any],
        status: str = "DELIVERED",
    ) -> Optional[Message]:
        if whatsapp_message_id:
            res = await self.session.execute(
                select(Message).where(Message.whatsapp_message_id == whatsapp_message_id)
            )
            existing = res.scalars().first()
            if existing:
                return None

        msg = Message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            whatsapp_message_id=whatsapp_message_id,
            direction=direction,
            from_phone=from_phone,
            to_phone=to_phone,
            content_jsonb=content_jsonb,
            content_hash="",
            message_type=message_type,
            status=status,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def apply_status_update(self, vendor_message_id: str, vendor_status: str) -> bool:
        status_map = {"sent": "SENT", "delivered": "DELIVERED", "read": "DELIVERED", "failed": "FAILED"}
        new_status = status_map.get(vendor_status, "DELIVERED")
        res = await self.session.execute(
            update(Message).where(Message.whatsapp_message_id == vendor_message_id).values(status=new_status)
        )
        return res.rowcount > 0
