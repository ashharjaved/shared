# src/conversation/domain/repositories/session_repository.py
"""Session repository protocol."""

from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from src.conversation.domain.entities.session import Session


class SessionRepository(ABC):
    """Protocol for session persistence."""
    
    @abstractmethod
    async def add(self, session: Session) -> None:
        """Add new session."""
        pass
    
    @abstractmethod
    async def get_by_id(self, session_id: UUID, tenant_id: UUID) -> Optional[Session]:
        """Get session by ID with RLS."""
        pass
    
    @abstractmethod
    async def get_active_session(
        self, 
        tenant_id: UUID, 
        channel_id: UUID, 
        user_msisdn: str
    ) -> Optional[Session]:
        """Get active session for user on channel."""
        pass
    
    @abstractmethod
    async def update(self, session: Session) -> None:
        """Update existing session."""
        pass
    
    @abstractmethod
    async def expire_old_sessions(self, before: datetime) -> int:
        """Expire sessions older than threshold. Returns count."""
        pass
    
    @abstractmethod
    async def get_user_sessions(
        self,
        tenant_id: UUID,
        user_msisdn: str,
        limit: int = 10
    ) -> List[Session]:
        """Get user's session history."""
        pass