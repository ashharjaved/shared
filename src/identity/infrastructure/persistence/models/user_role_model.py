"""
UserRole ORM Model
Maps to identity.user_roles table
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from identity.infrastructure.persistence.models.user_model import UserModel
from identity.infrastructure.persistence.models.role_model import RoleModel
from shared.infrastructure.database.base_model import Base


class UserRoleModel(Base):
    """
    SQLAlchemy model for identity.user_roles table.
    
    Many-to-many mapping between users and roles.
    """
    
    __tablename__ = "user_roles"
    __table_args__ = {"schema": "identity"}
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    
    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Audit Fields
    granted_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("identity.users.id"),
        nullable=True,
    )
    
    # Relationships
    user: Mapped[UserModel] = relationship(
        "UserModel",
        back_populates="user_roles",
        foreign_keys=[user_id],
        lazy="joined",
    )
    role: Mapped[RoleModel] = relationship(
        "RoleModel",
        back_populates="user_roles",
        lazy="joined",
    )
    
    def __repr__(self) -> str:
        return f"<UserRoleModel(user_id={self.user_id}, role_id={self.role_id})>"