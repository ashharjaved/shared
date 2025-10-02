"""WhatsApp Channel aggregate root."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from shared.domain.base_aggregate_root import BaseAggregateRoot
from src.messaging.domain.value_objects import (
    PhoneNumber,
    WhatsAppBusinessAccountId,
    AccessToken,
    RateLimitTier,
    ChannelStatus
)

class Channel(BaseAggregateRoot):
    """WhatsApp Business Account Channel."""

    def __init__(
        self,
        id: UUID,
        organization_id: UUID,
        phone_number: PhoneNumber,
        business_account_id: WhatsAppBusinessAccountId,
        access_token: AccessToken,
        webhook_verify_token: str,
        status: ChannelStatus = ChannelStatus.ACTIVE,
        rate_limit_tier: RateLimitTier = RateLimitTier.STANDARD,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        super().__init__(id)
        self.organization_id = organization_id
        self.phone_number = phone_number
        self.business_account_id = business_account_id
        self.access_token = access_token
        self.webhook_verify_token = webhook_verify_token
        self.status = status
        self.rate_limit_tier = rate_limit_tier
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    @classmethod
    def provision(
        cls,
        organization_id: UUID,
        phone_number: str,
        phone_number_id: str,
        business_account_id: str,
        access_token: str,
        webhook_verify_token: str,
        rate_limit_tier: str = "standard"
    ) -> "Channel":
        """Provision a new WhatsApp channel."""
        channel = cls(
            id=UUID(),
            organization_id=organization_id,
            phone_number=PhoneNumber(phone_number),
            business_account_id=WhatsAppBusinessAccountId(business_account_id),
            access_token=AccessToken(access_token),
            webhook_verify_token=webhook_verify_token,
            status=ChannelStatus.ACTIVE,
            rate_limit_tier=RateLimitTier.from_string(rate_limit_tier)
        )        
        
        return channel

    def suspend(self, reason: str) -> None:
        """Suspend the channel."""
        if self.status == ChannelStatus.SUSPENDED:
            return
            
        self.status = ChannelStatus.SUSPENDED
        self.metadata["suspension_reason"] = reason
        self.metadata["suspended_at"] = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow()
        
    def activate(self) -> None:
        """Reactivate a suspended channel."""
        if self.status == ChannelStatus.ACTIVE:
            return
            
        self.status = ChannelStatus.ACTIVE
        self.metadata.pop("suspension_reason", None)
        self.metadata.pop("suspended_at", None)
        self.updated_at = datetime.utcnow()
        
    def update_access_token(self, new_token: str) -> None:
        """Update the access token."""
        self.access_token = AccessToken(new_token)
        self.updated_at = datetime.utcnow()

    def can_send_messages(self) -> bool:
        """Check if channel can send messages."""
        return self.status == ChannelStatus.ACTIVE