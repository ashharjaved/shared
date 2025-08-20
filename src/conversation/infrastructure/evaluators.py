from __future__ import annotations
from typing import Any, Dict, Callable
import operator
import re

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: float(a) >= float(b),
    "<=": lambda a, b: float(a) <= float(b),
    ">":  lambda a, b: float(a) > float(b),
    "<":  lambda a, b: float(a) < float(b),
    "in": lambda a, b: a in b,
    "contains": lambda a, b: (b in a) if isinstance(a, str) else False,
    "startswith": lambda a, b: str(a).startswith(str(b)),
}

TOKEN_RE = re.compile(r"^\s*(?P<left>[^!<>=]+?)\s*(?P<op>==|!=|>=|<=|>|<|in|contains|startswith)\s*(?P<right>.+?)\s*$")

def _dot_get(ctx: Dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        part = part.strip()
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur

def _parse_value(raw: str, ctx: Dict[str, Any]) -> Any:
    s = raw.strip()
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    # try dot-path
    if "." in s or s in ("payload","vars","config"):
        v = _dot_get(ctx, s)
        return v
    # try number
    try:
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return s

def safe_eval(expr: str, ctx: Dict[str, Any]) -> bool:
    expr = expr.strip()
    if expr.lower() == "default":
        return True
    m = TOKEN_RE.match(expr)
    if not m:
        return False
    left = _parse_value(m.group("left"), ctx)
    right = _parse_value(m.group("right"), ctx)
    op = m.group("op")
    fn = OPS.get(op)
    if not fn:
        return False
    try:
        return bool(fn(left, right))
    except Exception:
        return False
