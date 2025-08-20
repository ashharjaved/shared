from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from .models import MenuFlow, ConversationSession
from ..domain.entities import Flow, Node, NodeType, Session
from datetime import datetime, timezone, timedelta

class FlowRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_default_flow(self, tenant_id: UUID) -> Optional[Flow]:
        stmt = (
            select(MenuFlow)
            .where(MenuFlow.tenant_id == tenant_id)
            .where(MenuFlow.is_active == True)  # noqa
            .where(MenuFlow.is_default == True)  # noqa
            .order_by(MenuFlow.version.desc())
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None
        definition = row.definition_jsonb
        nodes: Dict[str, Node] = {}
        for nid, nd in definition.get("nodes", {}).items():
            ntype = NodeType(nd["type"])
            node = Node(
                id=nid,
                type=ntype,
                text=nd.get("text"),
                assign=nd.get("assign"),
                branches=[Node(id="", type=NodeType.BRANCH)] and [
                    # normalize edges from dicts
                    __edge for __edge in (
                        [type("Edge", (), {"when": b.get("when","default"), "next": b.get("next")}) for b in nd.get("branches", [])]
                    )
                ] if nd.get("branches") else None,
                next=nd.get("next"),
            )
            nodes[nid] = node
        return Flow(id=row.id, name=row.name, version=row.version, start_node_id=definition["start_node_id"], nodes=nodes)

class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def get_or_create(self, tenant_id: UUID, channel_id: UUID, phone: str, ttl_seconds: int) -> Session:
        stmt = (
            select(ConversationSession)
            .where(ConversationSession.tenant_id == tenant_id)
            .where(ConversationSession.channel_id == channel_id)
            .where(ConversationSession.phone_number == phone)
            .limit(1)
        )
        row = (await self.db.execute(stmt)).scalar_one_or_none()
        expires_at = self._now() + timedelta(seconds=ttl_seconds)
        if not row:
            # INSERT
            ins = insert(ConversationSession).values(
                tenant_id=tenant_id,
                channel_id=channel_id,
                phone_number=phone,
                current_menu_id=None,
                context_jsonb={"vars": {}, "last_event_id": None},
                conversation_stage="INITIATED",
                status="ACTIVE",
                message_count=0,
                expires_at=expires_at,
                last_activity=self._now(),
            ).returning(ConversationSession)
            row = (await self.db.execute(ins)).scalar_one()
            await self.db.commit()
        return self._to_entity(row)

    async def refresh(self, sess: Session) -> Session:
        stmt = select(ConversationSession).where(ConversationSession.id == sess.id)
        row = (await self.db.execute(stmt)).scalar_one()
        return self._to_entity(row)

    async def optimistic_touch(self, sess: Session, lock_timeout_sec: int) -> None:
        # We use last_activity as a simple version field.
        old_last = sess.last_activity
        new_last = self._now()
        stmt = (
            update(ConversationSession)
            .where(ConversationSession.id == sess.id)
            .where(ConversationSession.last_activity == old_last)
            .values(last_activity=new_last)
        )
        res = await self.db.execute(stmt)
        if res.rowcount != 1:
            from ..domain.services import OptimisticLockError
            raise OptimisticLockError("Session modified concurrently")
        await self.db.commit()
        sess.last_activity = new_last

    async def save_progress(
        self,
        sess: Session,
        *,
        current_node_id: Optional[str],
        vars: Dict[str, Any],
        last_event_id: Optional[str],
        status: Optional[str] = None,
        stage: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        values = {
            "current_menu_id": None,  # keep null; we store node id in context vars
            "context_jsonb": {**(sess.context or {}), "vars": vars, "last_event_id": last_event_id, "current_node_id": current_node_id},
        }
        if status:
            values["status"] = status
        if stage:
            values["conversation_stage"] = stage
        if ttl_seconds:
            values["expires_at"] = self._now() + timedelta(seconds=ttl_seconds)
        stmt = update(ConversationSession).where(ConversationSession.id == sess.id).values(**values)
        await self.db.execute(stmt)
        await self.db.commit()

    async def expire(self, sess: Session) -> None:
        stmt = update(ConversationSession).where(ConversationSession.id == sess.id).values(status="EXPIRED", conversation_stage="EXPIRED", expires_at=self._now())
        await self.db.execute(stmt)
        await self.db.commit()

    def _to_entity(self, row: ConversationSession) -> Session:
        ctx = (row.context_jsonb or {})
        return Session(
            id=row.id,
            tenant_id=row.tenant_id,
            channel_id=row.channel_id,
            phone_number=row.phone_number,
            current_node_id=ctx.get("current_node_id"),
            vars=ctx.get("vars", {}),
            status=row.status,
            stage=row.conversation_stage,
            expires_at=row.expires_at,
            last_activity=row.last_activity,
            context=ctx,
        )

class ConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_config_map(self, tenant_id) -> Dict[str, Any]:
        # Simple key->value map from tenant_configurations
        from sqlalchemy import table, column, String as SAString, Integer as SAInteger
        from sqlalchemy import text as _text
        sql = _text(
            "SELECT config_key, config_value FROM tenant_configurations WHERE tenant_id=:t AND deleted_at IS NULL"
        )
        rows = (await self.db.execute(sql, {"t": tenant_id})).all()
        return {k: v for (k, v) in rows}
