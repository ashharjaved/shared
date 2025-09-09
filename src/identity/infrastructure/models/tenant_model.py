# src/identity/infrastructure/models/tenant_model.py
"""
Tenant ORM model.
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Index, String, Boolean, DateTime, ForeignKey, Enum, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import relationship

from src.shared.database.base_model import BaseModel


class TenantModel(BaseModel):
    """Tenant ORM model with hierarchical support."""
    
    __tablename__ = "tenant"
    
    id = Column(PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    parent_id = Column(PgUUID(as_uuid=True), ForeignKey("tenant.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    tenant_type = Column(
        Enum("root", "reseller", "tenant", name="tenant_type_enum"), 
        nullable=False,
        server_default="tenant"
    )
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now() at time zone 'utc'"),)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now() at time zone 'utc'"),server_onupdate=text("now() at time zone 'utc'"))
    
    # Relationships
    parent = relationship("TenantModel", remote_side=[id], back_populates="children")
    children = relationship("TenantModel", back_populates="parent")
    memberships = relationship("MembershipModel", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tenants_slug", "slug", unique=True),
        Index("ix_tenants_type", "tenant_type"),
    )