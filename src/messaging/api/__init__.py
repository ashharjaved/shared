"""Messaging API module initialization."""

from fastapi import APIRouter
from src.messaging.api.routes import (
    channel_routes,
    message_routes,
    template_routes,
    webhook_routes
)

# Create main messaging router
messaging_router = APIRouter(prefix="/messaging")

# Include all sub-routers
messaging_router.include_router(channel_routes.router)
messaging_router.include_router(message_routes.router)
messaging_router.include_router(template_routes.router)

# Webhook routes are registered separately without the /messaging prefix
webhook_router = webhook_routes.router

__all__ = ["messaging_router", "webhook_router"]