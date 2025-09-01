from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.messaging.domain.entities.channel import Channel

class ChannelRepository(ABC):
    """
    Tenant-scoped repository interface (RLS enforced in Infrastructure).
    DO NOT add infra-specific concerns here (sessions, SQLAlchemy, etc.).
    """

    @abstractmethod
    async def create(self, channel: Channel) -> Channel:
        """
        Persist a new Channel for the *current* tenant and return the stored entity.
        Infra must handle:
          - Encryption-at-rest for `token`.
          - Setting/using `app.jwt_tenant` for RLS.
        """
        raise NotImplementedError

    @abstractmethod
    async def list(self) -> List[Channel]:
        """
        List all channels for the *current* tenant (RLS).
        """
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, channel_id: UUID) -> Optional[Channel]:
        """
        Fetch a Channel by id within the *current* tenant context, or None if not found.
        """
        raise NotImplementedError
