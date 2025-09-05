# Begin: src/conversation/infrastructure/repositories/flow_repository_impl.py ***
from __future__ import annotations

import logging
from typing import Optional, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, update, text

from ...domain.entities import MenuFlow
from ...domain.errors import FlowNotFoundError
from ...domain.value_objects import MenuDefinition
from ...domain.repositories.flow_repository import FlowRepository
from ..models import MenuFlowORM
from ..rls import with_rls

from ...infrastructure.mappers import (
    menu_flow_to_domain,
    menu_flow_to_orm_new,
    menu_flow_update_orm,
    session_to_domain,
    session_to_orm_new,
    session_update_orm,
)


logger = logging.getLogger(__name__)


class PostgresFlowRepository(FlowRepository):
    """
    Postgres-backed FlowRepository.
    - Requires tenant_id at construction to enforce RLS via with_rls().
    - Maps ORM <-> Domain.
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        roles_csv: Optional[str] = None,
    ) -> None:
        self._sf = session_factory
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._roles_csv = roles_csv

    # ------------- mapping helpers -------------
    @staticmethod
    def _to_domain(row: MenuFlowORM) -> MenuFlow:
        return menu_flow_to_domain(row)

    # ------------- queries -------------
    async def get_default(self, *, industry_type: Optional[str] = None) -> MenuFlow:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            stmt = (
                select(MenuFlowORM)
                .where(MenuFlowORM.tenant_id == self._tenant_id)
                .where(MenuFlowORM.is_active.is_(True))
                .where(MenuFlowORM.is_default.is_(True))
            )
            if industry_type:
                stmt = stmt.where(MenuFlowORM.industry_type == industry_type)
            stmt = stmt.order_by(MenuFlowORM.version.desc())
            row = (await s.execute(stmt)).scalars().first()
            if not row:
                raise FlowNotFoundError("default flow not found")
            return self._to_domain(row)

    async def get_by_id(self, flow_id: UUID) -> MenuFlow:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            stmt = select(MenuFlowORM).where(MenuFlowORM.id == flow_id)
            row = (await s.execute(stmt)).scalars().first()
            if not row:
                raise FlowNotFoundError("flow not found")
            return self._to_domain(row)

    async def get_by_name(self, *, name: str, version: Optional[int] = None) -> MenuFlow:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            stmt = select(MenuFlowORM).where(
                MenuFlowORM.tenant_id == self._tenant_id, MenuFlowORM.name == name
            )
            if version is not None:
                stmt = stmt.where(MenuFlowORM.version == version)
            else:
                stmt = stmt.order_by(MenuFlowORM.version.desc())
            row = (await s.execute(stmt)).scalars().first()
            if not row:
                raise FlowNotFoundError("flow not found")
            return self._to_domain(row)

    async def list(
        self,
        *,
        active: Optional[bool] = None,
        name: Optional[str] = None,
        industry_type: Optional[str] = None,
    ) -> list[MenuFlow]:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            stmt = select(MenuFlowORM).where(MenuFlowORM.tenant_id == self._tenant_id)
            if active is not None:
                stmt = stmt.where(MenuFlowORM.is_active.is_(active))
            if name:
                stmt = stmt.where(MenuFlowORM.name == name)
            if industry_type:
                stmt = stmt.where(MenuFlowORM.industry_type == industry_type)
            stmt = stmt.order_by(MenuFlowORM.name.asc(), MenuFlowORM.version.desc())
            rows: Sequence[MenuFlowORM] = (await s.execute(stmt)).scalars().all()
            return [self._to_domain(r) for r in rows]

    async def create(self, flow: MenuFlow) -> MenuFlow:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            orm=menu_flow_to_orm_new(flow)
            s.add(orm)
            await s.flush()

            if flow.is_default:
                # enforce single default in (tenant, industry_type)
                await s.execute(
                    text(
                        """
                        UPDATE menu_flows
                           SET is_default = CASE WHEN id = :id THEN TRUE ELSE FALSE END,
                               updated_at = now()
                         WHERE tenant_id = :tid
                           AND industry_type = :ind
                        """
                    ),
                    {"id": orm.id, "tid": str(self._tenant_id), "ind": flow.industry_type},
                )
            await s.commit()
            return self._to_domain(orm)

    async def update(self, flow: MenuFlow) -> MenuFlow:
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            # Update mutable fields
            stmt = (
                update(MenuFlowORM)
                .where(MenuFlowORM.id == flow.id)
                .values(
                    name=flow.name,
                    industry_type=flow.industry_type,
                    version=flow.version,
                    is_active=flow.is_active,
                    is_default=flow.is_default,
                    definition_jsonb=flow.definition.to_json(),
                    updated_at=sa.text("now()"),
                )
                .returning(MenuFlowORM)
            )
            row = (await s.execute(stmt)).scalars().first()
            if not row:
                raise FlowNotFoundError("flow not found for update")

            if flow.is_default:
                await s.execute(
                    text(
                        """
                        UPDATE menu_flows
                           SET is_default = CASE WHEN id = :id THEN TRUE ELSE FALSE END,
                               updated_at = now()
                         WHERE tenant_id = :tid
                           AND industry_type = :ind
                        """
                    ),
                    {"id": row.id, "tid": str(self._tenant_id), "ind": flow.industry_type},
                )
            await s.commit()
            return self._to_domain(row)

    async def toggle_default(self, flow_id: UUID, *, industry_type: Optional[str]) -> None:
        # Fetch to know its industry_type if not provided
        async with self._sf() as s, with_rls(s, tenant_id=self._tenant_id, user_id=self._user_id, roles_csv=self._roles_csv):
            if industry_type is None:
                cur = await s.execute(select(MenuFlowORM.industry_type).where(MenuFlowORM.id == flow_id))
                ind = cur.scalar_one_or_none()
                if not ind:
                    raise FlowNotFoundError("flow not found for toggle_default")
                industry_type = ind

            await s.execute(
                text(
                    """
                    UPDATE menu_flows
                       SET is_default = (id = :id),
                           updated_at = now()
                     WHERE tenant_id = :tid
                       AND industry_type = :ind
                    """
                ),
                {"id": flow_id, "tid": str(self._tenant_id), "ind": industry_type},
            )
            await s.commit()
# End: src/conversation/infrastructure/repositories/flow_repository_impl.py ***
