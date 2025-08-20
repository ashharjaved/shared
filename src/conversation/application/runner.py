from __future__ import annotations
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from pydantic import BaseModel
from ..domain.entities import Flow, Node, NodeType, Session
from ..domain.services import (
    StepResult, Action, FlowDefinitionError, GuardExceeded, SessionExpired
)
from ..infrastructure.evaluators import safe_eval
from ..infrastructure.repositories import FlowRepository, SessionRepository, ConfigRepository
from ...config import Settings

class FlowRunner:
    def __init__(self, flow_repo: FlowRepository, session_repo: SessionRepository, config_repo: ConfigRepository, settings: Settings):
        self.flows = flow_repo
        self.sessions = session_repo
        self.configs = config_repo
        self.settings = settings

    async def run_trigger(self, tenant_id: UUID, channel_id: UUID, phone: str, payload: Dict[str, Any], event_id: Optional[str]) -> Dict[str, Any]:
        flow = await self.flows.get_active_default_flow(tenant_id)
        if not flow:
            raise FlowDefinitionError("No active default flow")
        session = await self.sessions.get_or_create(tenant_id, channel_id, phone, self.settings.CE_SESSION_TTL_SECONDS)
        if session.expires_at < datetime.now(timezone.utc):
            await self.sessions.expire(session)
            raise SessionExpired("Session expired")
        # idempotency
        last_eid = session.context.get("last_event_id")
        if last_eid and event_id and last_eid == event_id:
            return {"session_id": str(session.id), "outbound": [], "skipped": True}

        await self.sessions.optimistic_touch(session, self.settings.CE_LOCK_TIMEOUT_SECONDS)
        return await self._run(flow, session, payload, event_id)

    async def _run(self, flow: Flow, session: Session, payload: Dict[str, Any], event_id: Optional[str]) -> Dict[str, Any]:
        cfg = await self.configs.get_config_map(session.tenant_id)
        steps_done = 0
        outbound_previews: List[Dict[str, Any]] = []

        # current node
        node_id = session.current_node_id or flow.start_node_id
        ended = False

        while steps_done < self.settings.CE_MAX_STEPS_PER_TICK and not ended:
            node = flow.nodes.get(node_id)
            if not node:
                raise FlowDefinitionError(f"Node '{node_id}' missing")
            ctx = {"payload": payload, "vars": session.vars, "config": cfg}

            if node.type == NodeType.START:
                next_id = node.next or flow.start_node_id
                step = StepResult(node_id=node.id, actions=[], next_node_id=next_id)
            elif node.type == NodeType.MESSAGE:
                # Simple template replacement: {{config.key}} or {{vars.key}}
                text = node.text or ""
                def _tpl_replace(s: str) -> str:
                    import re
                    def repl(m):
                        path = m.group(1).strip()
                        # dot-get
                        cur = ctx
                        for part in path.split("."):
                            if isinstance(cur, dict) and part in cur:
                                cur = cur[part]
                            else:
                                return ""
                        return str(cur if cur is not None else "")
                    return re.sub(r"\{\{\s*([^}]+)\s*\}\}", repl, s)
                content = {"text": _tpl_replace(text)}
                outbound_previews.append({
                    "type": Action.SEND_MESSAGE.value,
                    "payload": {
                        "to_phone": session.phone_number,
                        "message_type": "text",
                        "content": content
                    }
                })
                step = StepResult(node_id=node.id, actions=[{"type": Action.SEND_MESSAGE.value, "payload": content}], next_node_id=node.next)
            elif node.type == NodeType.SET_VAR:
                for k, v in (node.assign or {}).items():
                    session.vars[k] = v
                step = StepResult(node_id=node.id, actions=[{"type": Action.SET_VAR.value, "payload": node.assign or {}}], next_node_id=node.next)
            elif node.type == NodeType.BRANCH:
                next_id = None
                next_id = self._evaluate_branch(node, ctx)
                step = StepResult(node_id=node.id, actions=[], next_node_id=next_id)
            elif node.type == NodeType.END:
                ended = True
                step = StepResult(node_id=node.id, actions=[{"type": Action.END.value}], next_node_id=None, ended=True)
            else:
                raise FlowDefinitionError(f"Unsupported node type: {node.type}")

            # persist step
            await self.sessions.save_progress(
                session,
                current_node_id=step.next_node_id,
                vars=session.vars,
                last_event_id=event_id,
                status=("EXPIRED" if ended else session.status),
                stage=("COMPLETED" if ended else "IN_PROGRESS"),
                ttl_seconds=self.settings.CE_SESSION_TTL_SECONDS if not ended else None,
            )
            steps_done += 1
            if step.next_node_id:
                node_id = step.next_node_id
            else:
                break

        if steps_done >= self.settings.CE_MAX_STEPS_PER_TICK and not ended:
            raise GuardExceeded("Max steps per tick reached")
        return {"session_id": str(session.id), "outbound": outbound_previews, "ended": ended}

    def _evaluate_branch(self, node: Node, ctx: Dict[str, Any]) -> Optional[str]:
        # Reuse safe_eval directly (ordered branches)
        if not node.branches:
            return node.next
        fallback = None
        for edge in node.branches:
            cond = getattr(edge, "when", "default")
            nxt = getattr(edge, "next", None)
            if str(cond).strip().lower() == "default":
                fallback = nxt
                continue
            if safe_eval(cond, ctx):
                return nxt
        return fallback
