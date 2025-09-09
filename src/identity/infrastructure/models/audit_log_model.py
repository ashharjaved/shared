# src/identity/infrastructure/models/audit_log_model.py
"""
Audit log ORM model.
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, Index, String, DateTime, BigInteger, text, JSON
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncAttrs

from src.shared.database.base_model import BaseModel


class AuditLogModel(BaseModel):
    """Audit log ORM model for tracking changes."""
    
    __tablename__ = "audit_log"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    actor_user = Column(PgUUID(as_uuid=True), nullable=True)
    actor_tenant = Column(PgUUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)
    resource = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)
    __table_args__ = (
        Index("ix_audit_tenant_ts", "actor_tenant", "ts"),
        Index("ix_audit_action_ts", "action", "ts"),    
    )
    def __repr__(self) -> str:
        """Return a string representation of the model."""
        return f"<AuditLogModel(id={self.id}, ts={self.ts}, actor_user={self.actor_user}, actor_tenant={self.actor_tenant}, action={self.action}, resource={self.resource}, resource_id={self.resource_id}, before={self.before}, after={self.after})>"