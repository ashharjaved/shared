"""
Database Function and Stored Procedure Helpers
Common patterns for calling database functions
"""
from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.observability.logger import get_logger

logger = get_logger(__name__)


class DatabaseFunctionHelper:
    """
    Helper class for common database function patterns.
    
    Provides typed wrappers for frequently used function patterns.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize function helper.
        
        Args:
            session: Async database session
        """
        self.session = session
    
    async def call_scalar_function(
        self,
        function_name: str,
        *args: Any,
        schema: str | None = None,
    ) -> Any:
        """
        Call a function that returns a single scalar value.
        
        Args:
            function_name: Function name
            *args: Function arguments
            schema: Schema name
            
        Returns:
            Scalar result
            
        Example:
            count = await helper.call_scalar_function(
                "count_active_sessions",
                user_id,
                schema="identity"
            )
        """
        qualified_name = f"{schema}.{function_name}" if schema else function_name
        placeholders = ", ".join([f":arg{i}" for i in range(len(args))])
        sql = f"SELECT {qualified_name}({placeholders})"
        params = {f"arg{i}": arg for i, arg in enumerate(args)}
        
        result = await self.session.execute(text(sql), params)
        return result.scalar()
    
    async def call_table_function(
        self,
        function_name: str,
        *args: Any,
        schema: str | None = None,
    ) -> Sequence[Row[Any]]:
        """
        Call a table-valued function (returns multiple rows).
        
        Args:
            function_name: Function name
            *args: Function arguments
            schema: Schema name
            
        Returns:
            Sequence of result rows
            
        Example:
            permissions = await helper.call_table_function(
                "get_user_effective_permissions",
                user_id,
                org_id,
                schema="identity"
            )
        """
        qualified_name = f"{schema}.{function_name}" if schema else function_name
        placeholders = ", ".join([f":arg{i}" for i in range(len(args))])
        sql = f"SELECT * FROM {qualified_name}({placeholders})"
        params = {f"arg{i}": arg for i, arg in enumerate(args)}
        
        result = await self.session.execute(text(sql), params)
        return result.fetchall()
    
    async def call_json_function(
        self,
        function_name: str,
        *args: Any,
        schema: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """
        Call a function that returns JSON/JSONB.
        
        Args:
            function_name: Function name
            *args: Function arguments
            schema: Schema name
            
        Returns:
            Parsed JSON result
            
        Example:
            analytics = await helper.call_json_function(
                "get_conversation_analytics",
                org_id,
                start_date,
                end_date,
                schema="analytics"
            )
        """
        import json
        
        result = await self.call_scalar_function(function_name, *args, schema=schema)
        
        if result is None:
            return {}
        
        if isinstance(result, (dict, list)):
            return result
        
        return json.loads(result) if isinstance(result, str) else result
    
    async def call_aggregation_function(
        self,
        function_name: str,
        table_name: str,
        column_name: str,
        filters: dict[str, Any] | None = None,
        schema: str | None = None,
    ) -> Any:
        """
        Call aggregation functions (COUNT, SUM, AVG, etc.) with filters.
        
        Args:
            function_name: Aggregation function (COUNT, SUM, AVG, MAX, MIN)
            table_name: Table name
            column_name: Column to aggregate
            filters: WHERE clause filters
            schema: Schema name
            
        Returns:
            Aggregation result
            
        Example:
            total_messages = await helper.call_aggregation_function(
                "COUNT",
                "messages",
                "*",
                filters={"status": "delivered", "channel_id": channel_id},
                schema="whatsapp"
            )
        """
        qualified_table = f"{schema}.{table_name}" if schema else table_name
        sql = f"SELECT {function_name}({column_name}) FROM {qualified_table}"
        
        params = {}
        if filters:
            where_clauses = []
            for i, (key, value) in enumerate(filters.items()):
                param_name = f"filter{i}"
                where_clauses.append(f"{key} = :{param_name}")
                params[param_name] = value
            
            sql += " WHERE " + " AND ".join(where_clauses)
        
        result = await self.session.execute(text(sql), params)
        return result.scalar()


class StoredProcedureHelper:
    """
    Helper class for common stored procedure patterns.
    """
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize procedure helper.
        
        Args:
            session: Async database session
        """
        self.session = session
    
    async def call_maintenance_procedure(
        self,
        procedure_name: str,
        schema: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Call a maintenance procedure (cleanup, archival, etc.).
        
        Args:
            procedure_name: Procedure name
            schema: Schema name
            **kwargs: Named arguments
            
        Example:
            await helper.call_maintenance_procedure(
                "archive_old_conversations",
                schema="conversations",
                days_old=90,
                batch_size=1000
            )
        """
        qualified_name = f"{schema}.{procedure_name}" if schema else procedure_name
        
        params = kwargs
        param_str = ", ".join([f"{k} => :{k}" for k in kwargs.keys()])
        sql = f"CALL {qualified_name}({param_str})"
        
        logger.info(
            f"Calling maintenance procedure: {qualified_name}",
            extra={"procedure": qualified_name, "params": kwargs},
        )
        
        await self.session.execute(text(sql), params)
    
    async def call_data_migration_procedure(
        self,
        procedure_name: str,
        source_id: UUID,
        target_id: UUID,
        schema: str | None = None,
        dry_run: bool = False,
    ) -> None:
        """
        Call a data migration procedure.
        
        Args:
            procedure_name: Procedure name
            source_id: Source identifier
            target_id: Target identifier
            schema: Schema name
            dry_run: Whether to run in dry-run mode
            
        Example:
            await helper.call_data_migration_procedure(
                "migrate_user_data",
                old_user_id,
                new_user_id,
                schema="identity",
                dry_run=True
            )
        """
        qualified_name = f"{schema}.{procedure_name}" if schema else procedure_name
        
        sql = f"CALL {qualified_name}(:source_id, :target_id, :dry_run)"
        params = {
            "source_id": source_id,
            "target_id": target_id,
            "dry_run": dry_run,
        }
        
        logger.info(
            f"Calling migration procedure: {qualified_name}",
            extra={
                "procedure": qualified_name,
                "source_id": str(source_id),
                "target_id": str(target_id),
                "dry_run": dry_run,
            },
        )
        
        await self.session.execute(text(sql), params)