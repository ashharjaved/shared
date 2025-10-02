"""Value objects for WhatsApp domain."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
import re


class ChannelStatus(Enum):
    """Channel status enumeration."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class RateLimitTier(Enum):
    """Rate limit tier enumeration."""
    STANDARD = "standard"
    HIGH_VOLUME = "high_volume"
    
    @classmethod
    def from_string(cls, value: str) -> "RateLimitTier":
        """Create from string value."""
        return cls(value.lower())
    
    def get_limit(self) -> int:
        """Get messages per second limit."""
        if self == RateLimitTier.STANDARD:
            return 80
        elif self == RateLimitTier.HIGH_VOLUME:
            return 250
        return 80


@dataclass(frozen=True)
class WhatsAppBusinessAccountId:
    """WhatsApp Business Account ID value object."""
    
    value: str
    
    def __post_init__(self):
        """Validate WABA ID."""
        if not self.value:
            raise ValueError("Business account ID cannot be empty")
        
        # WABA IDs are typically numeric strings
        if not self.value.isdigit():
            raise ValueError(f"Invalid business account ID: {self.value}")


@dataclass(frozen=True)
class AccessToken:
    """Access token value object (will be encrypted)."""
    
    value: str
    
    def __post_init__(self):
        """Validate access token."""
        if not self.value:
            raise ValueError("Access token cannot be empty")
        
        # Basic length check
        if len(self.value) < 20:
            raise ValueError("Access token appears to be invalid")


@dataclass(frozen=True)
class MessageContent:
    """Message content value object."""
    
    data: Dict[str, Any]
    
    def __post_init__(self):
        """Validate message content structure."""
        if not isinstance(self.data, dict):
            raise ValueError("Message content must be a dictionary")
    
    def get_text(self) -> Optional[str]:
        """Extract text content if present."""
        return self.data.get("body") or self.data.get("text", {}).get("body")
    
    def get_media_url(self) -> Optional[str]:
        """Extract media URL if present."""
        for media_type in ["image", "video", "audio", "document"]:
            if media_type in self.data:
                return self.data[media_type].get("link") or self.data[media_type].get("url")
        return None