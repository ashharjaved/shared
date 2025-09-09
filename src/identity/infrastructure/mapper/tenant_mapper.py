from __future__ import annotations

from datetime import datetime
from typing import Optional, overload, cast as typecast
from uuid import UUID

from identity.domain.value_objects import Slug, Timestamps, Name
from src.identity.domain.entities.tenant import Tenant
from src.identity.domain.types import TenantId, TenantType
from src.identity.infrastructure.models.tenant_model import TenantModel


class TenantMapper:
    """Mapper for Tenant entity and TenantModel."""

    # --- to_domain ---

    @overload
    def to_domain(self, model: TenantModel) -> Tenant: ...
    @overload
    def to_domain(self, model: None) -> None: ...

    def to_domain(self, model: Optional[TenantModel]) -> Optional[Tenant]:
        """
        Convert ORM model -> domain entity.

        Notes:
        - Do NOT use sqlalchemy.cast; it is for SQL expressions only.
        - Pylance sees ORM attributes as Column[...] at type-check time. We narrow with typing.cast.
        """
        if model is None:
            return None

        # Narrow all ORM attributes to their runtime Python types
        # IDs
        id_val: UUID = typecast(UUID, getattr(model, "id"))
        parent_id_val: Optional[UUID] = typecast(Optional[UUID], getattr(model, "parent_id"))

        # Scalars
        name_val: str = typecast(str, getattr(model, "name"))
        slug_val: str = typecast(str, getattr(model, "slug"))
        tenant_type_val: str = typecast(str, getattr(model, "tenant_type"))  # Enum mapped as str
        is_active_val: bool = bool(getattr(model, "is_active"))

        # Timestamps
        created_at_val = typecast(object, getattr(model, "created_at"))
        updated_at_val = typecast(object, getattr(model, "updated_at"))

        # Final precise typing for timestamps
        # Timestamps.from_datetimes requires datetime objects
        ts = Timestamps.from_datetimes(
            created_at=typecast("datetime", created_at_val),
            updated_at=typecast("datetime", updated_at_val),
        )

        # Wrap to domain types
        tenant_id: TenantId = TenantId(id_val)
        parent_tid: Optional[TenantId] = TenantId(parent_id_val) if parent_id_val else None
        tenant_type: TenantType = typecast(TenantType, tenant_type_val)

        return Tenant(
            id=tenant_id,
            name=Name(name_val),
            slug=Slug(slug_val),
            tenant_type=tenant_type,
            parent_tenant_id=parent_tid,
            is_active=is_active_val,
            timestamps=ts,
        )

    # --- to_orm ---

    def to_orm(self, entity: Tenant) -> TenantModel:
        """
        Convert domain entity -> ORM model.
        """
        def _unwrap_tid(tid: Optional[TenantId]) -> Optional[UUID]:
            return UUID(str(tid)) if tid is not None else None

        return TenantModel(
            id=UUID(str(entity.id)),
            parent_id=_unwrap_tid(entity.parent_tenant_id),
            name=str(entity.name),
            slug=str(entity.slug),
            tenant_type=entity.tenant_type,  # string literal compatible with ORM Enum
            is_active=entity.is_active,
            created_at=entity.timestamps.created_at,
            updated_at=entity.timestamps.updated_at,
        )