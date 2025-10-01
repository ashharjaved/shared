from __future__ import annotations

from typing import Generic, Protocol, TypeVar

M = TypeVar("M")  # ORM model type
E = TypeVar("E")  # Domain entity type


class Mapper(Protocol, Generic[M, E]):
    """Generic mapper protocol for converting between ORM models and domain entities.

    Implementations MUST be pure (no I/O, no session usage).
    """

    def to_domain(self, model: M) -> E:
        """Convert an ORM model instance to a domain entity."""
        ...

    def to_orm(self, entity: E) -> M:
        """Convert a domain entity to an ORM model instance."""
        ...


__all__ = ["Mapper", "M", "E"]