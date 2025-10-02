# src/shared/database/uow.py
# Source: :contentReference[oaicite:0]{index=0}
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
import inspect
from typing import Awaitable, Callable, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared_.database.rls import (
    apply_rls_locals,
    tenant_context_from_ctxvars,
    verify_rls_context,
)
from src.shared_.database.types import TenantContext

# Support BOTH styles:
#  - Non-awaitable factories (e.g., async_sessionmaker(...) -> AsyncSession)
#  - Awaitable factories (e.g., async def get_session() -> AsyncSession)
SessionFactorySync = Callable[[], AsyncSession]
SessionFactoryAsync = Callable[[], Awaitable[AsyncSession]]
SessionFactory = Union[SessionFactorySync, SessionFactoryAsync]

class AsyncUoW(AbstractAsyncContextManager):
    """
    Minimal async Unit of Work.
    - Services coordinate multiple repo ops in a single transaction.
    - Repos do not commit/rollback (keeps SRP & DIP).
    - RLS GUCs are applied once per transaction on entry.
    """

    def __init__(
        self,
        session_factory: Callable[[], Awaitable[AsyncSession]],
        *,
        context: Optional[TenantContext] = None,
        require_tenant: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._ctx = context  # if None, will be resolved from ctxvars
        self._require_tenant = require_tenant
        self.session: Optional[AsyncSession] = None

    async def __aenter__(self) -> "AsyncUoW":
        # Create session and open a transaction; RLS GUCs are transaction-scoped (SET LOCAL).
        #self.session = await self._session_factory()
        # Create session (handle both awaitable and direct-return factories)
        maybe_session = self._session_factory()
        self.session = (
            await maybe_session  # type: ignore[assignment]
            if inspect.isawaitable(maybe_session)
            else maybe_session   # type: ignore[assignment]
        )

        await self.session.begin()

        # Resolve tenant context (explicit > ctxvars)
        ctx = self._ctx or tenant_context_from_ctxvars()
        if self._require_tenant and (ctx is None or not ctx.tenant_id):
            # Let your global exception middleware translate this to { code, message }.
            raise RuntimeError("Tenant context not set")

        if ctx and ctx.tenant_id:
            await apply_rls_locals(self.session, ctx)
            await verify_rls_context(self.session)
        return self

    async def commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            if self.session is not None:
                await self.session.close()

    def require_session(self) -> AsyncSession:
        if self.session is None:
            raise RuntimeError("UoW session not initialized")
        return self.session