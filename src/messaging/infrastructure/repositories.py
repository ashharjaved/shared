# from __future__ import annotations
# from dataclasses import dataclass
# from typing import Any, Dict, Optional
# from uuid import UUID
# from sqlalchemy import select, update, insert
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.exc import IntegrityError

# from src.messaging.infrastructure.models import WhatsappChannel, Message
# from src.shared.database import async_session_factory

# @dataclass
# class ChannelRepository:
#     session: AsyncSession

#     async def get_by_tenant(self, tenant_id: UUID) -> Optional[WhatsappChannel]:
#         res = await self.session.execute(
#             select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id)
#         )
#         return res.scalars().first()

#     async def get_by_phone_number_id(self, phone_number_id: str) -> Optional[WhatsappChannel]:
#         res = await self.session.execute(
#             select(WhatsappChannel).where(WhatsappChannel.phone_number_id == phone_number_id)
#         )
#         return res.scalars().first()

#     async def set_or_update(self, tenant_id: UUID, data: Dict[str, Any]) -> WhatsappChannel:
#         existing = await self.get_by_tenant(tenant_id)
#         if existing:
#             for k, v in data.items():
#                 if hasattr(existing, k):
#                     setattr(existing, k, v)
#             await self.session.flush()
#             return existing
#         obj = WhatsappChannel(tenant_id=tenant_id, **{k: v for k, v in data.items() if hasattr(WhatsappChannel, k)})
#         self.session.add(obj)
#         await self.session.flush()
#         return obj

# @dataclass
# class InboundRepository:
#     session: AsyncSession

#     async def upsert_inbound_message(
#         self,
#         tenant_id: str,
#         channel_id: str,
#         whatsapp_message_id: Optional[str],
#         direction: str,
#         from_phone: str,
#         to_phone: str,
#         message_type: str,
#         content_jsonb: Dict[str, Any],
#         status: str = "DELIVERED",
#     ) -> Optional[Message]:
#         if whatsapp_message_id:
#             res = await self.session.execute(
#                 select(Message).where(Message.whatsapp_message_id == whatsapp_message_id)
#             )
#             existing = res.scalars().first()
#             if existing:
#                 return None

#         msg = Message(
#             tenant_id=tenant_id,
#             channel_id=channel_id,
#             whatsapp_message_id=whatsapp_message_id,
#             direction=direction,
#             from_phone=from_phone,
#             to_phone=to_phone,
#             content_jsonb=content_jsonb,
#             content_hash="",
#             message_type=message_type,
#             status=status,
#         )
#         self.session.add(msg)
#         await self.session.flush()
#         return msg

#     async def apply_status_update(self, vendor_message_id: str, vendor_status: str) -> bool:
#         status_map = {"sent": "SENT", "delivered": "DELIVERED", "read": "DELIVERED", "failed": "FAILED"}
#         new_status = status_map.get(vendor_status, "DELIVERED")
#         res = await self.session.execute(
#             update(Message).where(Message.whatsapp_message_id == vendor_message_id).values(status=new_status)
#         )
#         return res.rowcount > 0

#     @staticmethod
#     async def persist_inbound(phone_number_id: str, payload: dict) -> None:
#         """
#         Extract whatsapp_message_id and other fields; insert once.
#         """
#         wa_id = payload.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [{}])[0].get("id")
#         if not wa_id:
#             return  # no-op for non-message events
#         stmt = insert(Message).values(
#             tenant_id=None,           # set by trigger/DI
#             channel_id=None,          # resolved upstream by phone_number_id
#             whatsapp_message_id=wa_id,
#             direction="INBOUND",
#             from_phone=payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"],
#             to_phone=payload["entry"][0]["changes"][0]["value"]["metadata"]["display_phone_number"],
#             content_jsonb=payload,
#             content_hash="",
#             message_type=payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"],
#             status="DELIVERED",
#         )
#         async with async_session_factory() as session:
#             try:
#                 await session.execute(stmt)
#                 await session.commit()
#             except IntegrityError:
#                 await session.rollback()  # duplicate delivery; ignore
#----------------------------------------------------------------------------------------
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.messaging.infrastructure.models import Message, WhatsappChannel
from src.shared.database import async_session_factory


# ---------------------------------------------------------------------
# Channel repository (tenant-scoped WhatsApp channel/config)
# ---------------------------------------------------------------------
@dataclass
class ChannelRepository:
    session: AsyncSession

    async def get_by_tenant(self, tenant_id) -> Optional[WhatsappChannel]:
        q = select(WhatsappChannel).where(WhatsappChannel.tenant_id == tenant_id)
        res = await self.session.execute(q)
        return res.scalars().first()

    async def get_by_phone_number_id(self, phone_number_id: str) -> Optional[WhatsappChannel]:
        q = select(WhatsappChannel).where(WhatsappChannel.phone_number_id == phone_number_id)
        res = await self.session.execute(q)
        return res.scalars().first()

    async def set_or_update(self, tenant_id, data: Dict[str, Any]) -> WhatsappChannel:
        existing = await self.get_by_tenant(tenant_id)
        if existing:
            # Update only known attributes
            for k, v in data.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)
            await self.session.flush()
            return existing

        # Create new channel
        payload = {k: v for k, v in data.items() if hasattr(WhatsappChannel, k)}
        obj = WhatsappChannel(tenant_id=tenant_id, **payload)
        self.session.add(obj)
        await self.session.flush()
        return obj


# ---------------------------------------------------------------------
# Inbound repository (idempotent inbound persistence + status updates)
# ---------------------------------------------------------------------
@dataclass
class InboundRepository:
    session: AsyncSession

    async def upsert_inbound_message(
        self,
        tenant_id,
        channel_id,
        whatsapp_message_id: Optional[str],
        direction: str,
        from_phone: str,
        to_phone: str,
        message_type: str,
        content_jsonb: Dict[str, Any],
        status: str = "DELIVERED",
    ) -> Optional[Message]:
        """
        Insert inbound message exactly once (idempotent on whatsapp_message_id).
        Returns the created Message or None if it already existed.
        """
        if whatsapp_message_id:
            res = await self.session.execute(
                select(Message).where(Message.whatsapp_message_id == whatsapp_message_id)
            )
            if res.scalars().first():
                return None

        msg = Message(
            tenant_id=tenant_id,
            channel_id=channel_id,
            whatsapp_message_id=whatsapp_message_id,
            direction=direction,
            from_phone=from_phone,
            to_phone=to_phone,
            content_jsonb=content_jsonb,
            content_hash="",  # optional hash for dedupe if you add it
            message_type=message_type,
            status=status,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def apply_status_update(self, vendor_message_id: str, vendor_status: str) -> bool:
        """
        Map vendor status -> internal enum and update in place.
        Returns True if a row was updated, False otherwise.
        """
        status_map = {
            "sent": "SENT",
            "delivered": "DELIVERED",
            "read": "DELIVERED",
            "failed": "FAILED",
        }
        new_status = status_map.get(vendor_status, "DELIVERED")
        res = await self.session.execute(
            update(Message)
            .where(Message.whatsapp_message_id == vendor_message_id)
            .values(status=new_status)
        )
        return res.rowcount > 0

    # --- Utility for legacy/raw webhook path that doesn't have a session injected ---
    @staticmethod
    async def persist_inbound(phone_number_id: str, payload: dict) -> None:
        """
        Best-effort idempotent insert without DI (used by legacy webhook).
        No-op if no message id is found or on duplicate key.
        """
        try:
            entry = payload.get("entry", [{}])[0]
            change = entry.get("changes", [{}])[0]
            value = change.get("value", {})
            msg = (value.get("messages") or [{}])[0]
            wa_id = msg.get("id")
            if not wa_id:
                return  # not a message event

            stmt = insert(Message).values(
                tenant_id=None,  # set by DB default / trigger if present
                channel_id=None,  # resolved elsewhere by phone_number_id
                whatsapp_message_id=wa_id,
                direction="INBOUND",
                from_phone=msg.get("from", ""),
                to_phone=value.get("metadata", {}).get("display_phone_number", ""),
                content_jsonb=payload,
                content_hash="",
                message_type=msg.get("type", "text"),
                status="DELIVERED",
            )

            async with async_session_factory() as session:
                try:
                    await session.execute(stmt)
                    await session.commit()
                except IntegrityError:
                    await session.rollback()  # duplicate delivery; ignore safely
        except Exception:
            # Intentionally swallow errors in this static helper to avoid
            # failing webhook ack; main path should use DI + proper error handling.
            return
