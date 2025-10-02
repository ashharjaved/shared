"""
Role DTOs
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RoleDTO:
    """
    Role Data Transfer Object.
    """
    id: str
    organization_id: str
    name: str
    permissions: list[str]
    is_system: bool
    created_at: str
    description: Optional[str] = None