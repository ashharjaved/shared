# src/identity/infrastructure/mapper/user_mapper.py
from ast import Name
from datetime import datetime
import logging
from typing import List, Optional, overload, cast as typecast
from uuid import UUID

from identity.domain.types import TenantId, UserId
from src.identity.domain.entities.user import User
from src.identity.domain.value_objects import Email, Role, Timestamps, PasswordHash, Phone
from src.identity.infrastructure.models.user_model import UserModel

logger = logging.getLogger(__name__)

class UserMapper:    
    def to_domain(self, model: UserModel) -> User:
        if model is None:
            return None
        id_val: UUID = typecast(UUID, getattr(model, "id"))

        role_values: List[Role] = []
        if model.roles is not None:
            for r in model.roles:
                try:
                    role_values.append(Role(r))
                except Exception:
                    logger.warning(
                        "Unknown role value in DB; skipping",
                        extra={"role": r, "user_id": str(model.id)},
                    )
        # Timestamps
        created_at_val = typecast(datetime, getattr(model, "created_at"))
        updated_at_val = typecast(datetime, getattr(model, "updated_at"))

        # Final precise typing for timestamps
        ts = Timestamps.from_datetimes(
            created_at=created_at_val,
            updated_at=updated_at_val,
        )

        email_vo = Email(str(model.email))
        user_id: UserId = UserId(id_val)
        tenant_id: TenantId = TenantId(id_val)
        phone_vo = Phone.from_string(str(model.phone)) if getattr(model, "phone", None) else None
        password_vo = PasswordHash(str(model.password_hash))

        # Extract actual values for failed_login_attempts and last_login
        failed_login_attempts_val = int(getattr(model, "failed_login_attempts", 0))
        last_login_val = getattr(model, "last_login", None)

        return User(
            id=user_id,
            tenant_id=tenant_id,
            email=email_vo,
            phone=phone_vo,
            password_hash=password_vo,
            roles=role_values,
            is_active=bool(model.is_active),
            last_login=last_login_val,
            failed_login_attempts=failed_login_attempts_val,
            timestamps=ts,
        )

    def to_orm(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            email=str(entity.email),
            phone=str(entity.phone) if entity.phone else None,
            password_hash=str(entity.password_hash),
            roles=[r.value if isinstance(r, Role) else str(r) for r in entity.roles],
            is_active=bool(entity.is_active),
            last_login=entity.last_login,
            failed_login_attempts=int(entity.failed_login_attempts),
            # created_at/updated_at are DB-managed (defaults/onupdate)
        )