from __future__ import annotations
import logging, uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.identity.api.routes import router as identity_router
from src.platform.api.routes import router as platform_config_router
from src.identity.api.routes import router as auth_router
from src.identity.api.routes import router as identity_router
from src.platform.api.routes import router as platform_config_router
from src.identity.api.routes import router as auth_router
from src.messaging.api.routes import router as messaging_routes
from src.messaging.api.webhooks import router as messaging_webhooks

app = FastAPI(title="WhatsApp Chatbot Platform - API", version="1.0")

logger = logging.getLogger("uvicorn.error")


from fastapi.middleware.cors import CORSMiddleware
from src.shared.middleware import LoggingMiddleware
from src.shared.exceptions import add_exception_handlers

def create_app() -> FastAPI:
    app = FastAPI(
        title="WhatsApp Chatbot Platform",
        description="Enterprise SaaS platform for multi-tenant chatbot management",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    add_exception_handlers(app)
    app.include_router(platform_config_router)

    app.include_router(auth_router)
    return app

app = create_app()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp-chatbot-platform"}

@app.middleware("http")
async def add_request_id_and_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception as ex:
        logger.exception("unhandled_error", extra={"request_id": rid})
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    response.headers["X-Request-Id"] = rid
    return response

# Mount Identity routes
app.include_router(identity_router)
app.include_router(messaging_webhooks)  # public (signature verified)
app.include_router(messaging_routes)    # protected (Bearer)