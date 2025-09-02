# --- APPEND-ONLY: Identity dependencies ---
import json
from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from uuid import UUID
from typing import Callable, Optional, Dict, Any, Tuple,Awaitable
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.messaging.infrastructure.models.channel_model import WhatsAppChannelModel
from src.shared.cache import get_redis
from .database import get_session, set_rls_guc, AsyncSession
import os

def _jwt_secret() -> str: return os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
def _jwt_alg() -> str: return os.getenv("JWT_ALG", "HS256")

async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session

def _extract_bearer(req: Request) -> str:
    auth = req.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"missing_token"})
    return auth.split(" ", 1)[1].strip()

async def get_current_user_claims(req: Request) -> Dict[str, Any]:
    token = _extract_bearer(req)
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_alg()])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"invalid_token"})
    # enrich with email when available (optional)
    return payload

async def get_tenant_id_from_jwt(claims=Depends(get_current_user_claims)) -> UUID:
    try:
        return UUID(claims["tenant_id"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code":"unauthorized","message":"invalid_token_claims"})

async def enforce_rls(session=Depends(get_db_session), tenant_id: Optional[UUID]=None, claims=Depends(get_current_user_claims)):
    # Set GUCs per RLS contract
    await set_rls_guc(session, tenant_id=str(tenant_id) if tenant_id else None,
                      user_id=str(claims.get("sub")) if claims else None,
                      roles=str(claims.get("role")) if claims else None)
    return True

def get_channel_limits_cb(
    tenant_id:Optional[UUID]=None,

    *,
    session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
    redis: Optional["Redis"] = None,
    ttl_seconds: int = 60,
) -> Callable[[UUID],"Awaitable[Tuple[Optional[int], Optional[int]]]"]:
    """
    Returns an async closure: (channel_id) -> await (per_second_limit, monthly_limit)
    - Runs under Postgres RLS for the given tenant_id.
    - Reads from whatsapp_channels (nullable columns = “no limit” -> return None).
    - Memoizes in Redis for ttl_seconds to avoid hot-loop queries.
    """

    if session_factory is None:
        # lazy import to avoid cycles; must return async_sessionmaker
        from src.shared.database import get_session  # adjust path to your app
        session_factory = get_session()

    # NOTE: Do NOT try to get a redis client here if you only have an async factory like `async def get_redis()`.
    # Expect the caller to inject an already-instantiated async Redis client (redis.asyncio.Redis).
    r = redis  # may be None (caching optional)

    async def _cb(channel_id: UUID) -> Tuple[Optional[int], Optional[int]]:
        cache_key = f"chlimits:{tenant_id}:{channel_id}"

        # 1) Redis memo (optional)
        if r is not None:
            cached = await r.get(cache_key)  # type: ignore[attr-defined]
            if cached:
                try:
                    # redis returns bytes; decode safely
                    if isinstance(cached, (bytes, bytearray)):
                        cached = cached.decode("utf-8")
                    per_sec, monthly = json.loads(cached)
                    return (
                        int(per_sec) if per_sec is not None else None,
                        int(monthly) if monthly is not None else None,
                    )
                except Exception:
                    # fall through to DB
                    pass

        # 2) DB lookup under RLS
        assert session_factory is not None
        async with session_factory() as session:
            # enforce tenant scoping for RLS (session-local)
            await session.execute(
                text("SELECT set_config('app.jwt_tenant', :tid, true)"),
                {"tid": str(tenant_id)},
            )

            result = await session.execute(
                select(
                    WhatsAppChannelModel.rate_limit_per_second,
                    WhatsAppChannelModel.monthly_message_limit,
                ).where(WhatsAppChannelModel.id == channel_id)
            )
            row = result.first()

            if not row:
                per_sec = None
                monthly = None
            else:
                per_sec = int(row[0]) if row[0] is not None else None
                monthly = int(row[1]) if row[1] is not None else None

        # 3) cache briefly
        if r is not None:
            try:
                await r.set(cache_key, json.dumps([per_sec, monthly]), ex=ttl_seconds)  # type: ignore[attr-defined]
            except Exception:
                pass  # cache failures should not break path

        return per_sec, monthly
    return _cb
#######################################################
    async def enforce_channel_send_quota(*, tenant_id: UUID, channel_id: UUID,
            endpoint: str,
            session_factory: async_sessionmaker[AsyncSession],
            redis: Optional["Redis"] = None,
            # behavior knobs
            default_per_second: int = 20,          # used if DB per-second is NULL (i.e., "no limit") and you still want a guardrail
            honor_unlimited: bool = True,          # if True and DB returns NULL, treat as unlimited (skip per-sec enforcement)
            enable_global: bool = True,            # global per-sec guard
            cache_ttl_seconds: int = 60,           # cache for limits lookup
            ) -> RateLimitDecisionDTO:
            """
            One-shot: fetch channel caps (RLS-aware, Redis-memoized) and enforce them (Redis windows).
            Raises RateLimitedError on violation. On success returns DTO with remaining counters.
            """

            # ---------- 1) Fetch limits (cached -> DB w/ RLS) ----------
            per_sec, monthly_quota = await _get_channel_limits_once(
                tenant_id=tenant_id,
                channel_id=channel_id,
                session_factory=session_factory,
                redis=redis,
                ttl_seconds=cache_ttl_seconds,
            )

            # Decide effective per-second cap
            # - If DB value is None (unlimited):
            #   * honor_unlimited=True  -> skip the per-second window.
            #   * honor_unlimited=False -> use default_per_second as safety rail.
            enforce_per_sec = per_sec is not None or not honor_unlimited
            per_second_cap = per_sec if per_sec is not None else default_per_second

            # ---------- 2) Enforce using Redis windows ----------
            now = dt.datetime.utcnow()
            epoch_sec = int(now.timestamp())

            remaining_in_window = per_second_cap if enforce_per_sec else 2**31 - 1  # big number if not enforcing
            remaining_monthly: Optional[int] = None

            if redis is not None:
                # tenant window
                if enforce_per_sec:
                    tenant_key = f"rl:tenant:{tenant_id}:{epoch_sec}"
                    tcount = await _incr_with_expire(redis, tenant_key, ttl_seconds=1)
                    if tcount > per_second_cap:
                        raise RateLimitedError("Too many requests for tenant window")
                    remaining_in_window = max(0, per_second_cap - tcount)

                # global window (simple mirror of per-second cap; customize if you want a different global cap)
                if enable_global:
                    global_key = f"rl:global:{epoch_sec}"
                    gcount = await _incr_with_expire(redis, global_key, ttl_seconds=1)
                    if enforce_per_sec and gcount > per_second_cap:
                        raise RateLimitedError("Too many requests (global window)")

                # monthly meter (only if a quota exists)
                if monthly_quota is not None:
                    mon_key = f"mon:{tenant_id}:{now.strftime('%Y%m')}"
                    # ~31 days; good-enough rolling month. For calendar-precise, set expire to 1st of next month.
                    used = await _incr_with_expire(redis, mon_key, ttl_seconds=31 * 24 * 3600)
                    remaining_monthly = max(0, monthly_quota - used)
                    if remaining_monthly <= 0:
                        raise RateLimitedError("Monthly quota exceeded")

            else:
                # If you ever run without Redis, you can either:
                # - allow all (no enforcement), or
                # - raise, or
                # - plug a local in-memory limiter (process-bound).
                # Here: allow but report "infinite" remaining if not enforcing.
                remaining_in_window = per_second_cap if enforce_per_sec else 2**31 - 1
                remaining_monthly = None if monthly_quota is None else monthly_quota  # unknown usage

            return RateLimitDecisionDTO(
                allowed=True,
                remaining_in_window=remaining_in_window,
                remaining_monthly=remaining_monthly,
            )
    
# ---------- Helpers ----------
    async def _get_channel_limits_once(
        *,
        tenant_id: UUID,
        channel_id: UUID,
        session_factory: async_sessionmaker[AsyncSession],
        redis: Optional["Redis"]=None,
        ttl_seconds: int,
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        (per_second_limit, monthly_limit) lookup with optional Redis memo and RLS-safe DB query.
        """
        cache_key = f"chlimits:{tenant_id}:{channel_id}"

        # 1) cache
        if redis is not None:
            cached = await redis.get(cache_key)  # type: ignore[attr-defined]
            if cached:
                try:
                    if isinstance(cached, (bytes, bytearray)):
                        cached = cached.decode("utf-8")
                    per_sec, monthly = json.loads(cached)
                    return (
                        int(per_sec) if per_sec is not None else None,
                        int(monthly) if monthly is not None else None,
                    )
                except Exception:
                    pass  # corrupt cache -> fall through

        # 2) DB (RLS)
        async with session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.jwt_tenant', :tid, true)"),
                {"tid": str(tenant_id)},
            )
            from src.messaging.infrastructure.models.channel_model import WhatsAppChannelModel
              # local import to avoid cycles

            result = await session.execute(
                select(
                    WhatsAppChannelModel.rate_limit_per_second,
                    WhatsAppChannelModel.monthly_message_limit,
                ).where(WhatsAppChannelModel.id == channel_id)
            )
            row = result.first()

        if not row:
            per_sec = None
            monthly = None
        else:
            per_sec = int(row[0]) if row[0] is not None else None
            monthly = int(row[1]) if row[1] is not None else None

        # 3) write cache (best-effort)
        if redis is not None:
            try:
                await redis.set(cache_key, json.dumps([per_sec, monthly]), ex=ttl_seconds)  # type: ignore[attr-defined]
            except Exception:
                pass

        return per_sec, monthly

    async def _incr_with_expire(redis: Redis, key: str, *, ttl_seconds: int) -> int:
        """
        Atomic INCR with TTL. If key existed, TTL is not extended by default,
        so we ensure a TTL on first increment.
        """
        pipe = redis.pipeline()
        try:
            pipe.incr(key)
            pipe.expire(key, ttl_seconds, nx=True)
            res = await pipe.execute()
            return int(res[0])  # incr result
        finally:
            await pipe.close()