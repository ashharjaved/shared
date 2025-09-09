# src/shared/events.py
"""Domain event system for the WhatsApp SaaS platform."""

from uuid import UUID
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum

from pydantic import Field


class EventPriority(str, Enum):
    """Event processing priority levels."""
    LOW = "low"
    NORMAL = "normal" 
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DomainEvent(ABC):
    """Base class for all domain events."""
    
    # Automatically generated fields
    event_id: str = field(default_factory=lambda: str(UUID()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    # Event metadata
    event_version: int = 1
    priority: EventPriority = EventPriority.NORMAL
    
    # Context fields - set by infrastructure
    tenant_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    
    @property
    @abstractmethod
    def event_type(self) -> str:
        """Unique identifier for this event type."""
        pass
    
    @property
    def aggregate_id(self) -> Optional[str]:
        """ID of the aggregate that produced this event."""
        return None
    
    @property 
    def aggregate_type(self) -> Optional[str]:
        """Type of aggregate that produced this event."""
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        result = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
            "priority": self.priority.value,
        }
        
        if self.correlation_id:
            result["correlation_id"] = self.correlation_id
        if self.causation_id:
            result["causation_id"] = self.causation_id
        if self.tenant_id:
            result["tenant_id"] = str(self.tenant_id)
        if self.user_id:
            result["user_id"] = str(self.user_id)
        if self.aggregate_id:
            result["aggregate_id"] = self.aggregate_id
        if self.aggregate_type:
            result["aggregate_type"] = self.aggregate_type
            
        # Add event-specific data
        event_data = {}
        for key, value in self.__dict__.items():
            if not key.startswith(('event_', 'occurred_at', 'correlation_id', 'causation_id', 'tenant_id', 'user_id', 'priority')):
                if isinstance(value, UUID):
                    event_data[key] = str(value)
                elif isinstance(value, Enum):
                    event_data[key] = value.value
                elif isinstance(value, datetime):
                    event_data[key] = value.isoformat()
                else:
                    event_data[key] = value
        
        if event_data:
            result["data"] = event_data
            
        return result


class DomainEventPublisher:
    """Publisher for domain events using outbox pattern."""
    
    def __init__(self):
        self._events: List[DomainEvent] = []
    
    def publish(self, event: DomainEvent) -> None:
        """Add event to the current batch for publishing."""
        self._events.append(event)
    
    def get_events(self) -> List[DomainEvent]:
        """Get all events in the current batch."""
        return self._events.copy()
    
    def clear(self) -> List[DomainEvent]:
        """Clear and return all events in the current batch."""
        events = self._events.copy()
        self._events.clear()
        return events
    
    def has_events(self) -> bool:
        """Check if there are any events to publish."""
        return bool(self._events)


class EventHandler(ABC):
    """Base class for domain event handlers."""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle a domain event."""
        pass
    
    @property
    @abstractmethod
    def handled_events(self) -> List[Type[DomainEvent]]:
        """List of event types this handler can process."""
        pass

class TenantEvent(DomainEvent):
    """Base class for tenant-related events."""
    pass


class MessageEvent(DomainEvent):
    """Base class for message-related events."""
    pass

# Message Events
class MessageSendRequested(MessageEvent):
    """Message send was requested."""
    channel_id: UUID
    to: str
    message_type: str
    content: Dict[str, Any]
    idempotency_key: Optional[str] = None
    requested_by_user_id: UUID


class MessageSent(MessageEvent):
    """Message was successfully sent."""
    channel_id: UUID
    to: str
    message_type: str
    provider_message_id: str
    sent_at: datetime


class MessageDelivered(MessageEvent):
    """Message was delivered."""
    channel_id: UUID
    to: str
    provider_message_id: str
    delivered_at: datetime


class MessageFailed(MessageEvent):
    """Message failed to send."""
    channel_id: UUID
    to: str
    message_type: str
    error_code: str
    error_message: str
    attempt_count: int
    will_retry: bool


# Conversation Events
class ConversationStarted(MessageEvent):
    """Conversation was started."""
    channel_id: UUID
    phone_number: str
    flow_id: UUID
    session_id: UUID


class ConversationEnded(MessageEvent):
    """Conversation was ended."""
    channel_id: UUID
    phone_number: str
    session_id: UUID
    reason: str
    message_count: int
    duration_seconds: int


class MenuStepCompleted(MessageEvent):
    """Menu step was completed."""
    channel_id: UUID
    phone_number: str
    session_id: UUID
    menu_key: str
    input_received: str
    next_menu_key: Optional[str] = None