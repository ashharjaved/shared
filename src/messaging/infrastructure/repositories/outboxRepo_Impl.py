
from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from messaging.domain.entities import OutboxEvent
from messaging.domain.repositories.outbox_repo import OutboxRepository
from messaging.infrastructure.model.outboxModel import OutboxModel


class SQLAOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add(self, event: OutboxEvent) -> None:
        model = OutboxModel(
            tenant_id=event.tenant_id,
            payload=event.payload,
            created_at=event.created_at,
            processed_at=event.processed_at
        )
        self.session.add(model)
        await self.session.flush()
    
    async def get_unprocessed_events(self, limit: int = 100) -> List[OutboxEvent]:
        result = await self.session.execute(
            select(OutboxModel)
            .where(OutboxModel.processed_at.is_(None))
            .limit(limit)
        )
        events = []
        for model in result.scalars().all():
            events.append(OutboxEvent(
                id=model.id,
                tenant_id=model.tenant_id,
                payload=model.payload,
                created_at=model.created_at,
                processed_at=model.processed_at
            ))
        return events
    
    async def mark_processed(self, event_id: int) -> None:
        await self.session.execute(
            update(OutboxModel)
            .where(OutboxModel.id == event_id)
            .values(processed_at=datetime.utcnow())
        )
        