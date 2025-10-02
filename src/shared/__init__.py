"""
Shared Layer - Cross-Cutting Concerns
Domain contracts, infrastructure, application layer, and API utilities
"""

# Domain layer
from shared.domain import (
    BaseAggregateRoot,
    BaseEntity,
    BaseValueObject,
    DomainEvent,
    Failure,
    Result,
    Success,
)

# Infrastructure layer
from shared.infrastructure import (
    AuditLogger,
    Base,
    DatabaseSessionFactory,
    DomainEventPublisher,
    EncryptedString,
    EncryptionManager,
    EventBus,
    ICacheProvider,
    IRepository,
    IUnitOfWork,
    OutboxEvent,
    OutboxPublisher,
    RLSManager,
    RedisCache,
    SQLAlchemyRepository,
    SQLAlchemyUnitOfWork,
    bind_context,
    clear_context,
    configure_encryption,
    configure_logging,
    configure_metrics,
    configure_tracer,
    get_encryption_manager,
    get_event_bus,
    get_logger,
    get_metrics,
    get_tracer,
)

# Application layer
from shared.application import (
    BaseCommand,
    BaseQuery,
    CommandHandler,
    QueryHandler,
    UseCase,
)

# API layer
from shared.api import (
    APIException,
    AuthMiddleware,
    BusinessRuleViolationException,
    ConflictException,
    CorrelationIdMiddleware,
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ForbiddenException,
    NotFoundException,
    PaginatedResponse,
    RateLimitMiddleware,
    SuccessResponse,
    UnauthorizedException,
    ValidationException,
    api_exception_handler,
    create_api_router,
    generic_exception_handler,
)

__all__ = [
    # Domain
    "BaseEntity",
    "BaseValueObject",
    "BaseAggregateRoot",
    "DomainEvent",
    "Result",
    "Success",
    "Failure",
    # Infrastructure - Database
    "Base",
    "DatabaseSessionFactory",
    "IRepository",
    "SQLAlchemyRepository",
    "IUnitOfWork",
    "SQLAlchemyUnitOfWork",
    "RLSManager",
    # Infrastructure - Cache
    "ICacheProvider",
    "RedisCache",
    # Infrastructure - Security
    "EncryptionManager",
    "get_encryption_manager",
    "configure_encryption",
    "EncryptedString",
    "AuditLogger",
    # Infrastructure - Messaging
    "EventBus",
    "get_event_bus",
    "OutboxEvent",
    "OutboxPublisher",
    "DomainEventPublisher",
    # Infrastructure - Observability
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "configure_tracer",
    "get_tracer",
    "configure_metrics",
    "get_metrics",
    # Application
    "BaseCommand",
    "BaseQuery",
    "CommandHandler",
    "QueryHandler",
    "UseCase",
    # API
    "create_api_router",
    "SuccessResponse",
    "ErrorResponse",
    "ErrorDetail",
    "PaginatedResponse",
    "APIException",
    "ValidationException",
    "NotFoundException",
    "UnauthorizedException",
    "ForbiddenException",
    "ConflictException",
    "BusinessRuleViolationException",
    "ErrorCode",
    "api_exception_handler",
    "generic_exception_handler",
    "AuthMiddleware",
    "CorrelationIdMiddleware",
    "RateLimitMiddleware",
]