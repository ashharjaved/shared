# src/shared/database/base_repository.py
"""
Base repository with generic CRUD operations and RLS enforcement.
"""

from abc import ABC
from typing import Mapping, Protocol, Union, runtime_checkable
from typing import TypeVar, Generic, Optional, List, Any, Type, Sequence
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from src.shared.database.types import TenantContext
from src.shared.utils import tenant_ctxvars as ctxvars
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapper as SA_Mapper
from src.shared.errors import (
    ErrorCode,
    NotFoundError, 
    ConflictError, 
    DomainError, 
    RlsNotSetError)
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm.exc import UnmappedClassError
from typing import cast, Any
logger = structlog.get_logger(__name__)

# ---- Type constraints -------------------------------------------------------
# We need models that *have* a typed primary key attribute `id`.
@runtime_checkable
class HasId(Protocol):
    id: Any  # concrete models will provide a proper SQLAlchemy Mapped[...] type

# Type variables for generic repository
ModelType = TypeVar("ModelType", bound=HasId)
EntityType = TypeVar("EntityType")
IdType = TypeVar("IdType")

class Mapper(Protocol[ModelType, EntityType]):
     def to_domain(self, model: ModelType) -> EntityType: ...
     def to_orm(self, entity: EntityType) -> ModelType: ...

class BaseRepository(Generic[ModelType, EntityType, IdType], ABC):
    """
    Base repository providing generic CRUD operations with RLS enforcement.
    
    All operations enforce Row Level Security via GUC settings and provide
    clean domain/ORM boundaries through abstract conversion methods.
    """
    
    def __init__(self, session: AsyncSession, model_class: Type[ModelType], mapper: Mapper[ModelType, EntityType], 
                 verify_rls_on_call: bool = False):
        self._session = session
        self._model_class = model_class
        self._mapper = mapper
        self._verify_rls_on_call = verify_rls_on_call

    async def _assert_rls(self) -> None:
        """
        Very lightweight defense-in-depth: ensure tenant_id GUC is present.
        Safe no-op if verification SQL fails upstream mapping to DomainError.
        """
        if not self._verify_rls_on_call:
            return
        # Avoid circular import at module load
        from src.shared.database.rls import verify_rls_context  # type: ignore
        await verify_rls_context(self._session)

    async def get_by_id(self, id_value: IdType) -> Optional[EntityType]:
        """Get entity by ID with RLS enforcement."""
        
        try:
            await self._assert_rls()
            stmt = select(self._model_class).where(self._model_class.id == id_value)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            return self._mapper.to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get by ID", extra={"id": id_value, "error": str(e)})
            raise self._map_error(e)
    
    

    async def get_one(self, **filters) -> Optional[EntityType]:
        """Get single entity by filters with RLS enforcement."""
        try:
            await self._assert_rls()
            stmt = select(self._model_class)
            for key, value in filters.items():
                if hasattr(self._model_class, key):
                    stmt = stmt.where(getattr(self._model_class, key) == value)
            
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            return self._mapper.to_domain(model) if model else None
        except Exception as e:
            logger.error("Failed to get one", extra={"filters": filters, "error": str(e)})
            raise self._map_error(e)
    
    async def list(
        self, 
        limit: int = 100, 
        offset: int = 0, 
        order_by: Union[None, str, Any, list[Any]] = None,
        **filters
    ) -> List[EntityType]:
        """List entities with pagination and RLS enforcement."""
        try:
            await self._assert_rls()
            stmt = select(self._model_class)
            
            # Apply filters
            for key, value in filters.items():
                if not hasattr(self._model_class, key):
                    raise DomainError(message=f"Unknown filter field '{key}'", code=ErrorCode.INVALID_REQUEST)
                stmt = stmt.where(getattr(self._model_class, key) == value)
            # Optional ordering for deterministic paging
            if order_by is not None:
                if isinstance(order_by, list):
                    for ob in order_by:
                        stmt = stmt.order_by(ob if not isinstance(ob, str) else getattr(self._model_class, ob))
                else:
                    stmt = stmt.order_by(order_by if not isinstance(order_by, str) else getattr(self._model_class, order_by))
            stmt = stmt.limit(limit).offset(offset)
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._mapper.to_domain(model) for model in models]
        except Exception as e:
            logger.error("Failed to list", extra={"limit": limit, "offset": offset, "error": str(e)})
            raise self._map_error(e)
    
    async def count(self, **filters) -> int:
        """Count entities with filters and RLS enforcement."""
        
        try:
            await self._assert_rls()
            stmt = select(func.count(self._model_class.id))
            
            # Apply filters
            for key, value in filters.items():
                if hasattr(self._model_class, key):
                    stmt = stmt.where(getattr(self._model_class, key) == value)
            
            result = await self._session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error("Failed to count", extra={"filters": filters, "error": str(e)})
            raise self._map_error(e)
    
    async def exists(self, **filters) -> bool:
        """Check if entity exists with filters and RLS enforcement."""
        await self._assert_rls()
        count = await self.count(**filters)
        return count > 0
    
    async def create(self, entity: EntityType) -> EntityType:
        """Create new entity with RLS enforcement."""        
        try:
            await self._assert_rls()
            model = self._mapper.to_orm(entity)
            self._session.add(model)
            await self._session.flush()
            await self._session.refresh(model)
            
            return self._mapper.to_domain(model)
        except IntegrityError as e:
            logger.error("Integrity error creating entity", extra={"error": str(e)})
            raise ConflictError(f"Entity creation failed due to constraint violation: {str(e)}")
        except Exception as e:
            logger.error("Failed to create entity", extra={"error": str(e)})
            raise self._map_error(e)
    
    async def upsert(self, entity: EntityType, conflict_columns: Sequence[str]) -> EntityType:
        """Insert or update entity on conflict."""
        
        try:
            await self._assert_rls()
            model = self._mapper.to_orm(entity)
            # Build a dict using SQLAlchemy inspection (no __table__ typing issues)
            try:
                # Pylance doesn't know inspect(...) is a Mapper, so cast for type safety.
                mapper = cast(SA_Mapper[Any], sa_inspect(self._model_class))
            except (NoInspectionAvailable, UnmappedClassError) as e:
                raise DomainError(f"Model {self._model_class!r} is not a mapped class: {e}",code=ErrorCode.INTERNAL_ERROR) from e

            col_names = [c.key for c in mapper.columns]

            model_dict = {name: getattr(model, name) for name in col_names}

            # model_dict = {c.name: getattr(model, c.name) for c in model.__table__.columns}
            
            stmt = pg_insert(self._model_class).values(**model_dict)
            # Build update dict excluding conflict columns and timestamps
            update_dict = {
                key: value for key, value in model_dict.items()
                if key not in conflict_columns and key != 'created_at'
            }
            
            if update_dict:
                stmt = stmt.on_conflict_do_update(
                    index_elements=conflict_columns,
                    set_=update_dict
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
            
            await self._session.execute(stmt)
            await self._session.flush()
            
            # Retrieve the upserted entity
            filters = {col: getattr(model, col) for col in conflict_columns}
            got = await self.get_one(**filters)
            if got is None:
                # This should be rare; guard for type checker and correctness.
                raise NotFoundError("Upsert succeeded but entity could not be reloaded")
            return got
            
        except Exception as e:
            logger.error("Failed to upsert entity", extra={"error": str(e)})
            raise self._map_error(e)
    
    async def update(self, entity: EntityType) -> EntityType:
        """Update existing entity with RLS enforcement."""        
        try:
            await self._assert_rls()
            model = self._mapper.to_orm(entity)
            merged_model = await self._session.merge(model)
            await self._session.flush()
            await self._session.refresh(merged_model)
            
            return self._mapper.to_domain(merged_model)
        except NoResultFound:
            raise NotFoundError("Entity not found for update")
        except IntegrityError as e:
            logger.error("Integrity error updating entity", extra={"error": str(e)})
            raise ConflictError(f"Entity update failed due to constraint violation: {str(e)}")
        except Exception as e:
            logger.error("Failed to update entity", extra={"error": str(e)})
            raise self._map_error(e)
    
    async def delete(self, id_value: IdType) -> bool:
        """Delete entity by ID with RLS enforcement."""
        try:
            await self._assert_rls()
            stmt = delete(self._model_class).where(self._model_class.id == id_value)
            result = await self._session.execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            logger.error("Failed to delete entity", extra={"id": id_value, "error": str(e)})
            raise self._map_error(e)
          
    def _map_error(self, error: Exception) -> DomainError:
        """Map database errors to domain errors."""
        if isinstance(error, IntegrityError):
            return ConflictError(f"Database constraint violation: {str(error)}")
        elif isinstance(error, NoResultFound):
            return NotFoundError("Requested resource not found")
        elif isinstance(error, (DomainError, RlsNotSetError)):
            return error  # Pass through domain errors
        else:
            logger.error("Unmapped database error", extra={"error": str(error), "type": type(error)})
            return DomainError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Database operation failed: {error!s}")
        
    async def update_fields(self, id_value: IdType, **values: Any) -> EntityType:
        """
        Efficient in-place update with RETURNING; still RLS-safe and mapped via self._mapper.
        """
        await self._assert_rls()
        stmt = (
            update(self._model_class)
            .where(self._model_class.id == id_value)
            .values(**values)
            .returning(self._model_class)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise NotFoundError("Requested resource not found")
        return self._mapper.to_domain(model)

    # --- helpers: SQL function/procedure calls --------------------------------
    def _build_params(self, *args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        """
        Build a portable placeholder list and a param map for text() statements.
        Positional args become :p0, :p1, ...; keyword args keep their names.
        """
        param_map: dict[str, Any] = {}
        pos_placeholders: list[str] = []
        for i, val in enumerate(args):
            key = f"p{i}"
            pos_placeholders.append(f":{key}")
            param_map[key] = val
        # kwargs override any duplicate keys from args (unlikely but explicit)
        for k, v in kwargs.items():
            param_map[k] = v
        placeholders = ",".join(pos_placeholders + [f":{k}" for k in kwargs.keys()])
        return placeholders, param_map

    async def call_function_scalar(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a SQL function and return a single scalar value.
        Example: SELECT my_fn(:...);
        """
        try:
            await self._assert_rls()
            placeholders, params = self._build_params(*args, **kwargs)
            stmt = text(f"SELECT {name}({placeholders})")
            result = await self._session.execute(stmt, params)
            return result.scalar_one_or_none()
        except Exception as e:
            raise self._map_error(e)

    async def call_function_rows(self, name: str, *args: Any, **kwargs: Any) -> List[Mapping[str, Any]]:
        """
        Execute a SQL function that returns rows (SETOF record/table) and return dicts.
        Example: SELECT * FROM my_table_fn(:...);
        """
        try:
            await self._assert_rls()
            placeholders, params = self._build_params(*args, **kwargs)
            stmt = text(f"SELECT * FROM {name}({placeholders})")
            result = await self._session.execute(stmt, params)
            # row mappings -> plain dicts
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            raise self._map_error(e)

    async def call_function_entities(self, name: str, *args: Any, **kwargs: Any) -> List[EntityType]:
        """
        Execute a SQL function that returns rows shaped exactly like self._model_class
        and map them into domain entities via the repository's mapper.
        """
        try:
            await self._assert_rls()
            placeholders, params = self._build_params(*args, **kwargs)
            # Use from_statement to hydrate ORM models directly
            stmt = select(self._model_class).from_statement(text(f"SELECT * FROM {name}({placeholders})"))
            result = await self._session.execute(stmt, params)
            models = result.scalars().all()
            return [self._mapper.to_domain(m) for m in models]
        except Exception as e:
            raise self._map_error(e)

    async def call_procedure(self, name: str, *args: Any, **kwargs: Any) -> None:
        """
        Execute a SQL stored procedure. Procedures don't return a value;
        any OUT/INOUT results must be fetched by the procedure itself
        or via subsequent queries.
        Example: CALL my_proc(:...);
        """
        try:
            await self._assert_rls()
            placeholders, params = self._build_params(*args, **kwargs)
            stmt = text(f"CALL {name}({placeholders})")
            await self._session.execute(stmt, params)
            # flush only if your proc mutates data you want later in the same tx
            await self._session.flush()
        except Exception as e:
            raise self._map_error(e)
