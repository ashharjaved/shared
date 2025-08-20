# from __future__ import annotations
# import logging, uuid
# from fastapi import FastAPI, Request
# from fastapi.responses import JSONResponse
# from src.identity.api.routes import router as identity_router
# from src.platform.api.routes import router as platform_config_router
# from src.messaging.api.routes import router as messaging_routes
# from src.messaging.api.webhooks import router as messaging_webhooks
# logger = logging.getLogger("uvicorn.error")
# from .conversation.api.routes import router as conversation_router

# from fastapi.middleware.cors import CORSMiddleware
# from src.shared.middleware import LoggingMiddleware
# from src.shared.exceptions import add_exception_handlers

# def create_app() -> FastAPI:
#     app = FastAPI(
#         title="WhatsApp Chatbot Platform",
#         description="Enterprise SaaS platform for multi-tenant chatbot management",
#         version="1.0.0",
#     )

#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=["*"],   # tighten in production
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )
#     add_exception_handlers(app)
#     app.include_router(platform_config_router)
#     return app

# app = create_app()

# @app.middleware("http")
# async def add_request_id_and_logging(request: Request, call_next):
#     rid = request.headers.get("X-Request-Id", str(uuid.uuid4()))
#     request.state.request_id = rid
#     try:
#         response = await call_next(request)
#     except Exception as ex:
#         logger.exception("unhandled_error", extra={"request_id": rid})
#         return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
#     response.headers["X-Request-Id"] = rid
#     return response

# # Mount Identity routes
# app.include_router(identity_router)
# app.include_router(messaging_webhooks)  # public (signature verified)
# app.include_router(messaging_routes)    # protected (Bearer)
# app.include_router(conversation_router)/
# --------------------------------------------------------------------------------------------
# src/main.py
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.shared.model_loader import import_all_models
from src.shared.exceptions import add_exception_handlers
# Optional: if you want structured request logs, uncomment the next line and the add_middleware call.
# from src.shared.middleware import LoggingMiddleware

logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    """
    Application factory. Registers ORM mappers before any router imports
    to avoid partially-initialized-module errors from circular imports.
    """
    # 1) Ensure all model modules are imported once (side-effect registration)
    import_all_models()

    # 2) Build app
    app = FastAPI(
        title="WhatsApp Chatbot Platform",
        description="Enterprise SaaS platform for multi-tenant chatbot management",
        version="1.0.0",
    )

    # 3) Middleware & exception handlers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # app.add_middleware(LoggingMiddleware)  # optional, if available
    add_exception_handlers(app)

    # 4) Import and include routers AFTER models are registered
    from src.platform.api.routes import router as platform_config_router
    from src.identity.api.routes import router as identity_router
    from src.messaging.api.routes import router as messaging_routes
    from src.messaging.api.webhooks import router as messaging_webhooks
    from src.conversation.api.routes import router as conversation_router

    app.include_router(platform_config_router)
    app.include_router(identity_router)
    app.include_router(messaging_webhooks)  # public (signature verified)
    app.include_router(messaging_routes)    # protected (Bearer)
    app.include_router(conversation_router)

    # 5) Meta endpoints
    @app.get("/", tags=["meta"])
    def root() -> Dict[str, Any]:
        return {"status": "ok", "name": "WhatsApp Chatbot Platform", "version": "1.0.0"}

    return app


# Uvicorn entrypoint
app = create_app()


# Request-ID + top-level error guard
@app.middleware("http")
async def add_request_id_and_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = rid
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled_error", extra={"request_id": rid})
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    response.headers["X-Request-Id"] = rid
    return response
