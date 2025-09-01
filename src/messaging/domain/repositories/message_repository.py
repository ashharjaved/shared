from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.messaging.domain.entities.message import Message, MessageStatus, PhoneNumber


class MessageRepository(ABC):
    """
    Tenant-scoped repository interface for messages.
    Implementation SHOULD wrap DB stored procedures for atomicity:
      - sp_send_message(...) for queueing (idempotency + outbox).
      - sp_update_message_status(...) for safe transitions (outbox).
    """

    @abstractmethod
    async def queue_message(self, message: Message, *, idempotency_key: Optional[str] = None) -> Message:
        """
        Create an OUTBOUND message with initial status=QUEUED.
        MUST enforce idempotency (via DB proc or ensure_idempotency()).
        Returns the persisted Message (including DB-generated fields).
        """
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, message_id: UUID, new_status: MessageStatus) -> Message:
        """
        Update message status using the DB transition rules.
        Returns the updated Message.
        """
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(self, message_id: UUID) -> Optional[Message]:
        """
        Fetch a message by internal id within the *current* tenant, or None.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_recent_conversation(
        self,
        channel_id: UUID,
        peer_phone: PhoneNumber,
        *,
        limit: int = 50,
    ) -> List[Message]:
        """
        Return recent messages for a conversation (both directions) between the channel
        and the given peer phone number, ordered DESC by creation time, limited.
        Implementations may use a view (e.g., vw_conversation_windows) or a partition-aware query.
        """
        raise NotImplementedError