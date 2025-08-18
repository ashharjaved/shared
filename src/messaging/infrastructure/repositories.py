from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.messaging.infrastructure.models import Message
from src.shared.database import async_session
from sqlalchemy import insert
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
    
    @staticmethod
    async def persist_inbound(phone_number_id: str, payload: dict) -> None:
        """
        Extract whatsapp_message_id and other fields; insert once.
        """
        wa_id = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0].get("id")
        if not wa_id:
            return  # no-op for non-message events
        stmt = insert(Message).values(
            tenant_id=None,           # set by trigger/DI
            channel_id=None,          # resolved upstream by phone_number_id
            whatsapp_message_id=wa_id,
            direction="INBOUND",
            from_phone=payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"],
            to_phone=payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"],
            content_jsonb=payload,
            content_hash="",
            message_type=payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"],
            status="DELIVERED",
        )
        async with async_session() as session:
            try:
                await session.execute(stmt)
                await session.commit()
            except IntegrityError:
                await session.rollback()  # duplicate delivery; ignore

