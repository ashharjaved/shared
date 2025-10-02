"""
Unit of Work Interface (Protocol)
Manages transactions and coordinates repository operations
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IUnitOfWork(Protocol):
    """
    Unit of Work interface for transaction management.
    
    Coordinates multiple repository operations within a single transaction.
    All writes must occur within a UoW context to ensure atomicity.
    
    Usage:
        async with uow:
            entity = await uow.repository.get_by_id(id)
            entity.update_something()
            await uow.repository.update(entity)
            await uow.commit()  # Commits all changes atomically
    """
    
    async def __aenter__(self) -> IUnitOfWork:
        """
        Enter async context manager.
        
        Returns:
            Self (the UoW instance)
        """
        ...
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Exit async context manager.
        
        Automatically rolls back if exception occurred.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        ...
    
    async def commit(self) -> None:
        """
        Commit the current transaction.
        
        Persists all changes made within this UoW context.
        Should collect and publish domain events after successful commit.
        
        Raises:
            Exception: If commit fails
        """
        ...
    
    async def rollback(self) -> None:
        """
        Rollback the current transaction.
        
        Discards all changes made within this UoW context.
        """
        ...