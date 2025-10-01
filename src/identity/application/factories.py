# src/identity/application/factories.py
# Source: :contentReference[oaicite:2]{index=2}
from __future__ import annotations

from typing import Callable, Protocol, Any, TypeVar, Generic, Optional
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# UoW
from src.shared.database.types import TenantContext
from src.identity.infrastructure.repositories.user_repository_impl import UserRepositoryImpl
from src.shared.database.uow import AsyncUoW

# Services (ports / apps)
from src.identity.application.services.auth_service import AuthService
from src.identity.application.services.tenant_service import TenantService
from src.identity.application.services.user_service import UserService  # if you expose it

# Repositories (impls)
from src.identity.infrastructure.repositories.tenant_repository_impl import (
    TenantRepositoryImpl,
)

# Security ports (DIP)
from src.shared.security.passwords.ports import PasswordHasherPort
from src.shared.security.tokens.ports import TokenServicePort


# ---------- Provider Protocols (DIP) -----------------------------------------

class Provider(Protocol):
    def __call__(self) -> Any: ...

T = TypeVar("T", covariant=True)

class TypedProvider(Protocol, Generic[T]):
    def __call__(self) -> T: ...


# ---------- UoW factory (shared) ---------------------------------------------

def make_uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., AsyncUoW]:
    """
    Returns a factory function that produces a new AsyncUoW.
    Supports `require_tenant` and explicit `context=TenantContext(...)` overrides
    so services can impersonate a target tenant inside the tx.
    """
    async def _open_session() -> AsyncSession:
        return session_factory()

    def _uow_factory(
        *,
        require_tenant: bool = True,
        context: Optional[TenantContext] = None,
    ) -> AsyncUoW:
        return AsyncUoW(
            session_factory=_open_session,
            require_tenant=require_tenant,
            context=context,
        )

    return _uow_factory


# ---------- AuthService -------------------------------------------------------

def make_auth_service(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    password_hasher: PasswordHasherPort,
    token_service: TokenServicePort,
) -> AuthService:
    """
    Compose AuthService with UoW + security ports (hasher, token_service).
    """
    uow_factory = make_uow_factory(session_factory)
    return AuthService(
        uow_factory=uow_factory,
        password_hasher=password_hasher,
        token_service=token_service,
    )

# ---------- UserService (optional, if you use it directly) --------------------

def make_user_service(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    password_hasher: PasswordHasherPort,
) -> UserService:
    """
    Compose UserService with: UoW + repo factories + password hasher port.
    Repositories never commit; UoW owns the tx boundary per operation.
    """
    uow_factory = make_uow_factory(session_factory)

    def user_repo_factory(session: AsyncSession) -> UserRepositoryImpl:
        return UserRepositoryImpl(session=session)

    def tenant_repo_factory(session: AsyncSession) -> TenantRepositoryImpl:
        return TenantRepositoryImpl(session=session)

    return UserService(
        uow_factory=uow_factory,
        user_repo_factory=user_repo_factory,
        tenant_repo_factory=tenant_repo_factory,
        password_hasher=password_hasher,
    )


# ---------- TenantService -----------------------------------------------------

def make_tenant_service(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    user_service: UserService,
) -> TenantService:
    """
    Compose TenantService with UoW + repository factory + a ready UserService.

    - Keeps DIP: service depends on ports/factories, not concrete session.
    - Repository is bound to the live session provided by the UoW.
    """
    uow_factory = make_uow_factory(session_factory)

    def tenant_repo_factory(session: AsyncSession) -> TenantRepositoryImpl:
        return TenantRepositoryImpl(session=session)

    return TenantService(
        uow_factory=uow_factory,
        tenant_repo_factory=tenant_repo_factory,
        user_service=user_service,
    )