from __future__ import annotations
from typing import Any, Dict, Optional

def build_outbound_payload(
    *, api_base: str, phone_number_id: str, to: str,
    text: Optional[str], template: Optional[Dict[str, Any]], media: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    endpoint = f"{api_base}/{phone_number_id}/messages"
    payload: Dict[str, Any] = {"messaging_product": "whatsapp", "to": to}
    if text:
        payload["type"] = "text"
        payload["text"] = {"body": text}
    elif template:
        payload["type"] = "template"
        payload["template"] = {
            "name": template["name"],
            "language": {"code": template["language"]},
        }
        if template.get("vars"):
            payload["template"]["components"] = [{
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in template["vars"]]
            }]
    elif media:
        payload["type"] = media["type"]
        payload[media["type"]] = {"link": media["url"]}
    return {"endpoint": endpoint, "payload": payload}
