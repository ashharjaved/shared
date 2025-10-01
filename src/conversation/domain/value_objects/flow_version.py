# src/conversation/domain/value_objects/flow_version.py
"""Flow version value object."""

from typing import Optional
from pydantic import BaseModel, Field


class FlowVersion(BaseModel):
    """Semantic version for flows."""
    
    major: int = Field(..., ge=1, description="Major version")
    minor: int = Field(default=0, ge=0, description="Minor version")
    patch: int = Field(default=0, ge=0, description="Patch version")
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def increment_major(self) -> "FlowVersion":
        """Increment major version (breaking changes)."""
        return FlowVersion(major=self.major + 1, minor=0, patch=0)
    
    def increment_minor(self) -> "FlowVersion":
        """Increment minor version (new features)."""
        return FlowVersion(major=self.major, minor=self.minor + 1, patch=0)
    
    def increment_patch(self) -> "FlowVersion":
        """Increment patch version (bug fixes)."""
        return FlowVersion(major=self.major, minor=self.minor, patch=self.patch + 1)
    
    class Config:
        frozen = True