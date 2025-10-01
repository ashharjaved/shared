# src/identity/infrastructure/mappers/user_mapper.py
from __future__ import annotations

from src.identity.domain.entities.user import User
from src.identity.infrastructure.models.user_model import UserModel


class UserMapper:
    """
    Converts between the domain entity `User` and the SQLAlchemy ORM `UserModel`.
    Compatible with BaseRepository's Mapper protocol (to_domain / to_orm).
    """

    def to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            tenant_id=model.tenant_id,
            email=model.email,
            password_hash=model.password_hash,
            role=model.role,
            is_active=model.is_active,
            is_verified=model.is_verified,
            failed_login_attempts=model.failed_login_attempts,
            last_login=model.last_login,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_orm(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            email=entity.email,
            password_hash=entity.password_hash,
            role=entity.role,
            is_active=entity.is_active,
            is_verified=entity.is_verified,
            failed_login_attempts=entity.failed_login_attempts,
            last_login=entity.last_login,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )