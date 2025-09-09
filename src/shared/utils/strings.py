# /src/shared/utils/strings.py
"""
Robust string utilities.
"""

from __future__ import annotations

import re

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
