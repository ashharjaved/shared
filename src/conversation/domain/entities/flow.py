# src/conversation/domain/entities/flow.py
"""Flow entity - represents a conversation flow definition."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from src.shared.domain.entity import Entity
from src.conversation.domain.value_objects import FlowStatus, FlowVersion
from src.conversation.domain.entities.flow_step import FlowStep


class Flow(Entity):
    """
    Flow aggregate root.
    
    Represents a complete conversation flow with metadata and steps.
    Enforces business rules around flow lifecycle and versioning.
    """
    
    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        name: str,
        description: Optional[str],
        status: FlowStatus,
        version: FlowVersion,
        language: str,
        created_by: UUID,
        created_at: datetime,
        updated_at: datetime,
        published_at: Optional[datetime] = None,
        steps: Optional[List[FlowStep]] = None,
    ):
        super().__init__(id)
        self.tenant_id = tenant_id
        self.name = name
        self.description = description
        self.status = status
        self.version = version
        self.language = language
        self.created_by = created_by
        self.created_at = created_at
        self.updated_at = updated_at
        self.published_at = published_at
        self._steps = steps or []
        
    @property
    def steps(self) -> List[FlowStep]:
        """Get ordered list of steps."""
        return sorted(self._steps, key=lambda s: s.order)
    
    def add_step(self, step: FlowStep) -> None:
        """Add a step to the flow."""
        if self.status == FlowStatus.PUBLISHED:
            raise ValueError("Cannot modify published flow. Create new version.")
        
        # Check for duplicate step_key
        if any(s.step_key == step.step_key for s in self._steps):
            raise ValueError(f"Step key '{step.step_key}' already exists")
        
        self._steps.append(step)
        self.updated_at = datetime.utcnow()
    
    def update_step(self, step_key: str, updated_step: FlowStep) -> None:
        """Update an existing step."""
        if self.status == FlowStatus.PUBLISHED:
            raise ValueError("Cannot modify published flow. Create new version.")
        
        for i, step in enumerate(self._steps):
            if step.step_key == step_key:
                self._steps[i] = updated_step
                self.updated_at = datetime.utcnow()
                return
        
        raise ValueError(f"Step '{step_key}' not found")
    
    def remove_step(self, step_key: str) -> None:
        """Remove a step from the flow."""
        if self.status == FlowStatus.PUBLISHED:
            raise ValueError("Cannot modify published flow. Create new version.")
        
        self._steps = [s for s in self._steps if s.step_key != step_key]
        self.updated_at = datetime.utcnow()
    
    def publish(self) -> None:
        """Publish the flow for use."""
        if self.status == FlowStatus.PUBLISHED:
            raise ValueError("Flow already published")
        
        if not self._steps:
            raise ValueError("Cannot publish flow without steps")
        
        # Validate flow has entry point
        if not any(s.is_entry_point for s in self._steps):
            raise ValueError("Flow must have at least one entry point")
        
        self.status = FlowStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def archive(self) -> None:
        """Archive the flow (soft delete)."""
        if self.status == FlowStatus.ARCHIVED:
            raise ValueError("Flow already archived")
        
        self.status = FlowStatus.ARCHIVED
        self.updated_at = datetime.utcnow()
    
    def get_step(self, step_key: str) -> Optional[FlowStep]:
        """Get a step by its key."""
        for step in self._steps:
            if step.step_key == step_key:
                return step
        return None
    
    def get_entry_points(self) -> List[FlowStep]:
        """Get all entry point steps."""
        return [s for s in self._steps if s.is_entry_point]
    
    def validate(self) -> List[str]:
        """
        Validate flow configuration.
        
        Returns list of validation errors (empty if valid).
        """
        errors = []
        
        if not self._steps:
            errors.append("Flow has no steps")
            return errors
        
        # Check entry points
        entry_points = self.get_entry_points()
        if not entry_points:
            errors.append("Flow must have at least one entry point")
        
        # Validate each step
        step_keys = {s.step_key for s in self._steps}
        for step in self._steps:
            step_errors = step.validate(step_keys)
            errors.extend([f"Step '{step.step_key}': {err}" for err in step_errors])
        
        return errors