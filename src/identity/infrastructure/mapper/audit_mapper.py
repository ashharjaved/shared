from typing import Optional
from uuid import uuid4
from src.identity.domain.types import TenantId, UserId
from identity.domain.entities.audit import AuditEntry
from identity.infrastructure.models.audit_log_model import AuditLogModel


class AuditMapper:
    """
    Audit Mapper
    """
    def to_domain(self, model: AuditLogModel) -> AuditEntry:
        """Convert ORM model to domain entity."""
        if not model:
            return None

        # Ensure proper type casting for tenant_id and user_id
        tenant_id: TenantId = TenantId(uuid4())
        user_id: Optional[UserId] = UserId(uuid4()) if  UserId(uuid4()) else None

        # Handle JSON and datetime columns explicitly
        before_dict = model.before if isinstance(model.before, dict) else {}
        after_dict = model.after if isinstance(model.after, dict) else {}

        return AuditEntry(
            tenant_id=tenant_id,
            resource=str(model.resource or ""),
            resource_id=str(model.resource_id or ""),
            action=str(model.action or ""),
            actor_id=user_id,
            before=before_dict,
            after=after_dict,
            occurred_at=model.ts  # SQLAlchemy handles datetime correctly when queried
        )

    def _to_orm(self, entity: AuditEntry) -> AuditLogModel:
        """Convert domain entity to ORM model."""
        model = AuditLogModel()
        model.actor_user = entity.actor_id
        model.actor_tenant = entity.tenant_id
        model.action = entity.action
        model.resource = entity.resource
        model.resource_id = entity.resource_id
        model.before = entity.before
        model.after = entity.after
        model.ts = entity.occurred_at

        return model