"""
Base Query Handler
Abstract base for all query handlers
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from shared.application.base_query import BaseQuery
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

TQuery = TypeVar("TQuery", bound=BaseQuery)
TResult = TypeVar("TResult")


class QueryHandler(ABC, Generic[TQuery, TResult]):
    """
    Abstract base class for query handlers.
    
    Query handlers execute read operations without modifying state.
    They fetch data from repositories or read models.
    
    Type Parameters:
        TQuery: Query type this handler processes
        TResult: Return type of the handler
        
    Example:
        class GetUserByIdQueryHandler(QueryHandler[GetUserByIdQuery, UserDTO]):
            async def handle(self, query: GetUserByIdQuery) -> UserDTO:
                # Fetch from repo, map to DTO, return
                pass
    """
    
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        """
        Handle the query and return result.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result (DTO or entity)
            
        Raises:
            NotFoundError: If requested resource not found
        """
        pass
    
    async def __call__(self, query: TQuery) -> TResult:
        """
        Make handler callable directly.
        
        Adds logging around query execution.
        
        Args:
            query: Query to execute
            
        Returns:
            Query result
        """
        query_name = query.__class__.__name__
        
        logger.debug(
            f"Executing query: {query_name}",
            extra={"query": query_name},
        )
        
        try:
            result = await self.handle(query)
            
            logger.debug(
                f"Query executed successfully: {query_name}",
                extra={"query": query_name},
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Query execution failed: {query_name}",
                extra={"query": query_name, "error": str(e)},
            )
            raise