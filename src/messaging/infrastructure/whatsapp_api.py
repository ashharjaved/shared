from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, Optional

import httpx


class WhatsAppApiClient:
    """
    Minimal client wrapper for WhatsApp Cloud API (Meta Graph).
    - Use in Outbox Worker when sending queued messages.
    - Keep tokens out of logs; pass decrypted token per-channel.
    """

    def __init__(self, *, base_url: str = "https://graph.facebook.com/v20.0", timeout: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def send_message(
        self,
        *,
        phone_number_id: str,
        access_token: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        POST /{phone_number_id}/messages
        payload example (text):
        {
          "messaging_product": "whatsapp",
          "to": "+15551234567",
          "type": "text",
          "text": {"body": "hello"}
        }
        """
        url = f"{self._base}/{phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()

    @staticmethod
    def verify_webhook_signature(*, payload: bytes, signature_header: str, app_secret: str) -> bool:
        """
        X-Hub-Signature-256: sha256=<hexdigest>
        """
        try:
            method, hexdigest = signature_header.split("=", 1)
            if method.lower() != "sha256":
                return False
            mac = hmac.new(app_secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
            return hmac.compare_digest(mac.hexdigest(), hexdigest)
        except Exception:
            return False
