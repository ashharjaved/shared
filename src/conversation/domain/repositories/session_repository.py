## Begin: src/conversation/domain/repositories/session_repository.py ***
from __future__ import annotations

from typing import Mapping, Protocol, Optional
from uuid import UUID

from src.conversation.domain.value_objects import JSONValue

from ..entities import ConversationSession


class SessionRepository(Protocol):
    """
    Session repository for managing per-(channel, phone) sessions.
    Implementations should use DB procedures for open/close and enforce TTL & RLS.
    """

    async def open(self, *, channel_id: UUID, phone_number: str) -> ConversationSession:
        """
        Opens (or refreshes) a session for (channel_id, phone_number).
        Should call `sp_open_session` and return the session aggregate.
        """
        ...

    async def get_by_channel_phone(
        self, *, channel_id: UUID, phone_number: str
    ) -> Optional[ConversationSession]:
        """Returns an existing session or None if absent."""
        ...

    async def set_current_menu(self, *, session_id: UUID, menu_id: Optional[UUID]) -> None:
        """Persists the current_menu_id for a session."""
        ...

    async def bump_message_count(self, *, session_id: UUID) -> None:
        """Atomically increments message_count (and ideally last_activity)."""
        ...

    async def save_context(self, *, session_id: UUID, context: Mapping[str, JSONValue]) -> None:
        """
        Replaces or merges session context depending on implementation choice.
        (Application layer will define merge semantics.)
        """
        ...

    async def close(self, *, session_id: UUID) -> None:
        """Closes a session via sp_close_session."""
        ...
### End: src/conversation/domain/repositories/session_repository.py ***
