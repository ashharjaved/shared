"""
SQLAlchemy Implementation of Unit of Work
Manages database transactions with async SQLAlchemy sessions
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.unit_of_work import IUnitOfWork
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class SQLAlchemyUnitOfWork:
    """
    SQLAlchemy-based Unit of Work implementation.
    
    Manages database transactions and coordinates repository operations.
    Ensures all operations within context are atomic (all succeed or all fail).
    
    Attributes:
        session: Async SQLAlchemy session
        _committed: Flag tracking if transaction was committed
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize UoW with an async session.
        
        Args:
            session: Active async database session
        """
        self.session = session
        self._committed = False
    
    async def __aenter__(self) -> SQLAlchemyUnitOfWork:
        """
        Enter async context manager.
        
        Begins a new transaction if not already in one.
        
        Returns:
            Self (the UoW instance)
        """
        if not self.session.in_transaction():
            await self.session.begin()
        
        logger.debug("UnitOfWork transaction started")
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit async context manager.
        
        Automatically rolls back if exception occurred or not committed.
        
        Args:
            exc_type: Exception type if raised
            exc_val: Exception value if raised
            exc_tb: Exception traceback if raised
        """
        if exc_type is not None:
            await self.rollback()
            logger.error(
                "UnitOfWork rolled back due to exception",
                extra={"exception": str(exc_val)},
            )
        elif not self._committed:
            await self.rollback()
            logger.warning("UnitOfWork rolled back (not committed)")
    
    async def commit(self) -> None:
        """
        Commit the current transaction.
        
        Persists all changes made within this UoW context.
        Collects and publishes domain events from aggregates after commit.
        
        Raises:
            Exception: If commit fails
        """
        try:
            await self.session.commit()
            self._committed = True
            
            logger.debug("UnitOfWork transaction committed")
            
            # TODO: Collect and publish domain events from aggregates
            # This should iterate through tracked entities, collect events,
            # and publish to event bus (implementation in messaging layer)
            
        except Exception as e:
            await self.rollback()
            logger.error(
                "UnitOfWork commit failed",
                extra={"error": str(e)},
            )
            raise
    
    async def rollback(self) -> None:
        """
        Rollback the current transaction.
        
        Discards all changes made within this UoW context.
        """
        try:
            await self.session.rollback()
            self._committed = False
            
            logger.debug("UnitOfWork transaction rolled back")
        except Exception as e:
            logger.error(
                "UnitOfWork rollback failed",
                extra={"error": str(e)},
            )
            raise