# # /src/shared/http/dependencies.py
# """
# FastAPI dependencies for accessing request-scoped context.

# - request_context(): returns dict with request_id, tenant_id, user_id, roles
# - require_tenant(): raises if tenant_id missing (use inside tenant-protected routes)
# """

# from __future__ import annotations
# import datetime
# import json
# from typing import Awaitable, Callable, Dict, Optional, Set, Union
# from dataclasses import dataclass
# from uuid import UUID
# import inspect
# from fastapi import Depends, Header, HTTPException, Request, status
# from sqlalchemy import select, text
# from sqlalchemy.ext.asyncio import AsyncSession
# from typing import Callable, Optional, Dict, Tuple,Awaitable
# from src.shared.utils.strings import normalize_roles
# from src.shared.http.models import CurrentUser
# from src.shared.exceptions import RateLimitedError
# from src.messaging.infrastructure.models.channel_model import ChannelModel
# from src.shared.error_codes import ERROR_CODES
# from src.identity.domain.services.rbac_policy import is_at_least
# from src.identity.domain.value_objects.role import Role
# from src.shared.errors import ERROR_CODES as ENUM_ERROR_MAP, ErrorCode  # enum-based map
# from src.shared.database.deps import get_tenant_scoped_db
# from ..utils import tenant_ctxvars as ctxvars
# from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
# from redis.asyncio import Redis

# def _http(code: ErrorCode) -> int:
#     # enum-keyed map returns {"http": int, "code": str}
#     return int(ENUM_ERROR_MAP[code]["http"])

# def _payload(code: ErrorCode, message: str) -> Dict[str, str]:
#     return {"code": code.value, "message": message}

# def request_context() -> Dict[str, object]:
#     """Expose request-scoped context to route handlers."""
#     return ctxvars.get_request_context()

# @dataclass(frozen=True)
# class TenantContext:
#     tenant_id: str
#     user_id: str | None = None
#     roles: Union[str, list[str], None] = None

# def get_tenant_ctx(
#     request: Request,
#     x_active_tenant: str | None = Header(default=None, alias="X-Active-Tenant"),
# ) -> TenantContext:
#     """
#     Minimal example:
#     - Read tenant from header (or from JWT claims on request.state / middleware).
#     - Populate roles/user_id as available.
#     """
#     # In your real app, prefer pulling from verified JWT on request.state
#     tenant_id = x_active_tenant or ctxvars.get_tenant_id() or getattr(request.state, "tenant_id", None)
#     if not tenant_id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail={"code": "forbidden", "message": "Active tenant not set"}
#         )

#     user_id = ctxvars.get_user_id() or getattr(request.state, "user_id", None)
#     roles   = ctxvars.get_roles() or None
#     return TenantContext(tenant_id=tenant_id, user_id=user_id, roles=roles)

# async def user_repo(session: AsyncSession = Depends(get_tenant_scoped_db)):
#     from src.identity.infrastructure.repositories.user_repository_impl import (UserRepositoryImpl,)  # type: ignore
#     return UserRepositoryImpl(session)

# def tenant_repo(session: AsyncSession = Depends(get_tenant_scoped_db)):
#     from src.identity.infrastructure.repositories.tenant_repository_impl import TenantRepositoryImpl  # type: ignore
#     return TenantRepositoryImpl(session)

# def require_role(required_role: Role):
#     def _enforce(current_user = Depends(get_current_user)):
#         if not is_at_least(current_user.roles, required_role):            
#             raise HTTPException(
#                 status_code=_http(ErrorCode.FORBIDDEN),
#                 detail=_payload(ErrorCode.FORBIDDEN, "You are not allowed to perform this action."),
#             )
#         return current_user
#     return _enforce

# # --- Current user & role guard ---

# async def get_current_user(
#     request: Request,
#     user_repo=Depends(user_repo),
# ) -> CurrentUser:
#     """
#     Resolve the current authenticated user and return a stable DTO with roles.
#     Source priority:
#       1) request.state.user_claims (full JWT)
#       2) request.state.<user_id/email/tenant_id/roles>
#       3) DB fallback for missing pieces
#     """
#     claims = getattr(request.state, "user_claims", None)

#     # if claims:
#     #     # If for any reason ctxvars were not set in middleware, set them here defensively
#     #     tenant_id = claims.get("tid") or claims.get("tenant_id")
#     #     user_id   = claims.get("sub") or claims.get("uid")
#     #     roles     = normalize_roles(claims.get("roles") or claims.get("role"))
#     #     if not ctxvars.snapshot().get("tenant_id") and tenant_id:
#     #         ctxvars.set_all(
#     #             tenant_id=tenant_id,
#     #             user_id=user_id,
#     #             roles=[roles] if roles else [],
#     #             request_id=getattr(request.state, "request_id", None),
#     #         )

#     user_id: Optional[str] = None
#     email: Optional[str] = None
#     tenant_id: Optional[str] = getattr(request.state, "tenant_id", None)
#     roles: Set[str] = set()

#     if isinstance(claims, dict):
#         user_id = claims.get("sub") or claims.get("uid")
#         email = claims.get("email") or getattr(request.state, "email", None)
#         tenant_id = claims.get("tenant") or claims.get("tenant_id") or tenant_id
#         roles = normalize_roles(claims.get("roles") or claims.get("role"))
#     else:
#         user_id = getattr(request.state, "user_id", None)
#         email = getattr(request.state, "email", None)
#         roles = normalize_roles(getattr(request.state, "roles", None))

#     if not user_id:
#         data = ERROR_CODES.get("invalid_credentials", {"http": 401, "message": "Invalid credentials."})
#         raise HTTPException(
#             status_code=data["http"],
#             detail={"code": "invalid_credentials", "message": data["message"]},
#         )

#     # Fetch from repo only if we still miss email/roles
#     if email is None or not roles:
#         finder = getattr(user_repo, "get_by_id", None)
#         if not callable(finder):
#             data = ERROR_CODES.get("internal_error", {"http": 500, "message": "Internal error"})
#             raise HTTPException(
#                 status_code=data["http"],
#                 detail={"code": "internal_error", "message": data["message"]},
#             )
#         user = await finder(user_id) if inspect.iscoroutinefunction(finder) else finder(user_id)
#         if not user:
#             data = ERROR_CODES.get("user_not_found", {"http": 404, "message": "User not found"})
#             raise HTTPException(
#                 status_code=data["http"],
#                 detail={"code": "user_not_found", "message": data["message"]},
#             )
#         # Fill missing pieces from entity (defensive across shapes)
#         if email is None:
#             email = getattr(user, "email", None) or "unknown@example.com"
#         if not roles:
#             raw_roles = (
#                 getattr(user, "roles", None) or
#                 getattr(user, "role", None) or
#                 getattr(user, "roles_csv", None)
#             )
#             roles = normalize_roles(raw_roles)

#     # Make DTO available to downstream if you like
#     dto = CurrentUser(id=str(user_id), email=email or "unknown@example.com", tenant_id=tenant_id, roles=roles)
#     setattr(request.state, "current_user", dto)
#     return dto

# def get_channel_limits_cb(
#     tenant_id:Optional[UUID]=None,

#     *,
#     session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
#     redis: Optional["Redis"] = None,
#     ttl_seconds: int = 60,
# ) -> Callable[[UUID],"Awaitable[Tuple[Optional[int], Optional[int]]]"]:
#     """
#     Returns an async closure: (channel_id) -> await (per_second_limit, monthly_limit)
#     - Runs under Postgres RLS for the given tenant_id.
#     - Reads from whatsapp_channels (nullable columns = “no limit” -> return None).
#     - Memoizes in Redis for ttl_seconds to avoid hot-loop queries.
#     """

#     if session_factory is None:
#         # lazy import to avoid cycles; must return async_sessionmaker
#         from src.shared.database import get_session_factory  # adjust path to your app
#         session_factory = get_session_factory()

#     # NOTE: Do NOT try to get a redis tenant here if you only have an async factory like `async def get_redis()`.
#     # Expect the caller to inject an already-instantiated async Redis tenant (redis.asyncio.Redis).
#     r = redis  # may be None (caching optional)

#     async def _cb(channel_id: UUID) -> Tuple[Optional[int], Optional[int]]:
#         cache_key = f"chlimits:{tenant_id}:{channel_id}"

#         # 1) Redis memo (optional)
#         if r is not None:
#             cached = await r.get(cache_key)  # type: ignore[attr-defined]
#             if cached:
#                 try:
#                     # redis returns bytes; decode safely
#                     if isinstance(cached, (bytes, bytearray)):
#                         cached = cached.decode("utf-8")
#                     per_sec, monthly = json.loads(cached)
#                     return (
#                         int(per_sec) if per_sec is not None else None,
#                         int(monthly) if monthly is not None else None,
#                     )
#                 except Exception:
#                     # fall through to DB
#                     pass

#         # 2) DB lookup under RLS
#         assert session_factory is not None
#         async with session_factory() as session:
#             # enforce tenant scoping for RLS (session-local)
#             await session.execute(
#                 text("SELECT set_config('app.jwt_tenant', :tid, true)"),
#                 {"tid": str(tenant_id)},
#             )

#             result = await session.execute(
#                 select(
#                     ChannelModel.rate_limit_per_second,
#                     ChannelModel.monthly_message_limit,
#                 ).where(ChannelModel.id == channel_id)
#             )
#             row = result.first()

#             if not row:
#                 per_sec = None
#                 monthly = None
#             else:
#                 per_sec = int(row[0]) if row[0] is not None else None
#                 monthly = int(row[1]) if row[1] is not None else None

#         # 3) cache briefly
#         if r is not None:
#             try:
#                 await r.set(cache_key, json.dumps([per_sec, monthly]), ex=ttl_seconds)  # type: ignore[attr-defined]
#             except Exception:
#                 pass  # cache failures should not break path

#         return per_sec, monthly
#     return _cb

# async def _get_channel_limits_once(
#     *,
#     tenant_id: UUID,
#     channel_id: UUID,
#     session_factory: async_sessionmaker[AsyncSession],
#     redis: Optional["Redis"]=None,
#     ttl_seconds: int,
# ) -> Tuple[Optional[int], Optional[int]]:
#     """
#     (per_second_limit, monthly_limit) lookup with optional Redis memo and RLS-safe DB query.
#     """
#     cache_key = f"chlimits:{tenant_id}:{channel_id}"

#     # 1) cache
#     if redis is not None:
#         cached = await redis.get(cache_key)  # type: ignore[attr-defined]
#         if cached:
#             try:
#                 if isinstance(cached, (bytes, bytearray)):
#                     cached = cached.decode("utf-8")
#                 per_sec, monthly = json.loads(cached)
#                 return (
#                     int(per_sec) if per_sec is not None else None,
#                     int(monthly) if monthly is not None else None,
#                 )
#             except Exception:
#                 pass  # corrupt cache -> fall through

#     # 2) DB (RLS)
#     async with session_factory() as session:
#         await session.execute(
#             text("SELECT set_config('app.jwt_tenant', :tid, true)"),
#             {"tid": str(tenant_id)},
#         )
#         from src.messaging.infrastructure.models.channel_model import ChannelModel
#             # local import to avoid cycles

#         result = await session.execute(
#             select(
#                 ChannelModel.rate_limit_per_second,
#                 ChannelModel.monthly_message_limit,
#             ).where(ChannelModel.id == channel_id)
#         )
#         row = result.first()

#     if not row:
#         per_sec = None
#         monthly = None
#     else:
#         per_sec = int(row[0]) if row[0] is not None else None
#         monthly = int(row[1]) if row[1] is not None else None

#     # 3) write cache (best-effort)
#     if redis is not None:
#         try:
#             await redis.set(cache_key, json.dumps([per_sec, monthly]), ex=ttl_seconds)  # type: ignore[attr-defined]
#         except Exception:
#             pass

#     return per_sec, monthly

# # async def enforce_channel_send_quota(*, tenant_id: UUID, channel_id: UUID,
# #         endpoint: str,
# #         session_factory: async_sessionmaker[AsyncSession],
# #         redis: Optional["Redis"] = None,
# #         # behavior knobs
# #         default_per_second: int = 20,          # used if DB per-second is NULL (i.e., "no limit") and you still want a guardrail
# #         honor_unlimited: bool = True,          # if True and DB returns NULL, treat as unlimited (skip per-sec enforcement)
# #         enable_global: bool = True,            # global per-sec guard
# #         cache_ttl_seconds: int = 60,           # cache for limits lookup
# #         ) -> RateLimitDecisionDTO:
# #         """
# #         One-shot: fetch channel caps (RLS-aware, Redis-memoized) and enforce them (Redis windows).
# #         Raises RateLimitedError on violation. On success returns DTO with remaining counters.
# #         """

# #         # ---------- 1) Fetch limits (cached -> DB w/ RLS) ----------
# #         per_sec, monthly_quota = await _get_channel_limits_once(
# #             tenant_id=tenant_id,
# #             channel_id=channel_id,
# #             session_factory=session_factory,
# #             redis=redis,
# #             ttl_seconds=cache_ttl_seconds,
# #         )

# #         # Decide effective per-second cap
# #         # - If DB value is None (unlimited):
# #         #   * honor_unlimited=True  -> skip the per-second window.
# #         #   * honor_unlimited=False -> use default_per_second as safety rail.
# #         enforce_per_sec = per_sec is not None or not honor_unlimited
# #         per_second_cap = per_sec if per_sec is not None else default_per_second

# #         # ---------- 2) Enforce using Redis windows ----------
# #         now = datetime.datetime.utcnow()
# #         epoch_sec = int(now.timestamp())

# #         remaining_in_window = per_second_cap if enforce_per_sec else 2**31 - 1  # big number if not enforcing
# #         remaining_monthly: Optional[int] = None

# #         if redis is not None:
# #             # tenant window
# #             if enforce_per_sec:
# #                 tenant_key = f"rl:tenant:{tenant_id}:{epoch_sec}"
# #                 tcount = await _incr_with_expire(redis, tenant_key, ttl_seconds=1)
# #                 if tcount > per_second_cap:
# #                     raise RateLimitedError("Too many requests for tenant window")
# #                 remaining_in_window = max(0, per_second_cap - tcount)

# #             # global window (simple mirror of per-second cap; customize if you want a different global cap)
# #             if enable_global:
# #                 global_key = f"rl:global:{epoch_sec}"
# #                 gcount = await _incr_with_expire(redis, global_key, ttl_seconds=1)
# #                 if enforce_per_sec and gcount > per_second_cap:
# #                     raise RateLimitedError("Too many requests (global window)")

# #             # monthly meter (only if a quota exists)
# #             if monthly_quota is not None:
# #                 mon_key = f"mon:{tenant_id}:{now.strftime('%Y%m')}"
# #                 # ~31 days; good-enough rolling month. For calendar-precise, set expire to 1st of next month.
# #                 used = await _incr_with_expire(redis, mon_key, ttl_seconds=31 * 24 * 3600)
# #                 remaining_monthly = max(0, monthly_quota - used)
# #                 if remaining_monthly <= 0:
# #                     raise RateLimitedError("Monthly quota exceeded")

# #         else:
# #             # If you ever run without Redis, you can either:
# #             # - allow all (no enforcement), or
# #             # - raise, or
# #             # - plug a local in-memory limiter (process-bound).
# #             # Here: allow but report "infinite" remaining if not enforcing.
# #             remaining_in_window = per_second_cap if enforce_per_sec else 2**31 - 1
# #             remaining_monthly = None if monthly_quota is None else monthly_quota  # unknown usage

# #         return RateLimitDecisionDTO(
# #             allowed=True,
# #             remaining_in_window=remaining_in_window,
# #             remaining_monthly=remaining_monthly,
# #         )

# async def _incr_with_expire(redis: Redis, key: str, *, ttl_seconds: int) -> int:
#         """
#         Atomic INCR with TTL. If key existed, TTL is not extended by default,
#         so we ensure a TTL on first increment.
#         """
#         pipe = redis.pipeline()
#         try:
#             pipe.incr(key)
#             pipe.expire(key, ttl_seconds, nx=True)
#             res = await pipe.execute()
#             return int(res[0])  # incr result
#         finally:
#             await pipe.close()