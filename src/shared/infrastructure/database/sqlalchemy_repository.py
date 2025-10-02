"""
SQLAlchemy Implementation of Generic Repository
Concrete async repository using SQLAlchemy 2.x
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, Type, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.domain.base_entity import BaseEntity
from shared.infrastructure.database.base_model import Base
from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)

TEntity = TypeVar("TEntity", bound=BaseEntity)
TModel = TypeVar("TModel", bound=Base)


class SQLAlchemyRepository(Generic[TEntity, TModel]):
    """
    Generic async SQLAlchemy repository implementation.
    
    Provides CRUD operations for domain entities by mapping to/from ORM models.
    
    Type Parameters:
        TEntity: Domain entity type
        TModel: SQLAlchemy ORM model type
        
    Attributes:
        session: Async SQLAlchemy session
        model_class: ORM model class
        entity_class: Domain entity class
    """
    
    def __init__(
        self,
        session: AsyncSession,
        model_class: Type[TModel],
        entity_class: Type[TEntity],
    ) -> None:
        """
        Initialize repository with session and model mappings.
        
        Args:
            session: Active async database session
            model_class: SQLAlchemy ORM model class
            entity_class: Domain entity class
        """
        self.session = session
        self.model_class = model_class
        self.entity_class = entity_class
    
    def _to_entity(self, model: TModel) -> TEntity:
        """
        Convert ORM model to domain entity.
        
        Must be implemented by subclass to define mapping logic.
        
        Args:
            model: ORM model instance
            
        Returns:
            Domain entity instance
        """
        raise NotImplementedError("Subclass must implement _to_entity")
    
    def _to_model(self, entity: TEntity) -> TModel:
        """
        Convert domain entity to ORM model.
        
        Must be implemented by subclass to define mapping logic.
        
        Args:
            entity: Domain entity instance
            
        Returns:
            ORM model instance
        """
        raise NotImplementedError("Subclass must implement _to_model")
    
    async def add(self, entity: TEntity) -> TEntity:
        """
        Add a new entity to the repository.
        
        Args:
            entity: Domain entity to persist
            
        Returns:
            The persisted entity
        """
        try:
            model = self._to_model(entity)
            self.session.add(model)
            await self.session.flush()
            await self.session.refresh(model)
            
            logger.debug(
                f"Added {self.entity_class.__name__}",
                extra={"entity_id": str(entity.id)},
            )
            
            return self._to_entity(model)
        except Exception as e:
            logger.error(
                f"Failed to add {self.entity_class.__name__}",
                extra={"error": str(e), "entity_id": str(entity.id)},
            )
            raise
    
    async def get_by_id(self, entity_id: UUID) -> TEntity | None:
        """
        Retrieve entity by its unique identifier.
        
        Args:
            entity_id: UUID of the entity
            
        Returns:
            Entity if found, None otherwise
        """
        try:
            stmt = select(self.model_class).where(self.model_class.id == entity_id)
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model is None:
                logger.debug(
                    f"{self.entity_class.__name__} not found",
                    extra={"entity_id": str(entity_id)},
                )
                return None
            
            return self._to_entity(model)
        except Exception as e:
            logger.error(
                f"Failed to get {self.entity_class.__name__}",
                extra={"error": str(e), "entity_id": str(entity_id)},
            )
            raise
    
    async def get_by_ids(self, entity_ids: Sequence[UUID]) -> Sequence[TEntity]:
        """
        Retrieve multiple entities by their IDs.
        
        Args:
            entity_ids: List of UUIDs
            
        Returns:
            List of found entities
        """
        try:
            stmt = select(self.model_class).where(self.model_class.id.in_(entity_ids))
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
        except Exception as e:
            logger.error(
                f"Failed to get multiple {self.entity_class.__name__}",
                extra={"error": str(e), "count": len(entity_ids)},
            )
            raise
    
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
            skip: Number of records to skip
            limit: Maximum records to return
            order_by: Column name to order by
            **filters: Column filters
            
        Returns:
            List of matching entities
        """
        try:
            stmt = select(self.model_class)
            
            # Apply filters
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)
            
            # Apply ordering
            if order_by and hasattr(self.model_class, order_by):
                stmt = stmt.order_by(getattr(self.model_class, order_by))
            
            # Apply pagination
            stmt = stmt.offset(skip).limit(limit)
            
            result = await self.session.execute(stmt)
            models = result.scalars().all()
            
            return [self._to_entity(model) for model in models]
        except Exception as e:
            logger.error(
                f"Failed to find {self.entity_class.__name__} entities",
                extra={"error": str(e), "filters": filters},
            )
            raise
    
    async def find_one(self, **filters: Any) -> TEntity | None:
        """
        Find single entity matching filters.
        
        Args:
            **filters: Column filters
            
        Returns:
            First matching entity or None
        """
        try:
            stmt = select(self.model_class)
            
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)
            
            result = await self.session.execute(stmt)
            model = result.scalar_one_or_none()
            
            return self._to_entity(model) if model else None
        except Exception as e:
            logger.error(
                f"Failed to find one {self.entity_class.__name__}",
                extra={"error": str(e), "filters": filters},
            )
            raise
    
    async def update(self, entity: TEntity) -> TEntity:
        """
        Update an existing entity.
        
        Args:
            entity: Domain entity with updated values
            
        Returns:
            Updated entity
        """
        try:
            model = self._to_model(entity)
            merged = await self.session.merge(model)
            await self.session.flush()
            await self.session.refresh(merged)
            
            logger.debug(
                f"Updated {self.entity_class.__name__}",
                extra={"entity_id": str(entity.id)},
            )
            
            return self._to_entity(merged)
        except Exception as e:
            logger.error(
                f"Failed to update {self.entity_class.__name__}",
                extra={"error": str(e), "entity_id": str(entity.id)},
            )
            raise
    
    async def delete(self, entity_id: UUID) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: UUID of entity to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            stmt = delete(self.model_class).where(self.model_class.id == entity_id)
            result = await self.session.execute(stmt)
            await self.session.flush()
            
            deleted = result.rowcount > 0
            
            if deleted:
                logger.debug(
                    f"Deleted {self.entity_class.__name__}",
                    extra={"entity_id": str(entity_id)},
                )
            
            return deleted
        except Exception as e:
            logger.error(
                f"Failed to delete {self.entity_class.__name__}",
                extra={"error": str(e), "entity_id": str(entity_id)},
            )
            raise
    
    async def delete_many(self, entity_ids: Sequence[UUID]) -> int:
        """
        Delete multiple entities by IDs.
        
        Args:
            entity_ids: List of UUIDs to delete
            
        Returns:
            Number of entities deleted
        """
        try:
            stmt = delete(self.model_class).where(self.model_class.id.in_(entity_ids))
            result = await self.session.execute(stmt)
            await self.session.flush()
            
            count = result.rowcount
            
            logger.debug(
                f"Deleted {count} {self.entity_class.__name__} entities",
                extra={"count": count},
            )
            
            return count
        except Exception as e:
            logger.error(
                f"Failed to delete multiple {self.entity_class.__name__}",
                extra={"error": str(e), "count": len(entity_ids)},
            )
            raise
    
    async def count(self, **filters: Any) -> int:
        """
        Count entities matching filters.
        
        Args:
            **filters: Column filters
            
        Returns:
            Count of matching entities
        """
        try:
            stmt = select(func.count()).select_from(self.model_class)
            
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)
            
            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(
                f"Failed to count {self.entity_class.__name__}",
                extra={"error": str(e), "filters": filters},
            )
            raise
    
    async def exists(self, entity_id: UUID) -> bool:
        """
        Check if entity exists by ID.
        
        Args:
            entity_id: UUID to check
            
        Returns:
            True if exists, False otherwise
        """
        try:
            stmt = select(func.count()).select_from(self.model_class).where(
                self.model_class.id == entity_id
            )
            result = await self.session.execute(stmt)
            count = result.scalar_one()
            
            return count > 0
        except Exception as e:
            logger.error(
                f"Failed to check existence of {self.entity_class.__name__}",
                extra={"error": str(e), "entity_id": str(entity_id)},
            )
            raise
    
    # ========================================================================
    # DATABASE FUNCTIONS & STORED PROCEDURES
    # ========================================================================
    
    async def call_function(
        self,
        function_name: str,
        *args: Any,
        schema: str | None = None,
        return_type: str = "scalar",
    ) -> Any:
        """
        Call a PostgreSQL function.
        
        Args:
            function_name: Name of the function
            *args: Function arguments (positional)
            schema: Schema name (e.g., 'public', 'identity')
            return_type: Return type - 'scalar', 'row', 'rows', 'none'
            
        Returns:
            Function result based on return_type
            
        Examples:
            # Scalar function (returns single value)
            count = await repo.call_function(
                "count_active_users",
                org_id,
                schema="identity",
                return_type="scalar"
            )
            
            # Table-valued function (returns multiple rows)
            results = await repo.call_function(
                "get_user_permissions",
                user_id,
                schema="identity",
                return_type="rows"
            )
            
            # Function with no return
            await repo.call_function(
                "cleanup_expired_tokens",
                schema="identity",
                return_type="none"
            )
        """
        try:
            # Build function call
            qualified_name = f"{schema}.{function_name}" if schema else function_name
            
            # Create parameter placeholders
            placeholders = ", ".join([f":arg{i}" for i in range(len(args))])
            
            # Build SQL
            if return_type == "none":
                sql = f"SELECT {qualified_name}({placeholders})"
            else:
                sql = f"SELECT * FROM {qualified_name}({placeholders})"
            
            # Bind parameters
            params = {f"arg{i}": arg for i, arg in enumerate(args)}
            
            logger.debug(
                f"Calling function: {qualified_name}",
                extra={
                    "function": qualified_name,
                    "args": args,
                    "return_type": return_type,
                },
            )
            
            # Execute
            result = await self.session.execute(text(sql), params)
            
            # Process result based on return_type
            if return_type == "none":
                return None
            elif return_type == "scalar":
                return result.scalar()
            elif return_type == "row":
                return result.fetchone()
            elif return_type == "rows":
                return result.fetchall()
            else:
                raise ValueError(f"Invalid return_type: {return_type}")
                
        except Exception as e:
            logger.error(
                f"Function call failed: {qualified_name}",
                extra={"error": str(e), "function": qualified_name},
            )
            raise
    
    async def call_procedure(
        self,
        procedure_name: str,
        *args: Any,
        schema: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Call a PostgreSQL stored procedure.
        
        Args:
            procedure_name: Name of the procedure
            *args: Positional arguments
            schema: Schema name
            **kwargs: Named arguments
            
        Examples:
            # Simple procedure call
            await repo.call_procedure(
                "archive_old_conversations",
                days=90,
                schema="conversations"
            )
            
            # With positional args
            await repo.call_procedure(
                "update_user_stats",
                user_id,
                new_count,
                schema="identity"
            )
        """
        try:
            qualified_name = f"{schema}.{procedure_name}" if schema else procedure_name
            
            # Build parameter list
            params = {}
            sql_parts = []
            
            # Add positional args
            for i, arg in enumerate(args):
                key = f"arg{i}"
                params[key] = arg
                sql_parts.append(f":{key}")
            
            # Add named args
            for key, value in kwargs.items():
                params[key] = value
                sql_parts.append(f"{key} => :{key}")
            
            # Build SQL
            param_str = ", ".join(sql_parts)
            sql = f"CALL {qualified_name}({param_str})"
            
            logger.debug(
                f"Calling procedure: {qualified_name}",
                extra={
                    "procedure": qualified_name,
                    "args": args,
                    "kwargs": kwargs,
                },
            )
            
            # Execute
            await self.session.execute(text(sql), params)
            
        except Exception as e:
            logger.error(
                f"Procedure call failed: {qualified_name}",
                extra={"error": str(e), "procedure": qualified_name},
            )
            raise
    
    async def execute_raw_sql(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        fetch: str = "none",
    ) -> Any:
        """
        Execute raw SQL with parameter binding.
        
        Args:
            sql: Raw SQL query
            params: Named parameters for binding
            fetch: Fetch mode - 'none', 'scalar', 'row', 'rows', 'all'
            
        Returns:
            Query result based on fetch mode
            
        Examples:
            # Complex query not easily expressible in ORM
            results = await repo.execute_raw_sql(
                '''
                SELECT u.*, COUNT(c.id) as conv_count
                FROM identity.users u
                LEFT JOIN conversations.conversations c ON u.id = c.user_id
                WHERE u.organization_id = :org_id
                  AND u.created_at >= :start_date
                GROUP BY u.id
                HAVING COUNT(c.id) > :min_count
                ''',
                params={
                    "org_id": org_id,
                    "start_date": start_date,
                    "min_count": 5
                },
                fetch="rows"
            )
            
            # Execute with no result
            await repo.execute_raw_sql(
                "UPDATE identity.users SET last_active = NOW() WHERE id = :user_id",
                params={"user_id": user_id},
                fetch="none"
            )
        """
        try:
            logger.debug(
                "Executing raw SQL",
                extra={
                    "sql_preview": sql[:100],
                    "params": params,
                    "fetch": fetch,
                },
            )
            
            result = await self.session.execute(text(sql), params or {})
            
            if fetch == "none":
                return None
            elif fetch == "scalar":
                return result.scalar()
            elif fetch == "row":
                return result.fetchone()
            elif fetch == "rows" or fetch == "all":
                return result.fetchall()
            else:
                raise ValueError(f"Invalid fetch mode: {fetch}")
                
        except Exception as e:
            logger.error(
                "Raw SQL execution failed",
                extra={"error": str(e), "sql_preview": sql[:100]},
            )
            raise
    
    async def bulk_execute(
        self,
        sql: str,
        params_list: list[dict[str, Any]],
    ) -> None:
        """
        Execute SQL with multiple parameter sets (bulk operation).
        
        More efficient than executing individual statements in a loop.
        
        Args:
            sql: SQL statement with parameter placeholders
            params_list: List of parameter dictionaries
            
        Example:
            # Bulk insert
            await repo.bulk_execute(
                "INSERT INTO logs (user_id, action, timestamp) VALUES (:user_id, :action, :ts)",
                [
                    {"user_id": uid1, "action": "login", "ts": ts1},
                    {"user_id": uid2, "action": "logout", "ts": ts2},
                    # ... hundreds more
                ]
            )
        """
        try:
            logger.debug(
                "Executing bulk SQL",
                extra={"sql_preview": sql[:100], "batch_size": len(params_list)},
            )
            
            await self.session.execute(text(sql), params_list)
            
        except Exception as e:
            logger.error(
                "Bulk SQL execution failed",
                extra={"error": str(e), "batch_size": len(params_list)},
            )
            raise