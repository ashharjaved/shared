from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ConfigEntry:
    tenant_id: str
    key: str
    value: Any
