"""
Idempotency Manager
Handles idempotency key checking and result storage
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import json
from sqlalchemy import Column, DateTime, String, select, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from shared.infrastructure.database import Base
from shared.infrastructure.database.rls import RLSManager
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class IdempotencyKeyModel(Base):
    """
    ORM model for idempotency keys.
    
    Stores request results to prevent duplicate processing.
    Composite key: (organization_id, endpoint, key)
    """
    
    __tablename__ = "idempotency_keys"
    __table_args__ = {"schema": "identity"}
    
    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    
    # Composite unique key
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Result storage
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return (
            f"<IdempotencyKey("
            f"org={self.organization_id}, "
            f"endpoint={self.endpoint}, "
            f"key={self.key})>"
        )


class IdempotencyConflictError(Exception):
    """Raised when idempotency key already exists with different result."""
    
    def __init__(
        self,
        organization_id: UUID,
        endpoint: str,
        key: str,
        existing_result: str | None = None,
    ):
        self.organization_id = organization_id
        self.endpoint = endpoint
        self.key = key
        self.existing_result = existing_result
        super().__init__(
            f"Idempotency conflict for key: {key} on endpoint: {endpoint}"
        )


class IdempotencyManager:
    """
    Manages idempotency keys to prevent duplicate request processing.
    
    Enforces composite key: (organization_id, endpoint, key)
    Default expiry: 24 hours
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize idempotency manager.
        
        Args:
            session: Active database session with RLS context set
        """
        self.session = session
    
    async def check_idempotency(
        self,
        organization_id: UUID,
        endpoint: str,
        key: str,
    ) -> IdempotencyKeyModel | None:
        """
        Check if idempotency key already exists.
        
        Args:
            organization_id: Organization UUID
            endpoint: API endpoint path
            key: Unique idempotency key
            
        Returns:
            Existing IdempotencyKeyModel if found, None otherwise
        """
        # Set RLS context
        await RLSManager.set_tenant_context(
            session=self.session,
            organization_id=organization_id,
        )
        
        stmt = select(IdempotencyKeyModel).where(
            IdempotencyKeyModel.organization_id == organization_id,
            IdempotencyKeyModel.endpoint == endpoint,
            IdempotencyKeyModel.key == key,
            IdempotencyKeyModel.expires_at > datetime.utcnow(),
        )
        
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(
                "Idempotency key found",
                extra={
                    "organization_id": str(organization_id),
                    "endpoint": endpoint,
                    "key": key,
                    "created_at": existing.created_at.isoformat(),
                },
            )
        
        return existing
    
    async def store_idempotency_result(
        self,
        organization_id: UUID,
        endpoint: str,
        key: str,
        result_data: dict[str, Any],
        http_status: int = 200,
        ttl_hours: int = 24,
    ) -> IdempotencyKeyModel:
        """
        Store result for idempotency key.
        
        Args:
            organization_id: Organization UUID
            endpoint: API endpoint path
            key: Unique idempotency key
            result_data: Response data to store
            http_status: HTTP status code of response
            ttl_hours: Time-to-live in hours (default: 24)
            
        Returns:
            Created IdempotencyKeyModel
            
        Raises:
            IdempotencyConflictError: If key already exists
        """
        # Set RLS context
        await RLSManager.set_tenant_context(
            session=self.session,
            organization_id=organization_id,
        )
        
        # Check if already exists
        existing = await self.check_idempotency(organization_id, endpoint, key)
        if existing:
            raise IdempotencyConflictError(
                organization_id=organization_id,
                endpoint=endpoint,
                key=key,
                existing_result=existing.result_data,
            )
        
        # Create new idempotency record
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        idempotency_record = IdempotencyKeyModel(
            organization_id=organization_id,
            endpoint=endpoint,
            key=key,
            result_data=json.dumps(result_data),
            http_status=http_status,
            expires_at=expires_at,
        )
        
        self.session.add(idempotency_record)
        await self.session.flush()
        
        logger.info(
            "Idempotency key stored",
            extra={
                "organization_id": str(organization_id),
                "endpoint": endpoint,
                "key": key,
                "expires_at": expires_at.isoformat(),
            },
        )
        
        return idempotency_record
    
    async def get_cached_result(
        self,
        organization_id: UUID,
        endpoint: str,
        key: str,
    ) -> tuple[dict[str, Any] | None, int | None]:
        """
        Get cached result for idempotency key.
        
        Args:
            organization_id: Organization UUID
            endpoint: API endpoint path
            key: Unique idempotency key
            
        Returns:
            Tuple of (result_data, http_status) or (None, None) if not found
        """
        existing = await self.check_idempotency(organization_id, endpoint, key)
        
        if not existing:
            return None, None
        
        if existing.result_data:
            result_data = json.loads(existing.result_data)
        else:
            result_data = None
        
        return result_data, existing.http_status
    
    async def cleanup_expired_keys(self) -> int:
        """
        Clean up expired idempotency keys.
        
        Should be run periodically via background job.
        
        Returns:
            Number of deleted records
        """
        from sqlalchemy import delete
        
        stmt = delete(IdempotencyKeyModel).where(
            IdempotencyKeyModel.expires_at <= datetime.utcnow()
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        deleted_count = result.rowcount
        
        logger.info(
            "Cleaned up expired idempotency keys",
            extra={"deleted_count": deleted_count},
        )
        
        return deleted_count