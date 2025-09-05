#*** Begin: src/conversation/application/services/conversation_service.py ***
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List, cast
from uuid import UUID

from ...domain.entities import ConversationSession, MenuFlow
from ...domain.errors import FlowNotFoundError, InvalidSelectionError
from ...domain.repositories.flow_repository import FlowRepository
from ...domain.repositories.session_repository import SessionRepository
from ...domain.value_objects import JSONArray, MenuDefinition, JSONValue
from ..actions import ActionRouter
from ..context import RequestContext

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversationConfig:
    session_ttl_minutes: int = 30  # DB clamps to 30 mins, this is informative
    max_steps_per_session: int = 50  # anti-loop guard


class ConversationService:
    """
    Deterministic state machine that interprets inbound text into reply text.
    - DB is the source of truth; Redis may layer on top separately if desired.
    - Keeps menu position (key) and stack inside session.context_jsonb.
    """

    # context keys
    _CTX_MENU_KEY = "current_menu_key"    # str
    _CTX_MENU_STACK = "menu_stack"        # list[str]
    _CTX_STEPS = "steps"                  # int

    def __init__(
        self,
        *,
        flows: FlowRepository,
        sessions: SessionRepository,
        action_router: ActionRouter,
        config: ConversationConfig | None = None,
    ) -> None:
        self._flows = flows
        self._sessions = sessions
        self._actions = action_router
        self._cfg = config or ConversationConfig()

    async def handle_message(
        self,
        *,
        channel_id: UUID,
        user_phone: str,
        text: str,
        ctx: Optional[RequestContext] = None,
        industry_hint: Optional[str] = None,
    ) -> str:
        """
        High-level algorithm:
        1) Open/refresh session via sp_open_session (RLS enforced in repo).
        2) If first time (no flow bound), bind to tenant default flow and set menu key='main'.
        3) Parse commands (main/back/exit).
        4) Resolve selection -> next_menu or action; update context and/or call ActionRouter.
        5) Persist session changes (current_menu_id, context), bump counters.
        6) Return reply text for Messaging to send.
        """
        session = await self._sessions.open(channel_id=channel_id, phone_number=user_phone)
        if ctx:
            ctx.channel_id = channel_id
            ctx.session_id = session.id

        # Get or initialize flow/menu state
        flow, menu_key = await self._ensure_flow_and_menu(session, industry_hint=industry_hint)

        # Anti-loop safety
        steps = int(self._get_ctx_counter(session, self._CTX_STEPS))
        if steps >= self._cfg.max_steps_per_session:
            return "You’re typing fast. Please wait a bit and try again."

        # Normalize input
        incoming = text.strip()
        lowered = incoming.lower()

        # Commands
        if lowered in {"main", "menu", "restart"}:
            self._set_menu(session, "main")
            await self._persist_state(session, flow, changed_menu=True)
            return self._render_prompt(flow.definition, "main")

        if lowered in {"back", "prev"}:
            prev = self._pop_stack(session)
            key = prev or "main"
            self._set_menu(session, key)
            await self._persist_state(session, flow, changed_menu=True)
            return self._render_prompt(flow.definition, key)

        if lowered in {"exit", "bye"}:
            await self._sessions.close(session_id=session.id)
            return "Session closed. Send any message to start again."

        # Regular selection
        opt = flow.definition.resolve_option(menu_key, incoming)
        if opt is None:
            # invalid selection — don't move; just show prompt again
            await self._bump(session)
            return f"Invalid option. Please try again.\n\n{self._render_prompt(flow.definition, menu_key)}"

        # Switch to next menu
        if opt.next_menu:
            self._push_stack(session, menu_key)
            self._set_menu(session, opt.next_menu)
            await self._persist_state(session, flow, changed_menu=True)
            return self._render_prompt(flow.definition, opt.next_menu)

        # Invoke action
        if opt.action:
            reply = await self._actions.handle(
                tenant_id=session.tenant_id,
                session=session,
                flow=flow,
                action=opt.action,
                context=session.context,
            )
            await self._bump(session)
            # Optionally show the current menu prompt again (good UX)
            menu_key = self._get_menu_key(session)
            prompt = self._render_prompt(flow.definition, menu_key)
            return f"{reply}\n\n{prompt}"

        # Nothing to do — should not happen if schema is valid
        await self._bump(session)
        return self._render_prompt(flow.definition, menu_key)

    # ----------------------- internals -----------------------

    async def _ensure_flow_and_menu(
        self,
        session: ConversationSession,
        *,
        industry_hint: Optional[str],
    ) -> tuple[MenuFlow, str]:
        """
        Ensure session has a bound flow and a current menu key.
        - If session.current_menu_id is None → pick tenant default flow (optionally filtered by industry_hint)
        - Ensure context has current_menu_key and menu_stack
        """
        if session.current_menu_id is None:
            try:
                flow = await self._flows.get_default(industry_type=industry_hint)
            except FlowNotFoundError:
                # Fallback: any active default regardless of industry
                flow = await self._flows.get_default(industry_type=None)
            # bind flow id and set menu key
            session.set_current_menu(flow.id)
            self._init_context_if_needed(session)
            self._set_menu(session, "main")
            await self._sessions.set_current_menu(session_id=session.id, menu_id=flow.id)
            await self._sessions.save_context(session_id=session.id, context=session.context)
            return flow, "main"

        # We have a flow; fetch it
        flow = await self._flows.get_by_id(session.current_menu_id)
        self._init_context_if_needed(session)
        mk = self._get_menu_key(session)
        if not flow.definition.has_menu(mk):
            # Heal corrupt/unknown menu key by resetting to main
            self._set_menu(session, "main")
            await self._sessions.save_context(session_id=session.id, context=session.context)
            mk = "main"
        return flow, mk

    async def _persist_state(self, session: ConversationSession, flow: MenuFlow, *, changed_menu: bool) -> None:
        """
        Persist menu changes and step counter; bump message_count and last_activity.
        """
        # Increase step counter
        steps = int(self._get_ctx_counter(session, self._CTX_STEPS))
        session.context[self._CTX_STEPS] = steps + 1

        # Save context first
        await self._sessions.save_context(session_id=session.id, context=session.context)

        # Persist menu id only when binding flow first time; otherwise flow id is already set
        if changed_menu:
            # flow id remains same; only context menu key changes
            pass

        # Bump message counters & last_activity
        await self._sessions.bump_message_count(session_id=session.id)

    async def _bump(self, session: ConversationSession) -> None:
        # Increase steps + persist + bump counter
        steps = int(self._get_ctx_counter(session, self._CTX_STEPS))
        session.context[self._CTX_STEPS] = steps + 1
        await self._sessions.save_context(session_id=session.id, context=session.context)
        await self._sessions.bump_message_count(session_id=session.id)

    # ---- context helpers ----

    def _init_context_if_needed(self, session: ConversationSession) -> None:
        if self._CTX_MENU_STACK not in session.context:
            session.context[self._CTX_MENU_STACK] = cast(JSONArray, [])
        if self._CTX_MENU_KEY not in session.context:
            session.context[self._CTX_MENU_KEY] = "main"
        if self._CTX_STEPS not in session.context:
            session.context[self._CTX_STEPS] = 0

    def _get_menu_key(self, session: ConversationSession) -> str:
        raw = session.context.get(self._CTX_MENU_KEY)
        return str(raw) if isinstance(raw, str) else "main"

    def _set_menu(self, session: ConversationSession, key: str) -> None:
        session.context[self._CTX_MENU_KEY] = key

    def _push_stack(self, session: ConversationSession, key: str) -> None:
        stack = self._stack(session)
        stack.append(key)
        session.context[self._CTX_MENU_STACK] = cast(JSONArray, stack)

    def _pop_stack(self, session: ConversationSession) -> Optional[str]:
        stack = self._stack(session)
        if not stack:
            return None
        prev = stack.pop()
        session.context[self._CTX_MENU_STACK] = cast(JSONArray, stack)
        return prev

    def _stack(self, session: ConversationSession) -> List[str]:
        raw = session.context.get(self._CTX_MENU_STACK)
        if isinstance(raw, list):
            # coerce to list[str]
            return [str(x) for x in raw]
        return []


    def _get_ctx_counter(self, session: ConversationSession, key: str) -> int:
        raw: JSONValue | None = session.context.get(key)
        # Narrow to primitives accepted by int()
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, (int, float)):
            return int(raw)
        if isinstance(raw, str):
            try:
                return int(raw)
            except Exception:
                return 0
        # dict/list/None → 0
        return 0
    # ---- rendering ----

    def _render_prompt(self, definition: MenuDefinition, key: str) -> str:
        prompt = definition.prompt_for(key)
        opts = definition.options_for(key)
        # Keep numeric keys ordered if possible; else stable by key
        try:
            ordered = sorted(opts.items(), key=lambda kv: int(kv[0]))
        except Exception:
            ordered = sorted(opts.items(), key=lambda kv: kv[0])
        lines = [prompt]
        for k, opt in ordered:
            lines.append(f"{k}) {opt.label}")
        return "\n".join(lines)
#* End: src/conversation/application/services/conversation_service.py ***
