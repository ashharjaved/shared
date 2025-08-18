from __future__ import annotations
from typing import Any, Dict, Optional
from dataclasses import dataclass
from src.messaging.infrastructure.whatsapp_client import build_outbound_payload

@dataclass(slots=True)
class LinkChannel:
    tenant_id: str
    phone_number_id: str   # as returned from Meta WA
    business_phone: str    # E.164; validated at API layer
    access_token_ciphertext: str
    webhook_verify_token_ciphertext: str
    webhook_url: str
    rate_limit_per_second: int = 10
    monthly_message_limit: int = 10000

@dataclass
class PersistInboundEvent:
    # raw normalized fields computed by webhook handler
    tenant_id: str
    channel_id: str
    messages: list[dict]
    statuses: list[dict]

@dataclass
class PrepareOutboundMessage:
    tenant_id: str
    to: str
    text: Optional[str]
    template: Optional[Dict[str, Any]]
    media: Optional[Dict[str, Any]]

class MessageDeliveryService:
    def prepare_payload(
        self,
        api_base: str,
        phone_number_id: str,
        to: str,
        text: Optional[str] = None,
        template: Optional[Dict[str, Any]] = None,
        media: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return build_outbound_payload(
            api_base=api_base,
            phone_number_id=phone_number_id,
            to=to,
            text=text,
            template=template,
            media=media,
        )

__all__ = ["LinkChannel", "PrepareOutboundMessage"]