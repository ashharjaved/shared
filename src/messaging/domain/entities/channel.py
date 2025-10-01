"""WhatsApp Channel entity - core business logic for channel management."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum
from uuid import UUID

class ChannelStatus(Enum):
    """Channel connection status."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


@dataclass
class Channel:
    """
    WhatsApp Business API channel configuration.
    Represents a phone number connected to WhatsApp Business API.
    """
    id: UUID
    tenant_id: UUID
    name: str
    phone_number_id: str  # WhatsApp Phone Number ID
    business_phone: str  # Display phone number
    access_token: str  # Encrypted
    status: ChannelStatus
    rate_limit_per_second: int = 80
    monthly_message_limit: Optional[int] = None
    current_month_usage: int = 0
    webhook_verify_token: Optional[str] = None
    created_at: Optional[datetime] = None 
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        now = datetime.utcnow()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def can_send_message(self) -> bool:
        """Check if channel can send messages."""
        if self.status != ChannelStatus.ACTIVE:
            return False
        if self.monthly_message_limit and self.current_month_usage >= self.monthly_message_limit:
            return False
        return True
    
    def increment_usage(self) -> None:
        """Increment monthly usage counter."""
        self.current_month_usage += 1
        self.updated_at = datetime.utcnow()
    
    def reset_monthly_usage(self) -> None:
        """Reset monthly usage counter."""
        self.current_month_usage = 0
        self.updated_at = datetime.utcnow()
    
    def activate(self) -> None:
        """Activate the channel."""
        if self.status == ChannelStatus.SUSPENDED:
            raise ValueError("Cannot activate suspended channel without admin intervention")
        self.status = ChannelStatus.ACTIVE
        self.updated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate the channel."""
        self.status = ChannelStatus.INACTIVE
        self.updated_at = datetime.utcnow()
    
    def suspend(self, reason: str) -> None:
        """Suspend channel (e.g., for violations)."""
        self.status = ChannelStatus.SUSPENDED
        self.updated_at = datetime.utcnow()