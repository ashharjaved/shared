"""
Organization DTOs
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrganizationDTO:
    """
    Organization Data Transfer Object used within the application layer.
    """
    id: str
    name: str
    slug: str
    industry: str
    is_active: bool
    created_at: str
    timezone: str
    language: str
