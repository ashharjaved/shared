# Begin: src/conversation/application/actions.py ***
from __future__ import annotations

from typing import Protocol, Mapping
from uuid import UUID

from ..domain.entities import ConversationSession, MenuFlow
from ..domain.value_objects import JSONValue


class ActionRouter(Protocol):
    """
    Interface for pluggable business actions triggered from menu options.
    Implementations must be pure (no framework objects), and return reply text.
    """

    async def handle(
        self,
        *,
        tenant_id: UUID,
        session: ConversationSession,
        flow: MenuFlow,
        action: str,
        context: Mapping[str, JSONValue],
    ) -> str: ...


class DefaultActionRouter(ActionRouter):
    """
    Minimal, safe defaults — no PHI, no external calls.
    Extend/replace with domain-specific routers (e.g., appointments, fees).
    """

    async def handle(
        self,
        *,
        tenant_id: UUID,
        session: ConversationSession,
        flow: MenuFlow,
        action: str,
        context: Mapping[str, JSONValue],
    ) -> str:
        a = action.upper()

        if a == "SHOW_HOURS":
            return "Hours: Mon–Sat 9:00–18:00, Sun closed."
        if a == "SHOW_CONTACT":
            return "Contact: +91-80000-00000 or reply 'HELP' for assistance."
        if a == "CONNECT_AGENT":
            # Stub: upstream Messaging module can route to a live agent queue
            return "Connecting you to an agent. Please wait…"
        if a == "HELP":
            return "Send 1/2/3 to choose options. Try 'back', 'main', or 'exit'."
        if a == "BOOK_APPOINTMENT":
            # Stub: later integrate with Healthcare domain; keep text generic
            return "To book, please share preferred day and time. An agent will confirm."

        # Fallback: safe response
        return "Action is currently unavailable. Please choose another option."
# End: src/conversation/application/actions.py ***
