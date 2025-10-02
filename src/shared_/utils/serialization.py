# /src/shared/utils/serialization.py
"""
Safe JSON helpers with support for datetime, UUID, Decimal.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Union
from uuid import UUID

from src.shared_.errors import ValidationError
JSONValue = Union[str, int, float, bool, None, "JSONObject", "JSONArray"]
JSONObject = Dict[str, JSONValue]
JSONArray = List[JSONValue]

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

def convert_to_jsonvalue(data: Any) -> JSONValue:
    """Recursively convert a value to a JSONValue-compatible type."""
    if isinstance(data, (str, int, float, bool, type(None))):
        return data
    elif isinstance(data, list):
        return [convert_to_jsonvalue(item) for item in data]
    elif isinstance(data, dict):
        return {key: convert_to_jsonvalue(value) for key, value in data.items()}
    else:
        raise ValidationError(f"Value {data} is not JSON-serializable")

def ensure_jsonvalue_context(context: Mapping[str, Any]) -> Dict[str, JSONValue]:
    """Convert a Mapping[str, Any] to Dict[str, JSONValue]."""
    return {key: convert_to_jsonvalue(value) for key, value in context.items()}