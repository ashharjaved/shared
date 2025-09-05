# Begin: src/conversation/application/context.py ***
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(slots=True)
class RequestContext:
    """
    Lightweight context to propagate identifiers for logging/metrics.

    - request_id: correlation id per HTTP/Webhook request
    - tenant_id, user_id: from auth (user_id may be None on webhook)
    - channel_id, session_id: filled at runtime by the service
    """
    request_id: str
    tenant_id: UUID
    user_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
# End: src/conversation/application/context.py ***
