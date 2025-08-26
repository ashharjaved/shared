from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import TenantConfigView
from ..domain.services import ConfigurationService
from .commands import SetConfigCommand, DeleteConfigCommand


class ConfigurationHandlers:
    def __init__(self, service: ConfigurationService):
        self.service = service

    async def handle_set(self, session: AsyncSession, cmd: SetConfigCommand) -> TenantConfigView:
        return await self.service.set_config(
            session=session,
            dto=cmd,
        )


    async def handle_delete(self, session: AsyncSession, cmd: DeleteConfigCommand) -> None:
        await self.service.delete_config(
            session=session,
            dto=cmd,
        )
