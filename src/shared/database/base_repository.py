# src/shared/database/base_repository.py
"""
Base repository with generic CRUD operations and RLS enforcement.
"""

import logging
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable
from typing import TypeVar, Generic, Optional, List, Any, Dict, Type, Sequence
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.database.database import TenantContext
from src.shared.utils import tenant_ctxvars as ctxvars
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapper as SA_Mapper
from src.shared.errors import (
    NotFoundError, 
    ConflictError, 
    AppError, 
    RlsNotSetError,
    ValidationError
)
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm.exc import UnmappedClassError
from typing import cast, Any
logger = logging.getLogger(__name__)


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
    
    def __init__(self, session: AsyncSession, model_class: Type[ModelType], mapper: Mapper[ModelType, EntityType]):
        self._session = session
        self._model_class = model_class
        self._mapper = mapper
    
    # --- internal: build TenantContext from ctxvars ---
    def _current_ctx(self) -> TenantContext:
        snap = ctxvars.snapshot()
        tenant_id = snap.get("tenant_id")
        if not tenant_id:
            # keep it explicit so failures are clear at call site
            raise RlsNotSetError("Tenant context missing in ctxvars (tenant_id)")
        user_id = snap.get("user_id")
        roles_list = snap.get("roles") or []
        roles_csv = ",".join(roles_list) if isinstance(roles_list, list) else str(roles_list)
        return TenantContext(tenant_id=str(tenant_id), user_id=str(user_id), roles=roles_csv)

    async def get_by_id(self, id_value: IdType) -> Optional[EntityType]:
        """Get entity by ID with RLS enforcement."""
        
        try:
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
        **filters
    ) -> List[EntityType]:
        """List entities with pagination and RLS enforcement."""
        try:
            stmt = select(self._model_class)
            
            # Apply filters
            for key, value in filters.items():
                if hasattr(self._model_class, key):
                    stmt = stmt.where(getattr(self._model_class, key) == value)
            
            # Apply pagination
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
        count = await self.count(**filters)
        return count > 0
    
    async def create(self, entity: EntityType) -> EntityType:
        """Create new entity with RLS enforcement."""        
        try:
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
            model = self._mapper.to_orm(entity)
            # Build a dict using SQLAlchemy inspection (no __table__ typing issues)
            try:
                # Pylance doesn't know inspect(...) is a Mapper, so cast for type safety.
                mapper = cast(SA_Mapper[Any], sa_inspect(self._model_class))
            except (NoInspectionAvailable, UnmappedClassError) as e:
                raise AppError(f"Model {self._model_class!r} is not a mapped class: {e}")

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
            stmt = delete(self._model_class).where(self._model_class.id == id_value)
            result = await self._session.execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            logger.error("Failed to delete entity", extra={"id": id_value, "error": str(e)})
            raise self._map_error(e)
          
    def _map_error(self, error: Exception) -> AppError:
        """Map database errors to domain errors."""
        if isinstance(error, IntegrityError):
            return ConflictError(f"Database constraint violation: {str(error)}")
        elif isinstance(error, NoResultFound):
            return NotFoundError("Requested resource not found")
        elif isinstance(error, (AppError, RlsNotSetError)):
            return error  # Pass through domain errors
        else:
            logger.error("Unmapped database error", extra={"error": str(error), "type": type(error)})
            return AppError(f"Database operation failed: {str(error)}")
