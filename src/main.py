from __future__ import annotations

import logging

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.identity.api.routes import auth_router, admin_router
from src.shared.exceptions import app_error_handler, AppError, unhandled_error_handler
from src.shared.middleware import RequestContextMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app")

app = FastAPI(title="WhatsApp Chatbot Platform API", version="1.0.0")

# Middlewares
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(admin_router)
app.include_router(auth_router)

# Error handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

@app.get("/healthz")
async def healthz():
    return {"ok": True}
