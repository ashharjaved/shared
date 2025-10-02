"""
Channel Service
Business logic for channel management.
"""
from typing import List, Optional
from uuid import UUID, uuid4

from shared.infrastructure.security.field_encryption import decrypt_field_value, encrypt_field_value
from src.messaging.domain.entities.channel import Channel
from src.messaging.domain.protocols.channel_repository import ChannelRepository
from src.messaging.domain.exceptions import ChannelNotFoundError, ChannelInactiveError
#from shared.infrastructure.security.encryption import encrypt_field, decrypt_field
from shared.infrastructure.observability.logger import get_logger
from shared.infrastructure.security.audit_log import AuditLogger

logger = get_logger(__name__)


class ChannelService:
    """
    Application service for channel operations.
    
    Handles encryption, business rules, and audit logging.
    """
    
    def __init__(
        self,
        channel_repo: ChannelRepository,
        audit_logger: AuditLogger,
        encryption_key: str
    ):
        self.channel_repo = channel_repo
        self.audit_logger = audit_logger
        self.encryption_key = encryption_key
    
    async def create_channel(
        self,
        tenant_id: UUID,
        name: str,
        phone_number_id: str,
        business_phone: str,
        waba_id: str,
        access_token: str,
        rate_limit_per_second: int = 80,
        monthly_message_limit: int = 10000,
        webhook_verify_token: Optional[str] = None,
        metadata: Optional[dict] = None,
        user_id: Optional[UUID] = None
    ) -> Channel:
        """
        Create new WhatsApp channel.
        
        Encrypts access token before persistence.
        """
        # Check for duplicate
        existing = await self.channel_repo.get_by_tenant_and_phone(
            tenant_id, phone_number_id
        )
        if existing:
            raise ValueError("Channel with this phone number already exists")
        
        # Encrypt access token
        encrypted_token = encrypt_field_value(access_token)
        
        # Create entity
        channel = Channel(
            id=uuid4(),
            tenant_id=tenant_id,
            name=name,
            phone_number_id=phone_number_id,
            business_phone=business_phone,
            waba_id=waba_id,
            access_token_encrypted=encrypted_token,
            rate_limit_per_second=rate_limit_per_second,
            monthly_message_limit=monthly_message_limit,
            webhook_verify_token=webhook_verify_token,
            metadata=metadata or {}
        )
        
        # Persist
        channel = await self.channel_repo.create(channel)
        
        # Audit log
        await self.audit_logger.log(
            tenant_id=tenant_id,
            user_id=user_id,
            action="channel.created",
            resource_type="channel",
            resource_id=channel.id,
            details={"name": name, "phone": business_phone}
        )
        
        logger.info(
            f"Channel created: {channel.id}",
            extra={"tenant_id": tenant_id, "channel_id": channel.id}
        )
        
        return channel
    
    async def get_channel(self, channel_id: UUID) -> Channel:
        """Retrieve channel by ID."""
        channel = await self.channel_repo.get_by_id(channel_id)
        
        if not channel:
            raise ChannelNotFoundError(f"Channel {channel_id} not found")
        
        return channel
    
    async def list_channels(self, tenant_id: UUID) -> List[Channel]:
        """List all channels for tenant."""
        return await self.channel_repo.list_by_tenant(tenant_id)
    
    async def update_channel(
        self,
        channel_id: UUID,
        name: Optional[str] = None,
        rate_limit_per_second: Optional[int] = None,
        monthly_message_limit: Optional[int] = None,
        metadata: Optional[dict] = None,
        user_id: Optional[UUID] = None
    ) -> Channel:
        """Update channel configuration."""
        channel = await self.get_channel(channel_id)
        
        # Update fields
        if name:
            channel.name = name
        if rate_limit_per_second:
            channel.rate_limit_per_second = rate_limit_per_second
        if monthly_message_limit:
            channel.monthly_message_limit = monthly_message_limit
        if metadata:
            channel.metadata.update(metadata)
        
        # Persist
        channel = await self.channel_repo.update(channel)
        
        # Audit log
        await self.audit_logger.log(
            tenant_id=channel.tenant_id,
            user_id=user_id,
            action="channel.updated",
            resource_type="channel",
            resource_id=channel.id,
            details={"updates": {"name": name, "rate_limit": rate_limit_per_second}}
        )
        
        return channel
    
    async def activate_channel(
        self, channel_id: UUID, user_id: Optional[UUID] = None
    ) -> Channel:
        """Activate a suspended channel."""
        channel = await self.get_channel(channel_id)
        channel.activate()
        
        channel = await self.channel_repo.update(channel)
        
        await self.audit_logger.log(
            tenant_id=channel.tenant_id,
            user_id=user_id,
            action="channel.activated",
            resource_type="channel",
            resource_id=channel.id
        )
        
        return channel
    
    async def suspend_channel(
        self, channel_id: UUID, user_id: Optional[UUID] = None
    ) -> Channel:
        """Suspend a channel temporarily."""
        channel = await self.get_channel(channel_id)
        channel.suspend()
        
        channel = await self.channel_repo.update(channel)
        
        await self.audit_logger.log(
            tenant_id=channel.tenant_id,
            user_id=user_id,
            action="channel.suspended",
            resource_type="channel",
            resource_id=channel.id
        )
        
        return channel
    
    async def get_decrypted_token(self, channel_id: UUID) -> str:
        """
        Get decrypted access token for API calls.
        
        Use carefully - only for internal services.
        """
        channel = await self.get_channel(channel_id)
        
        if not channel.is_active():
            raise ChannelInactiveError(f"Channel {channel_id} is not active")
        
        return decrypt_field_value(channel.access_token_encrypted)