"""
Shared Infrastructure Layer
Database, cache, security, messaging, and observability
"""
from shared.infrastructure.cache import ICacheProvider, RedisCache
from shared.infrastructure.database import (
    Base,
    DatabaseSessionFactory,
    IRepository,
    IUnitOfWork,
    RLSManager,
    SQLAlchemyRepository,
    SQLAlchemyUnitOfWork,
)
from shared.infrastructure.messaging import (
    DomainEventPublisher,
    EventBus,
    OutboxEvent,
    OutboxPublisher,
    get_event_bus,
)
from shared.infrastructure.observability import (
    bind_context,
    clear_context,
    configure_logging,
    configure_metrics,
    configure_tracer,
    get_logger,
    get_metrics,
    get_tracer,
)
from shared.infrastructure.security import (
    AuditLogger,
    EncryptedString,
    EncryptionManager,
    configure_encryption,
    get_encryption_manager,
)

__all__ = [
    # Database
    "Base",
    "DatabaseSessionFactory",
    "IRepository",
    "SQLAlchemyRepository",
    "IUnitOfWork",
    "SQLAlchemyUnitOfWork",
    "RLSManager",
    # Cache
    "ICacheProvider",
    "RedisCache",
    # Security
    "EncryptionManager",
    "get_encryption_manager",
    "configure_encryption",
    "EncryptedString",
    "AuditLogger",
    # Messaging
    "EventBus",
    "get_event_bus",
    "OutboxEvent",
    "OutboxPublisher",
    "DomainEventPublisher",
    # Observability
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "configure_tracer",
    "get_tracer",
    "configure_metrics",
    "get_metrics",
]