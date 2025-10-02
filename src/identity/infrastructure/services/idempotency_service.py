"""
Idempotency Service
Prevents duplicate operations via idempotency keys
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.observability.logger import get_logger
from src.identity.infrastructure.persistence.models.idempotency_key_model import (
    IdempotencyKeyModel,
)

logger = get_logger(__name__)


class IdempotencyRecord:
    """
    Represents a stored idempotency record.
    
    Attributes:
        exists: Whether the key already exists
        response_code: HTTP response code (if stored)
        response_body: Response body (if stored)
    """
    
    def __init__(
        self,
        exists: bool,
        response_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.exists = exists
        self.response_code = response_code
        self.response_body = response_body


class IdempotencyService:
    """
    Service for idempotency key management.
    
    Prevents duplicate operations by storing and checking idempotency keys.
    Keys expire after 24 hours by default.
    
    Usage:
        service = IdempotencyService(session)
        
        # Check if request was already processed
        record = await service.check_idempotency(
            organization_id=org_id,
            endpoint="/api/users",
            idempotency_key="user-create-123",
            request_hash=hash_of_request_body,
        )
        
        if record.exists:
            # Return cached response
            return record.response_code, record.response_body
        
        # Process request...
        
        # Store result for future replays
        await service.store_result(
            organization_id=org_id,
            endpoint="/api/users",
            idempotency_key="user-create-123",
            request_hash=hash_of_request_body,
            response_code=201,
            response_body={"id": "..."},
        )
    """
    
    DEFAULT_EXPIRY_HOURS = 24
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize idempotency service.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def check_idempotency(
        self,
        organization_id: UUID,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
    ) -> IdempotencyRecord:
        """
        Check if a request with this idempotency key was already processed.
        
        Args:
            organization_id: Organization UUID (tenant isolation)
            endpoint: API endpoint (e.g., "/api/users")
            idempotency_key: Client-provided idempotency key
            request_hash: Hash of request body for validation
            
        Returns:
            IdempotencyRecord with exists=True if found
        """
        stmt = select(IdempotencyKeyModel).where(
            IdempotencyKeyModel.organization_id == organization_id,
            IdempotencyKeyModel.endpoint == endpoint,
            IdempotencyKeyModel.idempotency_key == idempotency_key,
            IdempotencyKeyModel.expires_at > datetime.utcnow(),
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            logger.debug(
                "Idempotency key not found (new request)",
                extra={
                    "organization_id": str(organization_id),
                    "endpoint": endpoint,
                    "idempotency_key": idempotency_key,
                },
            )
            return IdempotencyRecord(exists=False)
        
        # Validate request hash matches (ensures request body is identical)
        if model.request_hash != request_hash:
            logger.warning(
                "Idempotency key exists but request hash mismatch",
                extra={
                    "organization_id": str(organization_id),
                    "endpoint": endpoint,
                    "idempotency_key": idempotency_key,
                },
            )
            # This is a conflict - same key, different request
            raise IdempotencyConflictException(
                f"Idempotency key '{idempotency_key}' already used with different request body"
            )
        
        logger.info(
            "Idempotency key found (duplicate request detected)",
            extra={
                "organization_id": str(organization_id),
                "endpoint": endpoint,
                "idempotency_key": idempotency_key,
                "response_code": model.response_code,
            },
        )
        
        return IdempotencyRecord(
            exists=True,
            response_code=model.response_code,
            response_body=model.response_body,
        )
    
    async def store_result(
        self,
        organization_id: UUID,
        endpoint: str,
        idempotency_key: str,
        request_hash: str,
        response_code: int,
        response_body: Dict[str, Any],
        expiry_hours: int = DEFAULT_EXPIRY_HOURS,
    ) -> None:
        """
        Store the result of a successful operation for future replays.
        
        Args:
            organization_id: Organization UUID
            endpoint: API endpoint
            idempotency_key: Client-provided idempotency key
            request_hash: Hash of request body
            response_code: HTTP response code
            response_body: Response body to cache
            expiry_hours: Hours until key expires (default: 24)
        """
        model = IdempotencyKeyModel(
            id=uuid4(),
            organization_id=organization_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_code=response_code,
            response_body=response_body,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours),
        )
        
        self.session.add(model)
        await self.session.flush()
        
        logger.info(
            "Stored idempotency key",
            extra={
                "organization_id": str(organization_id),
                "endpoint": endpoint,
                "idempotency_key": idempotency_key,
                "response_code": response_code,
                "expires_at": model.expires_at.isoformat(),
            },
        )
    
    async def cleanup_expired(self) -> int:
        """
        Delete expired idempotency keys (cleanup job).
        
        Should be run periodically (e.g., daily cron job).
        
        Returns:
            Number of keys deleted
        """
        stmt = delete(IdempotencyKeyModel).where(
            IdempotencyKeyModel.expires_at < datetime.utcnow()
        )
        
        result = await self.session.execute(stmt)
        count = result.rowcount
        
        logger.info(
            f"Cleaned up {count} expired idempotency keys",
            extra={"count": count},
        )
        
        return count
    
    @staticmethod
    def hash_request(request_body: Dict[str, Any]) -> str:
        """
        Generate a deterministic hash of the request body.
        
        Args:
            request_body: Request payload dict
            
        Returns:
            SHA-256 hex digest
        """
        # Sort keys for deterministic hashing
        canonical = json.dumps(request_body, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyConflictException(Exception):
    """Raised when idempotency key exists with different request hash"""
    pass