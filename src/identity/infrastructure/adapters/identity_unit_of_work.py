"""
Identity Unit of Work
Coordinates identity repositories within a transaction with RLS enforcement
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWork
from shared.infrastructure.database.rls import RLSManager
from shared.infrastructure.observability.logger import get_logger
from src.identity.infrastructure.persistence.repositories.organization_repository import (
    OrganizationRepository,
)
from src.identity.infrastructure.persistence.repositories.user_repository import (
    UserRepository,
)
from src.identity.infrastructure.persistence.repositories.role_repository import (
    RoleRepository,
)
from src.identity.infrastructure.persistence.repositories.refresh_token_repository import (
    RefreshTokenRepository,
)
from src.identity.infrastructure.persistence.repositories.audit_log_repository import (
    AuditLogRepository,
)
from src.identity.infrastructure.persistence.repositories.api_key_repository import (
    ApiKeyRepository,
)

logger = get_logger(__name__)


class IdentityUnitOfWork(SQLAlchemyUnitOfWork):
    """
    Unit of Work for Identity module.
    
    Provides transactional access to all identity repositories with:
    - RLS context enforcement
    - Domain event collection and outbox publishing
    - Idempotency support
    
    Usage:
        async with uow:
            # Set tenant context (CRITICAL for RLS)
            uow.set_tenant_context(org_id, user_id, roles)
            
            # Perform operations
            user = await uow.users.get_by_id(user_id)
            await uow.commit()
    """
    
    def __init__(self, session_factory) -> None:
        super().__init__(session_factory)
        self._organizations: Optional[OrganizationRepository] = None
        self._users: Optional[UserRepository] = None
        self._roles: Optional[RoleRepository] = None
        self._refresh_tokens: Optional[RefreshTokenRepository] = None
        self._audit_logs: Optional[AuditLogRepository] = None
        self._api_keys: Optional[ApiKeyRepository] = None
        
        # RLS context tracking
        self._organization_id: Optional[UUID] = None
        self._user_id: Optional[UUID] = None
        self._roles_list: Optional[list[str]] = None
        self._rls_context_set: bool = False
        
        # Domain event tracking
        self._tracked_aggregates: list = []
    
    async def __aenter__(self) -> "IdentityUnitOfWork":
        """
        Enter UoW context and optionally set RLS.
        
        Returns:
            Self (UoW instance)
        """
        await super().__aenter__()
        
        # If RLS context was provided via set_tenant_context(), apply it now
        if self._organization_id and not self._rls_context_set:
            await self._apply_rls_context()
        
        return self
    
    def set_tenant_context(
        self,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        roles: Optional[list[str]] = None,
    ) -> None:
        """
        Set tenant context for RLS enforcement.
        
        CRITICAL: Must be called before any tenant-scoped operations.
        
        Args:
            organization_id: Organization UUID for RLS filtering
            user_id: User UUID (for audit trail)
            roles: List of role names (for permission checks)
            
        Example:
            async with uow:
                uow.set_tenant_context(org_id, user_id, ["TenantAdmin"])
                user = await uow.users.get_by_id(user_id)
        """
        self._organization_id = organization_id
        self._user_id = user_id
        self._roles_list = roles or []
        
        logger.debug(
            "Tenant context set for UoW",
            extra={
                "organization_id": str(organization_id),
                "user_id": str(user_id) if user_id else None,
                "roles": roles,
            },
        )
    
    async def _apply_rls_context(self) -> None:
        """
        Apply RLS context to the database session.
        
        Sets PostgreSQL GUC variables for Row-Level Security policies.
        """
        if not self._organization_id:
            logger.warning(
                "RLS context not set - queries may fail on RLS-protected tables",
                extra={"action": "call_set_tenant_context"},
            )
            return
        
        await RLSManager.set_tenant_context(
            session=self.session,
            organization_id=self._organization_id,
            user_id=self._user_id,
            roles=self._roles_list,
        )
        
        self._rls_context_set = True
        
        logger.info(
            "RLS context applied to session",
            extra={
                "organization_id": str(self._organization_id),
                "user_id": str(self._user_id) if self._user_id else None,
            },
        )
    
    def track_aggregate(self, aggregate) -> None:
        """
        Track an aggregate for domain event collection.
        
        Call this after any aggregate root mutation to ensure events are published.
        
        Args:
            aggregate: Aggregate root instance with domain events
        """
        if hasattr(aggregate, 'domain_events') and aggregate not in self._tracked_aggregates:
            self._tracked_aggregates.append(aggregate)
    
    async def commit(self) -> None:
        """
        Commit transaction with domain event publishing.
        
        Collects domain events from tracked aggregates and writes to outbox
        before committing the transaction.
        
        Raises:
            Exception: If commit fails (automatically rolls back)
        """
        try:
            # 1. Collect domain events from tracked aggregates
            events = self._collect_domain_events()
            
            # 2. Write events to outbox (transactionally)
            if events:
                await self._publish_to_outbox(events)
            
            # 3. Commit the transaction
            await super().commit()
            
            logger.debug(
                "Transaction committed successfully",
                extra={
                    "event_count": len(events),
                    "organization_id": str(self._organization_id) if self._organization_id else None,
                },
            )
            
        except Exception as e:
            logger.error(
                "Failed to commit transaction",
                extra={
                    "error": str(e),
                    "organization_id": str(self._organization_id) if self._organization_id else None,
                },
            )
            raise
    
    def _collect_domain_events(self) -> list:
        """
        Collect domain events from all tracked aggregates.
        
        Returns:
            List of domain events
        """
        events = []
        
        for aggregate in self._tracked_aggregates:
            if hasattr(aggregate, 'domain_events'):
                aggregate_events = aggregate.domain_events
                events.extend(aggregate_events)
                
                # Clear events from aggregate after collection
                if hasattr(aggregate, 'clear_events'):
                    aggregate.clear_events()
        
        logger.debug(
            f"Collected {len(events)} domain events from {len(self._tracked_aggregates)} aggregates"
        )
        
        return events
    
    async def _publish_to_outbox(self, events: list) -> None:
        """
        Write domain events to outbox table for eventual publishing.
        
        Args:
            events: List of domain events to publish
        """
        from shared.infrastructure.messaging.outbox_pattern import OutboxPublisher
        from datetime import datetime
        from uuid import uuid4
        
        publisher = OutboxPublisher(self.session)
        
        for event in events:
            # Determine aggregate info from event
            aggregate_id = getattr(event, 'organization_id', None) or getattr(event, 'user_id', None)
            aggregate_type = event.__class__.__module__.split('.')[2]  # Extract from module path
            
            # Serialize event data
            event_data = {
                key: str(value) if isinstance(value, UUID) else value
                for key, value in event.__dict__.items()
                if not key.startswith('_')
            }
            
            await publisher.add_event(
                aggregate_id=aggregate_id or uuid4(),
                aggregate_type=aggregate_type,
                event_type=event.__class__.__name__,
                event_data=event_data,
                occurred_at=getattr(event, 'occurred_at', datetime.utcnow()),
            )
        
        logger.info(
            f"Published {len(events)} events to outbox",
            extra={"event_types": [e.__class__.__name__ for e in events]},
        )
    
    # Repository properties
    @property
    def organizations(self) -> OrganizationRepository:
        """Get organization repository"""
        if self._organizations is None:
            self._organizations = OrganizationRepository(self.session)
        return self._organizations
    
    @property
    def users(self) -> UserRepository:
        """Get user repository"""
        if self._users is None:
            self._users = UserRepository(self.session)
        return self._users
    
    @property
    def roles(self) -> RoleRepository:
        """Get role repository"""
        if self._roles is None:
            self._roles = RoleRepository(self.session)
        return self._roles
    
    @property
    def refresh_tokens(self) -> RefreshTokenRepository:
        """Get refresh token repository"""
        if self._refresh_tokens is None:
            self._refresh_tokens = RefreshTokenRepository(self.session)
        return self._refresh_tokens
    
    @property
    def audit_logs(self) -> AuditLogRepository:
        """Get audit log repository"""
        if self._audit_logs is None:
            self._audit_logs = AuditLogRepository(self.session)
        return self._audit_logs
    
    @property
    def api_keys(self) -> ApiKeyRepository:
        """Get API key repository"""
        if self._api_keys is None:
            self._api_keys = ApiKeyRepository(self.session)
        return self._api_keys