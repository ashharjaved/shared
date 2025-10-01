"""WhatsApp webhook payload value objects."""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass(frozen=True)
class WebhookMessage:
    """Inbound message from webhook."""
    id: str  # WhatsApp message ID
    from_number: str
    timestamp: datetime
    type: str  # text, image, audio, etc.
    text: Optional[str] = None
    media_id: Optional[str] = None
    media_url: Optional[str] = None
    mime_type: Optional[str] = None
    context: Optional[Dict[str, Any]] = None  # Reply context
    
    @classmethod
    def from_webhook_data(cls, data: Dict[str, Any]) -> 'WebhookMessage':
        """Parse webhook message data."""
        msg = data['messages'][0]
        return cls(
            id=msg['id'],
            from_number=msg['from'],
            timestamp=datetime.fromtimestamp(int(msg['timestamp'])),
            type=msg['type'],
            text=msg.get('text', {}).get('body') if msg['type'] == 'text' else None,
            media_id=msg.get(msg['type'], {}).get('id') if msg['type'] in ['image', 'audio', 'video', 'document'] else None,
            mime_type=msg.get(msg['type'], {}).get('mime_type') if msg['type'] in ['image', 'audio', 'video', 'document'] else None,
            context=msg.get('context')
        )


@dataclass(frozen=True)
class WebhookStatus:
    """Message status update from webhook."""
    message_id: str
    recipient_id: str
    status: str  # sent, delivered, read, failed
    timestamp: datetime
    error: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_webhook_data(cls, data: Dict[str, Any]) -> 'WebhookStatus':
        """Parse webhook status data."""
        status = data['statuses'][0]
        return cls(
            message_id=status['id'],
            recipient_id=status['recipient_id'],
            status=status['status'],
            timestamp=datetime.fromtimestamp(int(status['timestamp'])),
            error=status.get('errors', [None])[0] if 'errors' in status else None
        )


@dataclass(frozen=True)
class WebhookVerification:
    """Webhook verification challenge."""
    mode: str
    token: str
    challenge: str
    
    def is_valid(self, expected_token: str) -> bool:
        """Verify the webhook challenge."""
        return self.mode == 'subscribe' and self.token == expected_token