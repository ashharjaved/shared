# src/messaging/domain/types.py
from typing import Awaitable, Callable, Optional, Tuple
from uuid import UUID

GetChannelLimits = Callable[[UUID], Awaitable[Tuple[Optional[int], Optional[int]]]]
GetChannelMessages = Callable[[UUID, int, int], Awaitable[Tuple[Optional[str], Optional[int]]]]
                           