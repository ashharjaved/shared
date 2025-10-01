# src/identity/infrastructure/mappers/tenant_mapper.py
from __future__ import annotations

from src.identity.domain.entities.tenant import Tenant
from src.identity.infrastructure.models.tenant_model import TenantModel

class TenantMapper:
    """
    Converts between the domain entity `Tenant` and the SQLAlchemy ORM `TenantModel`.
    Compatible with BaseRepository's Mapper protocol (to_domain / to_orm).
    """
    def to_domain(self, model: TenantModel) -> Tenant:
        """ORM -> Domain"""
        return Tenant(
            id=model.id,
            name=model.name,
            type=model.type,
            parent_tenant_id=model.parent_tenant_id,
            is_active=bool(model.is_active),
            created_at=model.created_at,
            updated_at=model.updated_at,
            remarks=model.remarks,
        )
    
    def to_orm(self, entity: Tenant) -> TenantModel:
            """Domain -> ORM (detached instance; not yet added to session)"""
            return TenantModel(
                id=entity.id,
                name=entity.name,
                type=entity.type,
                parent_tenant_id=entity.parent_tenant_id,
                is_active=entity.is_active,
                created_at=entity.created_at,
                updated_at=entity.updated_at,
                remarks=entity.remarks,
            )


    # Optional: keep old name for any legacy callers
    from_domain = to_orm