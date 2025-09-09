# src/messaging/domain/entities/channel.py
"""WhatsApp channel aggregate root."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from ..exceptions import ValidationError, InvariantViolation
from ..types import TenantId, ChannelId


@dataclass(slots=True)
class Channel:
    """WhatsApp channel aggregate root.
    
    Represents a WhatsApp Business Account phone number connection
    with tenant-scoped access and secret management.
    """
    
    id: ChannelId
    tenant_id: TenantId
    phone_number_id: str
    waba_id: str
    display_name: str
    status: str
    verify_token: str
    app_secret: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def __post_init__(self) -> None:
        """Validate channel invariants on construction.
        
        Raises:
            ValidationError: If channel data is invalid
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="active",
            ...     verify_token="verify123",
            ...     app_secret="secret123",
            ...     created_at=datetime.now()
            ... )
            >>> channel.is_active()
            True
        """
        self._validate_phone_number_id()
        self._validate_waba_id()
        self._validate_status()
        self._validate_secrets()
    
    def _validate_phone_number_id(self) -> None:
        """Validate phone number ID format."""
        if not self.phone_number_id:
            raise ValidationError("Phone number ID cannot be empty")
        if not self.phone_number_id.isdigit():
            raise ValidationError("Phone number ID must be numeric")
    
    def _validate_waba_id(self) -> None:
        """Validate WhatsApp Business Account ID format."""
        if not self.waba_id:
            raise ValidationError("WABA ID cannot be empty")
        if not self.waba_id.startswith("waba_"):
            raise ValidationError("WABA ID must start with 'waba_'")
    
    def _validate_status(self) -> None:
        """Validate channel status."""
        valid_statuses = {"active", "inactive"}
        if self.status not in valid_statuses:
            raise ValidationError(f"Status must be one of: {valid_statuses}")
    
    def _validate_secrets(self) -> None:
        """Validate channel secrets."""
        if not self.verify_token:
            raise ValidationError("Verify token cannot be empty")
        if not self.app_secret:
            raise ValidationError("App secret cannot be empty")
        if len(self.verify_token) < 8:
            raise ValidationError("Verify token must be at least 8 characters")
        if len(self.app_secret) < 16:
            raise ValidationError("App secret must be at least 16 characters")
    
    def is_active(self) -> bool:
        """Check if channel is active.
        
        Returns:
            True if channel status is active
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="active",
            ...     verify_token="verify123",
            ...     app_secret="secret123456789",
            ...     created_at=datetime.now()
            ... )
            >>> channel.is_active()
            True
        """
        return self.status == "active"
    
    def activate(self) -> None:
        """Activate the channel.
        
        Raises:
            InvariantViolation: If already active
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="inactive",
            ...     verify_token="verify123",
            ...     app_secret="secret123456789",
            ...     created_at=datetime.now()
            ... )
            >>> channel.activate()
            >>> channel.is_active()
            True
        """
        if self.status == "active":
            raise InvariantViolation("Channel is already active")
        
        self.status = "active"
        self.updated_at = datetime.utcnow()
    
    def deactivate(self) -> None:
        """Deactivate the channel.
        
        Raises:
            InvariantViolation: If already inactive
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="active",
            ...     verify_token="verify123",
            ...     app_secret="secret123456789",
            ...     created_at=datetime.now()
            ... )
            >>> channel.deactivate()
            >>> channel.is_active()
            False
        """
        if self.status == "inactive":
            raise InvariantViolation("Channel is already inactive")
        
        self.status = "inactive"
        self.updated_at = datetime.utcnow()
    
    def rotate_secrets(self, new_verify_token: str, new_app_secret: str) -> None:
        """Rotate channel secrets.
        
        Args:
            new_verify_token: New webhook verify token
            new_app_secret: New app secret for signature verification
            
        Raises:
            ValidationError: If new secrets are invalid
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="active",
            ...     verify_token="verify123",
            ...     app_secret="secret123456789",
            ...     created_at=datetime.now()
            ... )
            >>> channel.rotate_secrets("newverify123", "newsecret123456789")
            >>> channel.verify_token
            'newverify123'
        """
        # Temporarily set to validate
        old_verify = self.verify_token
        old_secret = self.app_secret
        
        self.verify_token = new_verify_token
        self.app_secret = new_app_secret
        
        try:
            self._validate_secrets()
        except ValidationError:
            # Restore old values on validation failure
            self.verify_token = old_verify
            self.app_secret = old_secret
            raise
        
        self.updated_at = datetime.utcnow()
    
    def update_display_name(self, display_name: str) -> None:
        """Update channel display name.
        
        Args:
            display_name: New display name
            
        Raises:
            ValidationError: If display name is invalid
            
        Examples:
            >>> from uuid import uuid4
            >>> from datetime import datetime
            >>> channel = Channel(
            ...     id=ChannelId(uuid4()),
            ...     tenant_id=TenantId(uuid4()),
            ...     phone_number_id="123456789",
            ...     waba_id="waba_123",
            ...     display_name="Test Channel",
            ...     status="active",
            ...     verify_token="verify123",
            ...     app_secret="secret123456789",
            ...     created_at=datetime.now()
            ... )
            >>> channel.update_display_name("Updated Channel")
            >>> channel.display_name
            'Updated Channel'
        """
        if not display_name or not display_name.strip():
            raise ValidationError("Display name cannot be empty")
        
        self.display_name = display_name.strip()
        self.updated_at = datetime.utcnow()