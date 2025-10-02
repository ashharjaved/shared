# src/modules/whatsapp/infrastructure/idempotency/idempotency_manager.py
"""
Idempotency Key Manager
Prevents duplicate message processing and sending
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, Column, String, DateTime, Index, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.infrastructure.database.base_model import Base
from src.shared.infrastructure.database.rls import enforce_rls
from src.shared.infrastructure.observability.logger import get_logger
from src.modules.whatsapp.domain.exceptions import WhatsAppDomainError


logger = get_logger(__name__)


class IdempotencyKeyModel(Base):
    """
    ORM model for idempotency keys.
    
    Table: whatsapp.idempotency_keys
    Ensures exactly-once processing of requests.
    """
    
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        Index(
            "idx_idempotency_tenant_endpoint_key",
            "tenant_id",
            "endpoint",
            "key",
            unique=True,
        ),
        Index(
            "idx_idempotency_expires_at",
            "expires_at",
        ),
        {"schema": "whatsapp"},
    )
    
    id = Column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    
    tenant_id = Column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    
    endpoint = Column(
        String(255),
        nullable=False,
        comment="API endpoint or operation name",
    )
    
    key = Column(
        String(255),
        nullable=False,
        comment="Client-provided idempotency key",
    )
    
    result_data = Column(
        Text,
        nullable=True,
        comment="Cached response for replay",
    )
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Key expiry (default 24 hours)",
    )


@dataclass
class IdempotencyKey:
    """Idempotency key data."""
    tenant_id: UUID
    endpoint: str
    key: str
    result_data: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class IdempotencyManager:
    """
    Manages idempotency keys for duplicate request prevention.
    
    Usage:
        manager = IdempotencyManager(session)
        
        # Check if request already processed
        existing = await manager.get_or_create(
            tenant_id=tenant_id,
            endpoint="send_message",
            key=client_idempotency_key,
            ttl_hours=24
        )
        
        if existing.result_data:
            # Already processed, return cached result
            return existing.result_data
        
        # Process request...
        result = await send_message(...)
        
        # Store result
        await manager.store_result(existing, result)
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize idempotency manager.
        
        Args:
            session: Database session
        """
        self.session = session
    
    async def get_or_create(
        self,
        tenant_id: UUID,
        endpoint: str,
        key: str,
        ttl_hours: int = 24,
    ) -> IdempotencyKey:
        """
        Get existing idempotency key or create new one.
        
        Args:
            tenant_id: Tenant UUID
            endpoint: Operation identifier
            key: Idempotency key
            ttl_hours: Time-to-live in hours
            
        Returns:
            IdempotencyKey instance
        """
        await enforce_rls(self.session, tenant_id)
        
        # Try to get existing
        stmt = select(IdempotencyKeyModel).where(
            and_(
                IdempotencyKeyModel.tenant_id == tenant_id,
                IdempotencyKeyModel.endpoint == endpoint,
                IdempotencyKeyModel.key == key,
                IdempotencyKeyModel.expires_at > datetime.utcnow(),
            )
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            logger.info(
                "Found existing idempotency key",
                extra={
                    "tenant_id": str(tenant_id),
                    "endpoint": endpoint,
                    "key": key,
                },
            )
            
            return IdempotencyKey(
                tenant_id=model.tenant_id,
                endpoint=model.endpoint,
                key=model.key,
                result_data=model.result_data,
                created_at=model.created_at,
                expires_at=model.expires_at,
            )
        
        # Create new
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        new_model = IdempotencyKeyModel(
            tenant_id=tenant_id,
            endpoint=endpoint,
            key=key,
            expires_at=expires_at,
        )
        
        self.session.add(new_model)
        await self.session.flush()
        
        logger.info(
            "Created new idempotency key",
            extra={
                "tenant_id": str(tenant_id),
                "endpoint": endpoint,
                "key": key,
                "expires_at": expires_at.isoformat(),
            },
        )
        
        return IdempotencyKey(
            tenant_id=tenant_id,
            endpoint=endpoint,
            key=key,
            created_at=new_model.created_at,
            expires_at=expires_at,
        )
    
    async def store_result(
        self,
        idempotency_key: IdempotencyKey,
        result_data: str,
    ) -> None:
        """
        Store operation result for future replay.
        
        Args:
            idempotency_key: Key to update
            result_data: Serialized result
        """
        await enforce_rls(self.session, idempotency_key.tenant_id)
        
        stmt = select(IdempotencyKeyModel).where(
            and_(
                IdempotencyKeyModel.tenant_id == idempotency_key.tenant_id,
                IdempotencyKeyModel.endpoint == idempotency_key.endpoint,
                IdempotencyKeyModel.key == idempotency_key.key,
            )
        )
        
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            model.result_data = result_data
            await self.session.flush()
            
            logger.info(
                "Stored idempotency result",
                extra={
                    "tenant_id": str(idempotency_key.tenant_id),
                    "endpoint": idempotency_key.endpoint,
                    "key": idempotency_key.key,
                },
            )
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired idempotency keys.
        
        Returns:
            Number of keys deleted
        """
        # This should be called by a periodic cleanup job
        stmt = text("""
            DELETE FROM whatsapp.idempotency_keys
            WHERE expires_at < NOW()
        """)
        
        result = await self.session.execute(stmt)
        count = result.rowcount
        
        logger.info(f"Cleaned up {count} expired idempotency keys")
        
        return count