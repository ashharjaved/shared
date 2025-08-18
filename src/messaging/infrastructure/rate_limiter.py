from __future__ import annotations
import time
from typing import Dict, Tuple

class TokenBucketLimiter:
    def __init__(self, rate_per_sec: int, capacity: int | None = None):
        self.rate = rate_per_sec
        self.capacity = capacity or rate_per_sec
        self._buckets: Dict[str, Tuple[float, float]] = {}

    def allow(self, key: str, tokens: float = 1.0) -> bool:
        now = time.time()
        tk, last = self._buckets.get(key, (self.capacity, now))
        tk = min(self.capacity, tk + (now - last) * self.rate)
        if tk >= tokens:
            tk -= tokens
            self._buckets[key] = (tk, now)
            return True
        self._buckets[key] = (tk, now)
        return False
