# src/identity/domain/entities/plan.py
"""Plan entity."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from ..types import PlanId, JsonDict
from ..value_objects import Slug, Name
from ..errors import ValidationError


@dataclass(slots=True)
class Plan:
    """Subscription plan entity."""
    
    id: PlanId
    slug: Slug
    name: Name
    price_inr: Decimal
    features_json: JsonDict
    is_active: bool
    
    def __post_init__(self) -> None:
        """Validate plan invariants."""
        if self.price_inr < 0:
            raise ValidationError("Plan price cannot be negative")
    
    @classmethod
    def create(
        cls,
        slug: str,
        name: str,
        price_inr: Decimal | float,
        features: dict[str, object],
    ) -> 'Plan':
        """Create new plan."""
        slug_vo = Slug(slug)
        name_vo = Name(name)
        price = Decimal(str(price_inr))
        
        return cls(
            id=PlanId(uuid4()),
            slug=slug_vo,
            name=name_vo,
            price_inr=price,
            features_json=features,
            is_active=True,
        )
    
    def activate(self) -> None:
        """Activate plan."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate plan."""
        self.is_active = False
    
    def has_feature(self, feature_key: str) -> bool:
        """Check if plan has specific feature."""
        return str(feature_key) in (self.features_json or {})
    
    def get_feature_value(self, feature_key: str, default: object = None) -> object:
        """Get feature value with default."""
        return self.features_json.get(feature_key, default)