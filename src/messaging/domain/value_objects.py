# src/messaging/domain/value_objects.py
from enum import Enum
from dataclasses import dataclass

class WhatsAppMessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    RECEIVED = "received"

class WhatsAppMessageDirection(str, Enum):
    INBOUND = "in"
    OUTBOUND = "out"

class WhatsAppChannelStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"

class OutboxEventType(str, Enum):
    MESSAGE_QUEUED = "MessageQueued"
    MESSAGE_STATUS_CHANGED = "MessageStatusChanged"

@dataclass(frozen=True)
class PhoneNumber:
    value: str

    def __post_init__(self):
        v = self.value.replace(" ", "")
        if not v.startswith("+"): 
            raise ValueError("Phone number must start with '+'")
        digits = v[1:]
        if not digits.isdigit() or not (1 <= len(digits) <= 15):
            raise ValueError("Phone number must be E.164 compliant (+[1-15 digits])")
        object.__setattr__(self, "value", v)

    def masked(self) -> str:
        # Keep + and last 2 digits
        v = self.value
        return v[:2] + "****" + v[-2:]


@dataclass(frozen=True)
class WhatsAppMessageId:
    value: str
    
    def __post_init__(self):
        if not self.value:
            raise ValueError("WhatsApp message ID cannot be empty")

@dataclass(frozen=True)
class SecretRef:
    """Opaque reference to a secret (e.g., key in KMS/Secrets Manager)."""
    key: str    # e.g., 'wa/access_token/<channel_id>'
        
