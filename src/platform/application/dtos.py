from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True, slots=True)
class ConfigDTO:
    key: str
    value: Dict[str, Any]
    is_encrypted: bool
    config_type: str
    source: str  # "tenant" | "reseller" | "platform"


@dataclass(frozen=True, slots=True)
class EffectiveRateLimitDTO:
    requests_per_minute: int
    burst_limit: int
    scope: str  # "TENANT" or "GLOBAL"
    source: str  # "tenant" | "global"


@dataclass(frozen=True, slots=True)
class RateLimitDecisionDTO:
    allowed: bool
    remaining_in_window: Optional[int] = None
    reason: Optional[str] = None
