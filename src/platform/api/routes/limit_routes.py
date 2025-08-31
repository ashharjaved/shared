from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy.ext.asyncio import AsyncSession

from ...application.services.rate_limit_service import RateLimitService, RateLimitedError
from ...infrastructure.cache.redis_client import RedisClient
from ..schemas import RateLimitCheckRequest, RateLimitDecisionResponse
from src.dependencies import get_db_session
from src.shared.error_codes import ERROR_CODES

router = APIRouter(prefix="/api/v1/platform/limits", tags=["platform:limits"])


async def _service(session: AsyncSession = Depends(get_db_session)) -> RateLimitService:
    redis = RedisClient()
    await redis.connect()
    return RateLimitService(session, redis)


def _tenant_id(request: Request) -> UUID:
    from uuid import UUID as _UUID
    claims = getattr(request.state, "user_claims", None)
    if not claims or not claims.get("tenant_id"):
        data = ERROR_CODES["unauthorized"]
        raise HTTPException(status_code=data["http"], detail={"code": "unauthorized", "message": data["message"]})
    return _UUID(claims["tenant_id"])


@router.get("/effective")
async def get_effective_policy(request: Request, svc: RateLimitService = Depends(_service)):
    tenant_id = _tenant_id(request)
    policy = await svc.effective_policy(tenant_id)
    if policy is None:
        return {"policy": None}
    return {"policy": policy.__dict__}


@router.post("/check", response_model=RateLimitDecisionResponse)
async def check_limit(payload: RateLimitCheckRequest, request: Request, svc: RateLimitService = Depends(_service)):
    tenant_id = _tenant_id(request)
    try:
        decision = await svc.check_and_consume(
            tenant_id,
            payload.endpoint,
            per_second=payload.per_second,
            enable_global=payload.enable_global,
            enable_monthly=payload.enable_monthly,
            monthly_quota=payload.monthly_quota,
        )
        return decision.__dict__
    except RateLimitedError as e:
        # Surface as 429 via shared exception handler (code=rate_limited)
        raise
