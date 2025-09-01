from time import perf_counter
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

async def health_db_old(db: AsyncSession = Depends(get_db_session)):
    try:
        await db.execute(text("SELECT 1"))
        return {"service": "postgres", "status": "ok"}
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"service": "postgres", "status": "unavailable"},
        )

@router.get("/_health/db", status_code=status.HTTP_200_OK)
async def health_db():
    Session = get_db_session()
    t0 = perf_counter()
    try:
        async with Session() as s:
            await s.execute(text("SELECT 1"))
        dt_ms = int((perf_counter() - t0) * 1000)
        return {"ok": True, "checks": {"db_select_1_ms": dt_ms}}
    except Exception as e:
        # Return 503 with the error string so you can SEE the real cause
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "ok": False,
                "checks": {"db": "SELECT 1 failed"},
                "error": type(e).__name__,
                "detail": str(e),
            },
        )