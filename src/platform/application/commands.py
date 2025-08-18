from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SetConfig:
    tenant_id: str
    key: str
    value: Any
