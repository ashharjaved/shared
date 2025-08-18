from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field, constr, field_validator, StringConstraints

# E.164 constrained string (Pydantic v2)
E164Str = Annotated[str, StringConstraints(pattern=r"^\+[1-9]\d{1,14}$")]
class WhatsAppVerifyQuery(BaseModel):
    hub_mode: str = Field(alias="hub.mode")
    hub_verify_token: str = Field(alias="hub.verify_token")
    hub_challenge: str = Field(alias="hub.challenge")

    @field_validator("hub_mode")
    def ensure_subscribe(cls, v: str) -> str:
        if v.lower() != "subscribe":
            raise ValueError("hub.mode must be 'subscribe'")
        return v

class OnboardingRequest(BaseModel):
    phone_number_id: str
    business_phone: Optional[E164Str] = None
    access_token: Optional[str] = None
    verify_token: Optional[str] = None
    webhook_url: Optional[str] = None
    waba_id: Optional[str] = None
    display_name: Optional[str] = None

class ChannelResponse(BaseModel):
    phone_number_id: str
    business_phone: Optional[str] = None
    waba_id: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = True

class WaMessageItem(BaseModel):
    id: Optional[str] = None
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None
    timestamp: Optional[str] = None
    type: Optional[str] = None
    text: Optional[Dict[str, Any]] = None
    image: Optional[Dict[str, Any]] = None
    document: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None

class WaStatusItem(BaseModel):
    id: str
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: Optional[str] = None
    recipient_id: Optional[str] = None

class WhatsAppInboundEntry(BaseModel):
    id: Optional[str] = None
    changes: List[Dict[str, Any]]

class WhatsAppInboundPayload(BaseModel):
    object: str
    entry: List[WhatsAppInboundEntry]

    def phone_number_ids(self) -> List[str]:
        ids: List[str] = []
        for e in self.entry:
            for ch in e.changes:
                val = ch.get("value") or {}
                meta = val.get("metadata") or {}
                pn = meta.get("phone_number_id")
                if pn:
                    ids.append(pn)
        return ids

    def iter_messages(self) -> List[WaMessageItem]:
        items: List[WaMessageItem] = []
        for e in self.entry:
            for ch in e.changes:
                val = ch.get("value") or {}
                for m in val.get("messages") or []:
                    items.append(WaMessageItem.parse_obj(m))
        return items

    def iter_statuses(self) -> List[WaStatusItem]:
        items: List[WaStatusItem] = []
        for e in self.entry:
            for ch in e.changes:
                val = ch.get("value") or {}
                for s in val.get("statuses") or []:
                    items.append(WaStatusItem.parse_obj(s))
        return items

class TemplateSpec(BaseModel):
    name: str
    language: str
    vars: Optional[List[str]] = None

class MediaSpec(BaseModel):
    type: Literal["image", "video", "document", "audio"]
    url: str

class OutboundRequest(BaseModel):
    to: E164Str
    text: Optional[str] = None
    template: Optional[TemplateSpec] = None
    media: Optional[MediaSpec] = None

    @field_validator("text")
    def at_least_one_kind(cls, v, values):
        if not v and not values.get("template") and not values.get("media"):
            raise ValueError("Provide text or template or media")
        return v

class OkResponse(BaseModel):
    ok: bool = True
    details: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
