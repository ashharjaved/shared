# /src/shared/utils/retry.py
"""
Async retry with exponential backoff + jitter.

- async def retry(fn, *, attempts=3, base_ms=50, max_ms=2000, jitter_ms=50, retry_on=(Exception,))
"""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, Iterable, Tuple, Type

ExcTuple = Tuple[Type[BaseException], ...]

async def retry(
    fn: Callable[[], Awaitable],
    *,
    attempts: int = 3,
    base_ms: int = 50,
    max_ms: int = 2000,
    jitter_ms: int = 50,
    retry_on: Iterable[Type[BaseException]] = (Exception,),
):
    exc_types: ExcTuple = tuple(retry_on)
    delay = base_ms
    last_exc: BaseException | None = None
    for i in range(attempts):
        try:
            return await fn()
        except exc_types as e:
            last_exc = e
            if i == attempts - 1:
                break
            jitter = random.randint(0, jitter_ms)
            await asyncio.sleep(min((delay + jitter) / 1000.0, max_ms / 1000.0))
            delay = min(delay * 2, max_ms)
    if last_exc:
        raise last_exc
