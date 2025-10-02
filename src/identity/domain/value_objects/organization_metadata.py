"""
Organization Metadata Value Object
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from shared.domain.base_value_object import BaseValueObject


class OrganizationMetadataModel(BaseModel):
    """Organization configuration metadata"""
    timezone: str = Field(default="UTC", description="Organization timezone")
    language: str = Field(default="en", description="Primary language")
    branding: dict = Field(default_factory=dict, description="Logo, colors, etc.")
    features: dict = Field(default_factory=dict, description="Feature flags")
    limits: dict = Field(default_factory=dict, description="Usage limits")


class OrganizationMetadata(BaseValueObject):
    """
    Organization metadata value object.
    
    Encapsulates organization-specific configuration.
    """
    
    def __init__(
        self,
        timezone: str = "UTC",
        language: str = "en",
        branding: Optional[dict] = None,
        features: Optional[dict] = None,
        limits: Optional[dict] = None,
    ) -> None:
        self._data = OrganizationMetadataModel(
            timezone=timezone,
            language=language,
            branding=branding or {},
            features=features or {},
            limits=limits or {},
        )
        self._finalize_init()  # ← FIX: Enforce immutability
    
    @classmethod
    def from_dict(cls, data: dict) -> OrganizationMetadata:
        """Create from dictionary"""
        model = OrganizationMetadataModel(**data)
        return cls(
            timezone=model.timezone,
            language=model.language,
            branding=model.branding,
            features=model.features,
            limits=model.limits,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage"""
        return self._data.model_dump()
    
    @property
    def timezone(self) -> str:
        return self._data.timezone
    
    @property
    def language(self) -> str:
        return self._data.language
    
    @property
    def branding(self) -> dict:
        return self._data.branding
    
    @property
    def features(self) -> dict:
        return self._data.features
    
    @property
    def limits(self) -> dict:
        return self._data.limits
    
    def _get_equality_components(self) -> tuple:
        return (self._data.model_dump_json(),)