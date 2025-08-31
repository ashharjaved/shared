from fastapi import APIRouter, status, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.cache import get_redis
from src.shared.database import get_session as get_db_session

router = APIRouter(tags=["Health"])

@router.get("/_health/redis")
async def health_redis():
    try:
        r = await get_redis()
        pong = await r.ping()
        return {"service": "redis", "status": "ok" if pong else "degraded"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"service": "redis", "status": "unavailable"},
        )

@router.get("/_health/db")
async def health_db(db: AsyncSession = Depends(get_db_session)):
    try:
        await db.execute(text("SELECT 1"))
        return {"service": "postgres", "status": "ok"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"service": "postgres", "status": "unavailable"},
        )
