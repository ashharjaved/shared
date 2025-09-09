# src/identity/infrastructure/repositories/subscription_repository_impl.py

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.domain.entities.subscription import TenantPlanSubscription
from src.identity.domain.repositories.subscriptions import SubscriptionRepository
from src.identity.domain.types import SubscriptionId, TenantId, PlanId
from src.identity.domain.value_objects import SubscriptionStatus
from src.shared.errors import DomainError, ConflictError, NotFoundError, ValidationError

from identity.infrastructure.models.subscription_model import SubscriptionModel
from src.shared.database.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SubscriptionRepositoryImpl(
    BaseRepository[SubscriptionModel, TenantPlanSubscription, SubscriptionId],
    SubscriptionRepository,
):
    """Subscription repository with strict RLS enforcement and domain mapping."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SubscriptionModel)

    # ---------- Queries ----------

    async def get_by_id(self, subscription_id: SubscriptionId) -> Optional[TenantPlanSubscription]:
        # BaseRepository.get_by_id() already verifies RLS and loads by PK
        return await super().get_by_id(subscription_id)

    async def get_active_by_tenant(self, tenant_id: TenantId) -> Optional[TenantPlanSubscription]:
        try:
            stmt = (
                select(SubscriptionModel)
                .where(SubscriptionModel.tenant_id == tenant_id)
                .where(SubscriptionModel.status == SubscriptionStatus.ACTIVE)
                .order_by(SubscriptionModel.start_at.desc())
                .limit(1)
            )
            res = await self._session.execute(stmt)
            model = res.scalar_one_or_none()
            return self._to_domain(model) if model else None
        except Exception as e:
            logger.error("subscriptions.get_active_by_tenant failed",
                         extra={"tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    async def list_by_tenant(self, tenant_id: TenantId) -> List[TenantPlanSubscription]:
        try:
            stmt = (
                select(SubscriptionModel)
                .where(SubscriptionModel.tenant_id == tenant_id)
                .order_by(SubscriptionModel.start_at.desc())
            )
            res = await self._session.execute(stmt)
            return [self._to_domain(m) for m in res.scalars().all()]
        except Exception as e:
            logger.error("subscriptions.list_by_tenant failed",
                         extra={"tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    async def list_by_plan(self, plan_id: PlanId) -> List[TenantPlanSubscription]:
        try:
            stmt = select(SubscriptionModel).where(SubscriptionModel.plan_id == plan_id)
            res = await self._session.execute(stmt)
            return [self._to_domain(m) for m in res.scalars().all()]
        except Exception as e:
            logger.error("subscriptions.list_by_plan failed",
                         extra={"plan_id": str(plan_id), "error": str(e)})
            raise self._map_error(e)

    async def list_expiring_soon(self, days_ahead: int = 7) -> List[TenantPlanSubscription]:
        """
        Subscriptions whose end_at is within [now, now+days] and still ACTIVE.
        """
        try:
            now = func.now()
            horizon = func.now() + timedelta(days=days_ahead)
            stmt = (
                select(SubscriptionModel)
                .where(SubscriptionModel.status == SubscriptionStatus.ACTIVE)
                .where(SubscriptionModel.end_at >= now)
                .where(SubscriptionModel.end_at <= horizon)
                .order_by(SubscriptionModel.end_at.asc())
            )
            res = await self._session.execute(stmt)
            return [self._to_domain(m) for m in res.scalars().all()]
        except Exception as e:
            logger.error("subscriptions.list_expiring_soon failed",
                         extra={"days_ahead": days_ahead, "error": str(e)})
            raise self._map_error(e)

    async def list_past_due(self, as_of: Optional[datetime] = None) -> List[TenantPlanSubscription]:
        """
        Subscriptions that should have ended but are still ACTIVE.
        """
        try:
            cutoff = as_of if as_of is not None else func.now()
            stmt = (
                select(SubscriptionModel)
                .where(SubscriptionModel.status == SubscriptionStatus.ACTIVE)
                .where(SubscriptionModel.end_at < cutoff)
                .order_by(SubscriptionModel.end_at.asc())
            )
            res = await self._session.execute(stmt)
            return [self._to_domain(m) for m in res.scalars().all()]
        except Exception as e:
            logger.error("subscriptions.list_past_due failed",
                         extra={"as_of": as_of.isoformat() if isinstance(as_of, datetime) else None,
                                "error": str(e)})
            raise self._map_error(e)

    async def has_active_subscription(self, tenant_id: TenantId) -> bool:
        try:
            stmt = (
                select(func.count(SubscriptionModel.id))
                .where(SubscriptionModel.tenant_id == tenant_id)
                .where(SubscriptionModel.status == SubscriptionStatus.ACTIVE)
            )
            res = await self._session.execute(stmt)
            return (res.scalar() or 0) > 0
        except Exception as e:
            logger.error("subscriptions.has_active_subscription failed",
                         extra={"tenant_id": str(tenant_id), "error": str(e)})
            raise self._map_error(e)

    # ---------- Mutations ----------

    async def create(self, subscription: TenantPlanSubscription) -> TenantPlanSubscription:
        """
        Delegates to BaseRepository.create(); relies on DB constraints:
        - uq_tenant_subscription_status ensures 1 ACTIVE per tenant.
        - ck_subscription_time_order enforces end_at > start_at.
        """
        # Basic guards before hitting DB constraints
        if subscription.end_at <= subscription.start_at:
            raise ValidationError("end_at must be greater than start_at")
        return await super().create(subscription)

    async def update(self, subscription: TenantPlanSubscription) -> TenantPlanSubscription:
        if subscription.end_at <= subscription.start_at:
            raise ValidationError("end_at must be greater than start_at")
        return await super().update(subscription)

    # ---------- Mapping ----------

    def _to_domain(self, model: Optional[SubscriptionModel]) -> Optional[TenantPlanSubscription]:
        if model is None:
            return None
        return TenantPlanSubscription(
            id=model.id,
            tenant_id=model.tenant_id,
            plan_id=model.plan_id,
            status=model.status,
            start_at=model.start_at,
            end_at=model.end_at,
            meta=dict(model.meta or {}),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_orm(self, entity: TenantPlanSubscription) -> SubscriptionModel:
        m = SubscriptionModel()
        m.id = getattr(entity, "id", None)
        m.tenant_id = entity.tenant_id
        m.plan_id = entity.plan_id
        m.status = entity.status
        m.start_at = entity.start_at
        m.end_at = entity.end_at
        m.meta = dict(entity.meta or {})
        # created_at/updated_at are DB-managed
        return m