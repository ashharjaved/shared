"""
Generic Repository Interface (Protocol)
Contract for all repository implementations
"""
from __future__ import annotations

from typing import Any, Generic, Protocol, Sequence, TypeVar
from uuid import UUID

from shared.domain.base_entity import BaseEntity

T = TypeVar("T", bound=BaseEntity, contravariant=True)
TEntity = TypeVar("TEntity", bound=BaseEntity)


class IRepository(Protocol, Generic[TEntity]):
    """
    Generic repository interface for domain entities.
    
    All repository implementations must conform to this protocol.
    Repositories provide abstract persistence operations without
    exposing ORM details to the domain/application layers.
    
    Type Parameters:
        TEntity: Domain entity type (must extend BaseEntity)
    """
    
    async def add(self, entity: TEntity) -> TEntity:
        """
        Add a new entity to the repository.
        
        Args:
            entity: Domain entity to persist
            
        Returns:
            The persisted entity
            
        Raises:
            DuplicateEntityError: If entity with same ID already exists
        """
        ...
    
    async def get_by_id(self, entity_id: UUID) -> TEntity | None:
        """
        Retrieve entity by its unique identifier.
        
        Args:
            entity_id: UUID of the entity
            
        Returns:
            Entity if found, None otherwise
        """
        ...
    
    async def get_by_ids(self, entity_ids: Sequence[UUID]) -> Sequence[TEntity]:
        """
        Retrieve multiple entities by their IDs.
        
        Args:
            entity_ids: List of UUIDs
            
        Returns:
            List of found entities (may be shorter than input if some not found)
        """
        ...
    
    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        **filters: Any,
    ) -> Sequence[TEntity]:
        """
        Find all entities matching filters.
        
        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            order_by: Column name to order by (e.g., 'created_at')
            **filters: Column filters (e.g., status='active')
            
        Returns:
            List of matching entities
        """
        ...
    
    async def find_one(self, **filters: Any) -> TEntity | None:
        """
        Find single entity matching filters.
        
        Args:
            **filters: Column filters
            
        Returns:
            First matching entity or None
        """
        ...
    
    async def update(self, entity: TEntity) -> TEntity:
        """
        Update an existing entity.
        
        Args:
            entity: Domain entity with updated values
            
        Returns:
            Updated entity
            
        Raises:
            EntityNotFoundError: If entity doesn't exist
        """
        ...
    
    async def delete(self, entity_id: UUID) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: UUID of entity to delete
            
        Returns:
            True if deleted, False if not found
        """
        ...
    
    async def delete_many(self, entity_ids: Sequence[UUID]) -> int:
        """
        Delete multiple entities by IDs.
        
        Args:
            entity_ids: List of UUIDs to delete
            
        Returns:
            Number of entities deleted
        """
        ...
    
    async def count(self, **filters: Any) -> int:
        """
        Count entities matching filters.
        
        Args:
            **filters: Column filters
            
        Returns:
            Count of matching entities
        """
        ...
    
    async def exists(self, entity_id: UUID) -> bool:
        """
        Check if entity exists by ID.
        
        Args:
            entity_id: UUID to check
            
        Returns:
            True if exists, False otherwise
        """
        ...