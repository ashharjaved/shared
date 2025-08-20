from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict
from uuid import UUID
from ..api.schemas import TriggerRequest, SessionRead, FlowRead
from ..application.commands import TriggerFlow
from ..application.handlers import handle_trigger_flow
from sqlalchemy.ext.asyncio import AsyncSession
from ...shared.security import get_principal
from src.dependencies import get_session
from src.config import Settings, get_settings
router = APIRouter(prefix="/api/v1/ce", tags=["conversation"])

@router.post("/trigger")
async def trigger_flow(req: TriggerRequest,
                       db: AsyncSession = Depends(get_session),
                       settings: Settings = Depends(get_settings),
                       principal: Any = Depends(get_principal)) -> Dict[str, Any]:
    # tenant guard
    if str(req.tenant_id) != str(getattr(principal, "tenant_id", None)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")
    result = await handle_trigger_flow(db, settings, TriggerFlow(
        tenant_id=req.tenant_id,
        channel_id=req.channel_id,
        contact_id=req.contact_id,
        inbound_payload=req.payload,
        event_id=req.event_id
    ))
    return {"ok": True, **result}
