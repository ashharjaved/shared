"""
WhatsApp Channel Entity
Represents a tenant's WhatsApp Business Account configuration.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from shared.domain.base_entity import BaseEntity


class Channel(BaseEntity):
    """
    Aggregate root for WhatsApp channel configuration.
    
    Attributes:
        tenant_id: Owning tenant UUID
        name: Human-readable channel name
        phone_number_id: WhatsApp phone number ID from Meta
        business_phone: E.164 formatted phone number
        waba_id: WhatsApp Business Account ID
        access_token_encrypted: Encrypted Meta API token
        status: Channel operational status
        rate_limit_per_second: Send rate limit (default 80/sec)
        monthly_message_limit: Quota limit
        webhook_verify_token: Token for webhook verification
        metadata: Additional configuration (JSON)
    """
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        name: str,
        phone_number_id: str,
        business_phone: str,
        waba_id: str,
        access_token_encrypted: str,
        status: str = "active",
        rate_limit_per_second: int = 80,
        monthly_message_limit: int = 10000,
        webhook_verify_token: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        super().__init__(id, created_at, updated_at)
        self.tenant_id = tenant_id
        self.name = name
        self.phone_number_id = phone_number_id
        self.business_phone = business_phone
        self.waba_id = waba_id
        self.access_token_encrypted = access_token_encrypted
        self.status = status
        self.rate_limit_per_second = rate_limit_per_second
        self.monthly_message_limit = monthly_message_limit
        self.webhook_verify_token = webhook_verify_token
        self.metadata = metadata or {}
    
    def activate(self) -> None:
        """Activate the channel."""
        self.status = "active"
    
    def suspend(self) -> None:
        """Suspend the channel."""
        self.status = "suspended"
    
    def deactivate(self) -> None:
        """Deactivate the channel."""
        self.status = "inactive"
    
    def is_active(self) -> bool:
        """Check if channel is operational."""
        return self.status == "active"
    
    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name={self.name}, phone={self.business_phone})>"