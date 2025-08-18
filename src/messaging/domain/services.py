from __future__ import annotations
from typing import Any, Dict, Optional

from src.messaging.infrastructure.whatsapp_client import build_outbound_payload

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
