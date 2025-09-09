# /src/shared/utils/serialization.py
"""
Safe JSON helpers with support for datetime, UUID, Decimal.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

class SafeEncoder(json.JSONEncoder):
    def default(self, o: Any):
        if isinstance(o, (datetime,)):
            return o.isoformat()
        if isinstance(o, (UUID,)):
            return str(o)
        if isinstance(o, (Decimal,)):
            return float(o)
        return super().default(o)

def dumps(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), cls=SafeEncoder)

def loads(s: str) -> Any:
    return json.loads(s)
