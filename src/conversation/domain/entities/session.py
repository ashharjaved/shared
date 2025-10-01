# src/conversation/domain/entities/session.py
"""Session entity - represents an active conversation session."""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from src.shared.domain.entity import Entity
from src.conversation.domain.value_objects import SessionStatus


class Session(Entity):
    """
    Session aggregate root.
    
    Represents an active conversation session with a user.
    Manages session lifecycle, context, and timeout.
    """
    
    DEFAULT_TTL_MINUTES = 30
    MAX_MESSAGE_HISTORY = 3
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        channel_id: UUID,
        user_msisdn: str,
        flow_id: UUID,
        current_step_key: str,
        status: SessionStatus,
        language: str,
        context: Dict[str, Any],
        message_history: List[Dict[str, Any]],
        created_at: datetime,
        updated_at: datetime,
        expires_at: datetime,
        intent_history: Optional[List[str]] = None,
    ):
        super().__init__(id)
        self.tenant_id = tenant_id
        self.channel_id = channel_id
        self.user_msisdn = user_msisdn
        self.flow_id = flow_id
        self.current_step_key = current_step_key
        self.status = status
        self.language = language
        self.context = context
        self.message_history = message_history
        self.created_at = created_at
        self.updated_at = updated_at
        self.expires_at = expires_at
        self.intent_history = intent_history or []
    
    @classmethod
    def create(
        cls,
        id: UUID,
        tenant_id: UUID,
        channel_id: UUID,
        user_msisdn: str,
        flow_id: UUID,
        entry_step_key: str,
        language: str = "en",
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> "Session":
        """Create a new session."""
        now = datetime.utcnow()
        return cls(
            id=id,
            tenant_id=tenant_id,
            channel_id=channel_id,
            user_msisdn=user_msisdn,
            flow_id=flow_id,
            current_step_key=entry_step_key,
            status=SessionStatus.ACTIVE,
            language=language,
            context={},
            message_history=[],
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
    
    def advance_to_step(self, step_key: str) -> None:
        """Move session to next step."""
        if self.status != SessionStatus.ACTIVE:
            raise ValueError(f"Cannot advance session in {self.status} status")
        
        self.current_step_key = step_key
        self.touch()
    
    def update_context(self, key: str, value: Any) -> None:
        """Update session context variable."""
        self.context[key] = value
        self.touch()
    
    def add_message(self, role: str, content: str, intent: Optional[str] = None) -> None:
        """Add message to history (keep last N messages)."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if intent:
            message["intent"] = intent
            self.intent_history.append(intent)
        
        self.message_history.append(message)
        
        # Keep only last N messages
        if len(self.message_history) > self.MAX_MESSAGE_HISTORY:
            self.message_history = self.message_history[-self.MAX_MESSAGE_HISTORY:]
        
        self.touch()
    
    def touch(self, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> None:
        """Update session activity and extend TTL."""
        now = datetime.utcnow()
        self.updated_at = now
        self.expires_at = now + timedelta(minutes=ttl_minutes)
    
    def complete(self) -> None:
        """Mark session as completed."""
        self.status = SessionStatus.COMPLETED
        self.updated_at = datetime.utcnow()
    
    def expire(self) -> None:
        """Mark session as expired."""
        self.status = SessionStatus.EXPIRED
        self.updated_at = datetime.utcnow()
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() > self.expires_at
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """Get value from session context."""
        return self.context.get(key, default)
    
    def get_recent_messages(self, count: int = MAX_MESSAGE_HISTORY) -> List[Dict[str, Any]]:
        """Get recent messages for NLP context."""
        return self.message_history[-count:]