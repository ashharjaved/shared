
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID
from messaging.domain.entities import OutboxEvent
from messaging.domain.value_objects import OutboxEventType

class OutboxRepository(ABC):
    @abstractmethod
    async def add(self, tenant_id: UUID, event: OutboxEvent, idempotency_key: Optional[str] = None) -> None: ...
    @abstractmethod
    async def add_many(self, tenant_id: UUID, events: List[OutboxEvent]) -> None: ...
    @abstractmethod
    async def get_unprocessed_events(
        self, tenant_id: UUID, event_type: Optional[OutboxEventType] = None, limit: int = 100
    ) -> List[OutboxEvent]: ...
    @abstractmethod
    async def claim_next_batch(self, tenant_id: UUID, worker_id: str, lease_seconds: int = 30, limit: int = 100) -> List[OutboxEvent]: ...
    @abstractmethod
    async def mark_processed(self, tenant_id: UUID, event_id: int) -> None: ...
    @abstractmethod
    async def mark_failed(self, tenant_id: UUID, event_id: int, error_code: str) -> None: ...
