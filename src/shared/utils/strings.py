# /src/shared/utils/strings.py
"""
Robust string utilities.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Set

_SNAKE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_SNAKE_2 = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALNUM = re.compile(r"[^0-9a-zA-Z]+")

def to_snake(s: str) -> str:
    s = s.strip()
    s = _SNAKE_1.sub(r"\1_\2", s)
    s = _SNAKE_2.sub(r"\1_\2", s)
    s = _NON_ALNUM.sub("_", s)
    s = s.strip("_")
    return s.lower()

def slugify(s: str) -> str:
    s = to_snake(s)
    return s.replace("_", "-")

# 1) Normalize arbitrary strings to canonical snake_case keys
def normalize_role_value(s: Optional[str]) -> str:
    if not s:
        return ""
    s = s.strip().replace("-", "_").replace(" ", "_").lower()
    return s

def normalize_roles(raw: Any) -> Set[str]:
    """
    Accept roles as: list/tuple/set, single string, CSV string, or None.
    Returns UPPER-CASED set[str].
    """
    if raw is None:
        return set()
    if isinstance(raw, (set, list, tuple)):
        return {str(r).strip().upper() for r in raw if str(r).strip()}
    s = str(raw).strip()
    if not s:
        return set()
    if "," in s:
        return {part.strip().upper() for part in s.split(",") if part.strip()}
    return {s.upper()}

_E164 = re.compile(r"^\+?[1-9]\d{7,14}$")

def normalize_msisdn(s: str) -> str:
    s = s.strip().replace(" ", "").replace("-", "")
    if not _E164.match(s):
        raise ValueError("invalid_msisdn")
    return s if s.startswith("+") else f"+{s}"