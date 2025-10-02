"""
Shared Domain Layer
Pure domain contracts with no framework dependencies
"""
from shared.domain.base_aggregate_root import BaseAggregateRoot
from shared.domain.base_entity import BaseEntity
from shared.domain.base_value_object import BaseValueObject
from shared.domain.domain_event import DomainEvent
from shared.domain.result import Failure, Result, Success

__all__ = [
    "BaseEntity",
    "BaseValueObject",
    "BaseAggregateRoot",
    "DomainEvent",
    "Result",
    "Success",
    "Failure",
]