# src/identity/infrastructure/models/user_model.py
"""
User ORM model.
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Index, String, Boolean, DateTime, Integer, ForeignKey, UniqueConstraint, text, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID, CITEXT
from sqlalchemy.orm import relationship

from src.shared.database.base_model import BaseModel


class UserModel(BaseModel):
    """User ORM model (app_user table)."""
    
    __tablename__ = "users"
    
    id = Column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(PgUUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False)
    email = Column(CITEXT, nullable=False)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    roles = Column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now() at time zone 'utc'"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now() at time zone 'utc'"),server_onupdate=text("now() at time zone 'utc'"))
    
    # Relationships  
    tenant = relationship("TenantModel", back_populates="users")
    memberships = relationship("MembershipModel", back_populates="user", cascade="all, delete-orphan")
    
    # Unique constraint for email per tenant
    __table_args__ = (
        Index("ix_users_tenant_email", "tenant_id", "email"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        {"postgresql_partition_by": "tenant_id"},  # Enable partitioning if needed
    )
